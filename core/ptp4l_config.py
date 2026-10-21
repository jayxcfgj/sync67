"""PTP4L Config – format-preserving parser/serializer for /etc/linuxptp/ptp4l.conf.

Format: key<whitespace>value  (tab or spaces preserved)
Comments: # line or #key<whitespace>value (commented out)
"""

import os
import re
import shutil
import subprocess
from pathlib import Path

from core.net_interface import phc_index


class PTP4LConfigError(Exception):
    ...


_KV_RE = re.compile(r'^(\w[\w.]*)\s+(.+)$')
# Auch "# key value" (Leerzeichen nach #) als kommentierter Key erkennen
_COMMENTED_KV_RE = re.compile(r'^#\s*(\w[\w.]*)\s+(.+)$')
_SECTION_RE = re.compile(r'^#\s+[A-Z]')
_SECTION_HEADER_RE = re.compile(r'^\[([^\]]+)\]\s*$')

# Interface-Section-Defaults: exakt wie in der aktuellen
# /etc/linuxptp/ptp4l.conf unter [enp37s0] (Referenz: dort funktionieren
# die Werte). time_stamping bleibt bewusst kommentiert, damit der
# globale Wert weiter greift.
INTERFACE_DEFAULT_LINES = [
    'delay_mechanism\tE2E',
    'network_transport\tUDPv4',
    '# time_stamping\thardware',
    'delayAsymmetry\t0',
    'logMinPdelayReqInterval\t0',
    'logSyncInterval\t0',
    'logAnnounceInterval\t0',
    'announceReceiptTimeout\t3',
    'logMinDelayReqInterval\t0',
    'fault_reset_interval\t4',
    'fault_badpeernet_interval\t16',
]

# Strings from ptp4l binary that look like config keys but aren't
_SKIP_STRINGS = frozenset({
    'calloc', 'malloc', 'realloc', 'free', 'memcmp', 'memcpy', 'memset',
    'strlen', 'strcmp', 'strdup', 'strncmp', 'strncpy', 'strrchr',
    'strcasecmp', 'strerror', 'strtod', 'snprintf',
    'fopen', 'fclose', 'fgets', 'fseek', 'fwrite', 'fflush',
    'printf', 'perror', 'exit', 'signal',
    'send', 'recv', 'sendto', 'recvfrom', 'sendmsg', 'recvmsg',
    'poll', 'ioctl', 'connect', 'socket', 'bind',
    'unlink', 'usleep', 'sqrt', 'srandom',
    'getifaddrs', 'freeifaddrs', 'if_nametoindex', 'if_indextoname',
    'inet_aton', 'inet_pton', 'getsockname', 'getsockopt', 'setsockopt',
    'shmat', 'shmdt', 'shmget',
    'clock_gettime', 'clock_adjtime', 'timerfd_create', 'timerfd_settime',
    'getopt_long', 'optarg', 'stdin', 'stdout', 'stderr',
    'global', 'auto', 'none', 'true', 'false', 'normal', 'full',
    'hardware', 'software', 'legacy', 'onestep', 'p2p1step',
    'ieee1588', 'linreg', 'nullf', 'both', 'bond', 'team',
    'activebackup', 'activeport', 'generic', 'noop',
    'clockIdentity', 'slave_event_monitor', 'gmCapable',
    'hwts_filter', 'leapfile', 'interface_rate_tlv',
    'pi_f_offset_const', 'pi_offset_const', 'pi_max_frequency',
    'min_neighbor_prop_delay', 'ignore_transport_specific',
    'message_tag', 'in6addr_any', 'chmod', 'ethtool',
    'initial_delay', 'step_window', 'filter_weight', 'raw_weight',
    'ts2phc',
    'activebackup', 'activeport',
    'rising', 'falling', 'moving_average', 'moving_median',
    'down', 'insert', 'delete',
})


