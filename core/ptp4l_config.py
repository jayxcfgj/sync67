"""PTP4L Config – format-preserving parser/serializer for /etc/linuxptp/ptp4l.conf.

Format: key<whitespace>value  (tab or spaces preserved)
Comments: # line or #key<whitespace>value (commented out)
"""

import os
import re
import shutil
from pathlib import Path


class PTP4LConfigError(Exception):
    ...


_KV_RE = re.compile(r'^(\w[\w.]*)\s+(.+)$')
_COMMENTED_KV_RE = re.compile(r'^#(\w[\w.]*)\s+(.+)$')
_SECTION_RE = re.compile(r'^#\s+[A-Z]')


class PTP4LConfig:
    def __init__(self):
        self.default_path = str(Path(__file__).parent / 'ptp4l_default.cfg')
        self._lines = []
        self._data = {}
        self._line_map = {}  # key -> line_index
        self._loaded_path = None
        self._modified = False

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
        if key not in self._line_map:
            return False
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

    def get_comment_state(self, key):
        """Gibt zurück ob ein Parameter auskommentiert ist."""
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
            shutil.copy(self.default_path, self._loaded_path)
        except (OSError, PermissionError) as e:
            raise PTP4LConfigError(f"Could not reset: {e}") from e
        self._modified = True
        self.load(self._loaded_path)
        return True

    def get_loaded_path(self):
        return self._loaded_path

    def is_modified(self):
        return self._modified

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
        if val in ('0', '1'):
            return int(val)
        try:
            if '.' in val:
                return float(val)
            return int(val, 0)  # handles 0x hex
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
