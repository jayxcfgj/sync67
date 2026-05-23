"""PTP4L Config – format-preserving parser/serializer for /etc/linuxptp/ptp4l.conf.

Format: key<whitespace>value  (tab or spaces preserved)
Comments: # line or #key<whitespace>value (commented out)
"""

import os
import re
import shutil
import subprocess
from pathlib import Path


class PTP4LConfigError(Exception):
    ...


_KV_RE = re.compile(r'^(\w[\w.]*)\s+(.+)$')
_COMMENTED_KV_RE = re.compile(r'^#(\w[\w.]*)\s+(.+)$')
_SECTION_RE = re.compile(r'^#\s+[A-Z]')

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
    'fault_badpeernet_interval', 'ts2phc',
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

            # Filter out lines with unsupported params
            if self._supported is not None:
                filtered = []
                for line in self._lines:
                    m = _KV_RE.match(line) or _COMMENTED_KV_RE.match(line)
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

    def get(self, key):
        return self._data.get(key)

    def set(self, key, value):
        if self._supported is not None and key not in self._supported:
            return False
        if key in self._line_map:
            old = self._data.get(key)
            if old == value:
                return False
            self._data[key] = value

            # Update raw line
            idx = self._line_map[key]
            old_line = self._lines[idx]
            m = _KV_RE.match(old_line) or _COMMENTED_KV_RE.match(old_line)
            if m:
                indent = old_line[:m.start(1)]
                self._lines[idx] = f"{indent}{key}\t{value}"
            self._modified = True
            return True

        # Key not in file – append new line at end
        self._data[key] = value
        self._lines.append(f"{key}\t{value}")
        self._line_map[key] = len(self._lines) - 1
        self._modified = True
        return True

    def get_comment_state(self, key):
        """Returns whether a parameter is commented out."""
        idx = self._line_map.get(key)
        if idx is None:
            return False
        return self._lines[idx].strip().startswith('#')

    def set_comment_state(self, key, commented):
        """Setzt einen Parameter aktiv oder kommentiert ihn aus."""
        idx = self._line_map.get(key)
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

    def reset_to_default(self):
        if not os.path.exists(self.default_path):
            return False
        if not self._loaded_path or self._loaded_path == self.default_path:
            return False
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

            with open(self._loaded_path, 'w') as f:
                f.write('\n'.join(filtered))
                if not filtered[-1].endswith('\n'):
                    f.write('\n')
        except (OSError, PermissionError) as e:
            raise PTP4LConfigError(f"Could not reset: {e}") from e
        self._modified = True
        self.load(self._loaded_path)
        return True

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
        for idx, line in enumerate(self._lines):
            m = _KV_RE.match(line)
            if m:
                key, val = m.group(1), m.group(2).strip()
                self._data[key] = self._parse_value(val)
                self._line_map[key] = idx
                continue
            m = _COMMENTED_KV_RE.match(line)
            if m:
                key, val = m.group(1), m.group(2).strip()
                self._data[key] = self._parse_value(val)
                self._line_map[key] = idx

    def _parse_value(self, val):
        val = val.strip()
        if val.startswith('0x'):
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