def detect_supported_params():
    """Scan ptp4l binary for supported config parameter names.
    
    Returns a set of known parameter names, or None if detection fails
    (which means all params are allowed as fallback).
    """
    try:
        result = subprocess.run(
            ['strings', '-n', '3', '/usr/sbin/ptp4l'],
            capture_output=True, text=True, timeout=5
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None
    
    if result.returncode != 0:
        return None
    
    params = set()
    for line in result.stdout.split('\n'):
        s = line.strip()
        if not s or len(s) < 3:
            continue
        if re.match(r'^[a-zA-Z][a-zA-Z0-9._]+$', s):
            if s not in _SKIP_STRINGS:
                params.add(s)
    return params if params else None


class PTP4LConfig:
    def __init__(self):
        self.default_path = str(Path(__file__).parent / 'ptp4l_default.cfg')
        self._lines = []
        self._data = {}
        self._line_map = {}  # key -> line_index
        self._loaded_path = None
        self._modified = False
        self._supported = detect_supported_params()

    # ─── Public API ──────────────────────────────────────────

    def load(self, path):
        self._loaded_path = str(path)
        try:
            with open(self._loaded_path, 'r') as f:
                raw = f.read()
        except FileNotFoundError:
            raise PTP4LConfigError(f"Config not found: {self._loaded_path}")
        self._lines = raw.split('\n')
        self._data = {}
        self._line_map = {}
        self._modified = False
        self._parse()

    def save(self, path=None):
        path = str(path or self._loaded_path)
        if not path:
            raise PTP4LConfigError("No path specified")
        if os.path.exists(path):
            shutil.copy(path, path + '.bak')
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)

            # Filter out lines with unsupported params (nur aktive Keys –
            # kommentierte Zeilen sind fuer ptp4l inert und werden
            # mitsamt Kommentar erhalten)
            if self._supported is not None:
                filtered = []
                for line in self._lines:
                    m = _KV_RE.match(line)
                    if m and m.group(1) not in self._supported:
                        continue
                    filtered.append(line)
                self._lines = filtered

            text = '\n'.join(self._lines)
            if not text.endswith('\n'):
                text += '\n'
            with open(path, 'w') as f:
                f.write(text)
        except OSError as e:
            raise PTP4LConfigError(f"Could not write {path}: {e}") from e
        self._modified = False

    def get(self, key, section='global'):
        return self._data.get(section, {}).get(key)

    def find(self, key):
        """(section, value) des ersten Vorkommens – sonst (None, None)."""
        for section, data in self._data.items():
            if key in data:
                return section, data[key]
        return None, None

    def get_sections(self):
        """Section-Header in Datei-Reihenfolge (nur im File vorhandene)."""
        out = []
        for line in self._lines:
            m = _SECTION_HEADER_RE.match(line)
            if m:
                out.append(m.group(1))
        return out

    def ensure_section(self, name):
        """Sorgt den Header [name] am Dateiende sicher an. False wenn da.

        Neue Sections bekommen sofort `phc_index` (aufgeloest ueber
        ethtool -T / Sysfs, -1 = auto) – ohne den Wert scheitert ptp4l
        bei mehreren NICs mit 'PHC device mismatch'.
        """
        if name in self.get_sections():
            return False
        while self._lines and self._lines[-1] == '':
            self._lines.pop()
        if self._lines:
            self._lines.append('')
        self._lines.append(f'[{name}]')
        self._lines.append(f'phc_index\t{phc_index(name)}')
        self._lines.append('')
        self._parse()
        self._modified = True
        return True

    def _section_bounds(self, section):
        """(start, end) Line-Bereich der Section; end = naechster Header
        bzw. Dateiende. None wenn die Section fehlt (ausser global)."""
        header_idx = None
        for idx, line in enumerate(self._lines):
            m = _SECTION_HEADER_RE.match(line)
            if not m:
                continue
            if header_idx is None and section == 'global' \
                    and m.group(1) != section:
                # global ohne eigenen Header: KVs vor erstem fremden Header
                return (0, idx)
            if m.group(1) == section:
                header_idx = idx
                break
        if header_idx is None:
            if section == 'global':
                return (0, len(self._lines))
            return None
        end = len(self._lines)
        for idx in range(header_idx + 1, len(self._lines)):
            if _SECTION_HEADER_RE.match(self._lines[idx]):
                end = idx
                break
        return (header_idx, end)

    def _shift_line_maps(self, from_idx):
        """Line-Indices nach einer Einfuegung ab from_idx +1 verschieben."""
        for sec_map in self._line_map.values():
            for key, idx in sec_map.items():
                if idx >= from_idx:
                    sec_map[key] = idx + 1

    def set(self, key, value, section='global'):
        if self._supported is not None and key not in self._supported:
            return False
        sec_data = self._data.setdefault(section, {})
        sec_map = self._line_map.setdefault(section, {})
        if key in sec_map:
            old = sec_data.get(key)
            # Auch Typ-Vergleich: '16' (Andere-Tab) == 16 (geparst) –
            # sonst schreibt set() die Zeile nur wegen Typ/Leerzeichen neu
            if old == value or str(old) == str(value):
                return False
            sec_data[key] = value

            # Update raw line
            idx = sec_map[key]
            old_line = self._lines[idx]
            m = _KV_RE.match(old_line) or _COMMENTED_KV_RE.match(old_line)
            if m:
                indent = old_line[:m.start(1)]
                self._lines[idx] = f"{indent}{key}\t{value}"
            self._modified = True
            return True

        # Key nicht in der Section – am Ende der Section einfuegen
        if section not in self.get_sections():
            self.ensure_section(section)
            # ensure_section parst neu -> Referenzen neu holen
            sec_data = self._data.setdefault(section, {})
            sec_map = self._line_map.setdefault(section, {})
        bounds = self._section_bounds(section)
        start, end = bounds
        insert_at = end
        while insert_at - 1 > start and self._lines[insert_at - 1].strip() == '':
            insert_at -= 1
        self._lines.insert(insert_at, f"{key}\t{value}")
        self._shift_line_maps(insert_at)
        sec_data[key] = value
        sec_map[key] = insert_at
        self._modified = True
        return True

    def get_comment_state(self, key, section='global'):
        """Returns whether a parameter is commented out."""
        idx = self._line_map.get(section, {}).get(key)
        if idx is None:
            return False
        return self._lines[idx].strip().startswith('#')

    def set_comment_state(self, key, commented, section='global'):
        """Setzt einen Parameter aktiv oder kommentiert ihn aus."""
        idx = self._line_map.get(section, {}).get(key)
        if idx is None:
            return False
        line = self._lines[idx]
        stripped = line.strip()
        if commented and not stripped.startswith('#'):
            self._lines[idx] = '#' + line.lstrip()
            self._modified = True
        elif not commented and stripped.startswith('#'):
            self._lines[idx] = stripped.lstrip('# ')
            self._modified = True
        else:
            return False
        return True

    def reset_to_default(self, preferred=None, available=None):
        """Config auf Default zuruecksetzen.

        Schreibt [global] aus der Default-Datei plus eine Interface-Section
        mit den Defaults wie in der Referenz-Conf. Interface-Namenwahl:
        preferred (Combo-Auswahl) wenn ptp-faehig, sonst erstes verfuegbares
        ptp-faehiges Interface, sonst preferred als Fallback.
        Liefert den verwendeten Interface-Namen oder None bei Fehler.
        """
        if not os.path.exists(self.default_path):
            return None
        if not self._loaded_path or self._loaded_path == self.default_path:
            return None
        if available is None:
            try:
                from core.net_interface import phc_interfaces
                available = phc_interfaces()
            except Exception:
                available = []
        if preferred and preferred in available:
            iface = preferred
        elif available:
            iface = available[0]
        else:
            iface = preferred
        try:
            # Read default, filter unsupported params, write to target
            with open(self.default_path) as f:
                default_lines = f.read().split('\n')

            filtered = []
            for line in default_lines:
                m = _KV_RE.match(line)
                if m and self._supported is not None and m.group(1) not in self._supported:
                    continue
                filtered.append(line)

            text = '\n'.join(filtered).rstrip('\n')
            if iface:
                text += f'\n\n[{iface}]\n'
                for line in INTERFACE_DEFAULT_LINES:
                    text += line + '\n'
                text += f'phc_index\t{phc_index(iface)}\n'
            if not text.endswith('\n'):
                text += '\n'

            with open(self._loaded_path, 'w') as f:
                f.write(text)
        except (OSError, PermissionError) as e:
            raise PTP4LConfigError(f"Could not reset: {e}") from e
        self._modified = True
        self.load(self._loaded_path)
        return iface

    def get_loaded_path(self):
        return self._loaded_path

    def is_modified(self):
        return self._modified

    def get_unsupported(self, meta_keys):
        """Return set of meta keys not supported by installed ptp4l."""
        if self._supported is None:
            return set()
        return {k for k in meta_keys if k not in self._supported}

    def sections(self):
        return ['Quick', 'Default', 'Port', 'Runtime', 'Servo', 'Transport', 'Interface']

    # ─── Parsing ─────────────────────────────────────────────

    def _parse(self):
        section = 'global'
        self._data = {section: {}}
        self._line_map = {section: {}}
        for idx, line in enumerate(self._lines):
            m = _SECTION_HEADER_RE.match(line)
            if m:
                section = m.group(1)
                self._data.setdefault(section, {})
                self._line_map.setdefault(section, {})
                continue
            m = _KV_RE.match(line)
            if m:
                key, val = m.group(1), m.group(2).strip()
                self._data[section][key] = self._parse_value(val)
                self._line_map[section][key] = idx
                continue
            m = _COMMENTED_KV_RE.match(line)
            if m:
                key, val = m.group(1), m.group(2).strip()
                self._data[section][key] = self._parse_value(val)
                self._line_map[section][key] = idx

    def _parse_value(self, val):
        val = val.strip()
        if val.startswith('0x'):
            return val
        # Preserve leading zero (e.g. octal file modes like 0660)
        if val.startswith('0') and len(val) > 1 and val[1:].isdigit():
            return val
        if val in ('0', '1'):
            return int(val)
        try:
            if '.' in val:
                return float(val)
            return int(val)
        except (ValueError, TypeError):
            pass
        return val


def format_value(value):
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    return str(value)
