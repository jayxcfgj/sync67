"""AES67 SPA Config – format-preserving parser/serializer for pipewire-aes67.conf.

Strategy
--------
- Parse file into structured _data dict for readable access (get())
- Maintain _line_map: list of (path_tuple, line_idx) for every key=value
- When set() is called, modify _data AND update the raw line in _raw_lines
- When save() is called, write _raw_lines back to disk
- add/remove rtp_sink manipulates _raw_lines directly
"""

import os
import re
import shutil
from pathlib import Path
from copy import deepcopy


class ConfigNotFoundError(FileNotFoundError):
    ...
class ConfigParseError(ValueError):
    ...
class ConfigWriteError(IOError):
    ...


_SECTION_RE = re.compile(
    r'^(?P<indent>\s*)(?P<key>context\.\w+)\s*=\s*(?P<brace>[\[\{])\s*$'
)
_KV_RE = re.compile(
    r'^(?P<indent>\s*)(?P<key>[\w.\-]+)\s*=\s*(?P<value>.+?)\s*,?\s*$'
)
_BLOCK_START_RE = re.compile(
    r'^(?P<indent>\s*)(?P<key>[\w.\-]+)\s*=\s*(?P<brace>[\[\{])\s*$'
)


def parse_value(val_str):
    val_str = val_str.strip().rstrip(',')
    if not val_str:
        return ''
    if val_str == 'true':
        return True
    if val_str == 'false':
        return False
    if val_str in ('null', 'nil', '~'):
        return None
    if val_str.startswith('"') and val_str.endswith('"'):
        return val_str
    try:
        if '.' in val_str:
            return float(val_str)
        return int(val_str)
    except ValueError:
        return val_str


def format_value(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, list):
        inner = ', '.join(format_value(v) for v in value)
        return '[ ' + inner + ' ]'
    if isinstance(value, dict):
        return '{ }'
    if value is None:
        return 'null'
    return str(value)


class AES67Config:
    def __init__(self):
        self.default_path = "/usr/share/pipewire/pipewire-aes67.conf"

        self._raw_lines = []     # list of str (preserved from original)
        self._data = {}          # structured parsed data
        self._line_map = []      # list of (path_tuple, line_idx)
        self._loaded_path = None
        self._modified = False

    # ─── Public API ──────────────────────────────────────────────

    def load(self, path):
        self._loaded_path = str(path)
        try:
            with open(self._loaded_path, 'r', encoding='utf-8') as f:
                raw = f.read()
        except FileNotFoundError:
            raise ConfigNotFoundError(f"Config not found: {self._loaded_path}")

        self._raw_lines = raw.split('\n')
        self._line_map = []
        self._data = {}
        self._modified = False
        self._parse()

    def save(self, path=None):
        path = str(path or self._loaded_path)
        if not path:
            raise ConfigWriteError("No path specified")
        if os.path.exists(path):
            shutil.copy(path, path + '.bak')
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(self._raw_lines))
        except OSError as e:
            raise ConfigWriteError(f"Could not write {path}: {e}") from e
        self._modified = False

    def get(self, *keys):
        if not keys:
            return None
        val = self._data
        for key in keys:
            if isinstance(val, dict):
                if key not in val:
                    return None
                val = val[key]
            elif isinstance(val, list):
                if isinstance(key, int):
                    if key < 0 or key >= len(val):
                        return None
                    val = val[key]
                elif val and isinstance(val[0], dict):
                    found = [v for v in val if v.get('name') == key]
                    if not found:
                        found = [v for v in val if key in v.get('name', '')]
                    if not found:
                        return None
                    val = found[0]
                else:
                    return None
            else:
                return val
        return val

    def set(self, value, *keys):
        if len(keys) < 2:
            return False

        # Update parsed data
        parent = self._data
        for key in keys[:-1]:
            if isinstance(parent, dict):
                if key not in parent:
                    return False
                parent = parent[key]
            elif isinstance(parent, list):
                if isinstance(key, int):
                    if key < 0 or key >= len(parent):
                        return False
                    parent = parent[key]
                elif parent and isinstance(parent[0], dict):
                    found = [v for v in parent if v.get('name') == key or key in v.get('name', '')]
                    if not found:
                        return False
                    parent = found[0]
                else:
                    return False
            else:
                return False

        leaf_key = keys[-1]
        if not isinstance(parent, dict) or leaf_key not in parent:
            return False
        old = parent[leaf_key]
        if old == value:
            return False
        parent[leaf_key] = value

        # Update raw line
        line_idx = self._find_line_idx(keys)
        if line_idx is not None:
            old_line = self._raw_lines[line_idx]
            m = _KV_RE.match(old_line)
            if m:
                indent = m.group('indent')
                new_line = f"{indent}{leaf_key} = {format_value(value)}"
                self._raw_lines[line_idx] = new_line
        self._modified = True
        return True

    def get_default(self, *keys):
        cfg = AES67Config()
        try:
            cfg.load(self.default_path)
        except (ConfigNotFoundError, FileNotFoundError):
            return None
        return cfg.get(*keys)

    def reset_to_default(self):
        if not os.path.exists(self.default_path):
            return False
        shutil.copy(self.default_path, self._loaded_path)
        self._modified = True
        self.load(self._loaded_path)
        return True

    def get_module_index(self, name):
        modules = self._data.get('context.modules', [])
        for idx, mod in enumerate(modules):
            if isinstance(mod, dict) and mod.get('name') == name:
                return idx
        return -1

    def add_rtp_sink(self, template_index=-1):
        modules = self._data.get('context.modules', [])
        if template_index < 0:
            template_index = self.get_module_index('libpipewire-module-rtp-sink')
        if template_index < 0:
            return -1

        template = modules[template_index]
        new_mod = deepcopy(template)
        new_mod['args']['destination.ip'] = '239.69.150.243'
        new_mod['args']['destination.port'] = 5004
        new_mod['args']['sess.name'] = '"PipeWire RTP stream"'
        modules.append(new_mod)

        # Find insertion point in raw_lines
        # Insert after the closing } of the last module
        insert_at = self._find_module_line_end(len(modules) - 2)
        if insert_at is not None:
            insert_at += 1  # after the closing line
        else:
            insert_at = len(self._raw_lines) - 1

        serialized = self._serialize_module(new_mod)
        for line in reversed(serialized):
            self._raw_lines.insert(insert_at, line)

        self._modified = True
        return len(modules) - 1

    def remove_rtp_sink(self, index):
        modules = self._data.get('context.modules', [])
        if index < 0 or index >= len(modules):
            return False
        target = modules[index]
        if not isinstance(target, dict) or target.get('name') != 'libpipewire-module-rtp-sink':
            return False
        rtp_count = sum(1 for m in modules
                        if isinstance(m, dict) and m.get('name') == 'libpipewire-module-rtp-sink')
        if rtp_count <= 1:
            return False

        # Find line range and remove
        start = self._find_module_line_start(index)
        end = self._find_module_line_end(index)
        if start is not None and end is not None:
            del self._raw_lines[start:end + 1]

        del modules[index]
        self._modified = True
        return True

    def get_loaded_path(self):
        return self._loaded_path

    def is_modified(self):
        return self._modified

    # ─── Parsing ─────────────────────────────────────────────────

    def _parse(self):
        """Parse raw_lines into _data and build _line_map."""
        self._data = {}
        self._line_map = []
        lines = self._raw_lines
        i = 0
        while i < len(lines):
            line = lines[i]
            m = _SECTION_RE.match(line)
            if m:
                key = m.group('key')
                brace = m.group('brace')
                if brace == '{':
                    content, end_idx = self._parse_braced_block(lines, i + 1,
                                                               key)
                    if isinstance(content, list) and len(content) == 1 and isinstance(content[0], dict):
                        self._data[key] = content[0]
                    else:
                        self._data[key] = content
                    i = end_idx + 1
                else:
                    content, end_idx = self._parse_bracket_block(lines, i + 1, key)
                    self._data[key] = content
                    i = end_idx + 1
            else:
                i += 1

    def _parse_braced_block(self, lines, start_idx, parent_path):
        """Parse { } block. Returns (data, end_idx).
        Records entries in _line_map as 'parent_path.key' for each kv_pair.
        """
        result = {}
        i = start_idx
        depth = 1

        # Inline content after { on the previous line
        if start_idx - 1 >= 0:
            prev = lines[start_idx - 1]
            bp = prev.find('{')
            if bp >= 0:
                after = prev[bp + 1:].strip()
                if after and not after.startswith('}') and not after.startswith('#'):
                    self._parse_inline_kv(after, result)

        while i < len(lines) and depth > 0:
            line = lines[i]
            stripped = line.strip()

            if not stripped or stripped.startswith('#'):
                i += 1
                continue

            # Opening brace nested
            if '{' in stripped and not stripped.startswith('#'):
                # But might be key = { block or just { ... }
                # Only count if not already handled as block_start
                pass

            # Closing brace
            close_test = stripped.rstrip(',').strip()
            if close_test == '}':
                depth -= 1
                if depth == 0:
                    return result, i
                i += 1
                continue

            # key = { ... } sub-block
            m = _BLOCK_START_RE.match(line)
            if m and m.group('brace') == '{':
                k = m.group('key')
                sub_path = parent_path + '.' + k if parent_path else k
                sub, end_idx = self._parse_braced_block(lines, i + 1, sub_path)
                result[k] = sub
                i = end_idx + 1
                continue

            # key = [ ... ] sub-array
            m = _BLOCK_START_RE.match(line)
            if m and m.group('brace') == '[':
                k = m.group('key')
                sub_path = parent_path + '.' + k if parent_path else k
                sub, end_idx = self._parse_bracket_block(lines, i + 1, sub_path)
                result[k] = sub
                i = end_idx + 1
                continue

            # key = value
            m = _KV_RE.match(line)
            if m:
                k = m.group('key')
                v = parse_value(m.group('value'))
                result[k] = v
                full_path = parent_path + '.' + k if parent_path else k
                self._line_map.append((full_path, i))
                i += 1
                continue

            i += 1

        return result, i

    def _parse_bracket_block(self, lines, start_idx, parent_path):
        """Parse [ ] block. Returns (list, end_idx)."""
        result = []
        i = start_idx
        depth = 1

        while i < len(lines) and depth > 0:
            line = lines[i]
            stripped = line.strip()

            if not stripped or stripped.startswith('#'):
                i += 1
                continue

            # Closing bracket
            close_test = stripped.rstrip(',').strip()
            if close_test == ']':
                depth -= 1
                if depth == 0:
                    return result, i
                i += 1
                continue

            # Object { ... } inside array
            if stripped.startswith('{'):
                if '}' in stripped:
                    # Single-line { name = xxx }
                    obj = self._parse_single_line_object(stripped)
                    obj_idx = len(result)
                    # Record name -> index mapping for path tracking
                    if 'name' in obj or 'factory' in obj:
                        self._line_map.append((f'{parent_path}[{obj_idx}]', i))
                    result.append(obj)
                    i += 1
                else:
                    # Multi-line object
                    obj_idx = len(result)
                    obj_path = f"{parent_path}[{obj_idx}]"
                    inner, end_idx = self._parse_braced_block(lines, i + 1, obj_path)
                    result.append(inner)
                    i = end_idx + 1
                continue

            # Simple value
            result.append(parse_value(stripped))
            i += 1

        return result, i

    def _parse_single_line_object(self, text):
        result = {}
        inner = text.strip()
        if inner.startswith('{'):
            inner = inner[1:]
        inner = inner.rstrip(',').rstrip('}')
        self._parse_inline_kv(inner, result)
        return result

    def _parse_inline_kv(self, text, target):
        pat = re.compile(r'([\w.\-]+)\s*=\s*("[^"]*"|\[[^\]]*\]|\S+)')
        pos = 0
        while pos < len(text):
            m = pat.search(text, pos)
            if not m:
                break
            k = m.group(1)
            v_text = m.group(2).rstrip(',')
            target[k] = parse_value(v_text)
            pos = m.end()

    # ─── Line lookup ─────────────────────────────────────────────

    def _find_line_idx(self, keys):
        """Find raw line index by building a path from keys and
        looking it up in _line_map.
        """
        if len(keys) < 2:
            return None
        section = keys[0]

        if section in ('context.properties', 'context.spa-libs'):
            target_path = '.'.join(keys)
            for path, idx in self._line_map:
                if path == target_path:
                    return idx
            return None

        if section == 'context.objects':
            obj_id = keys[1]
            obj_idx = obj_id if isinstance(obj_id, int) else None
            if obj_idx is None:
                # Find by factory name
                objs = self._data.get('context.objects', [])
                for i, o in enumerate(objs):
                    if isinstance(o, dict) and o.get('factory') == obj_id:
                        obj_idx = i
                        break
            if obj_idx is None:
                return None
            target_path = f'context.objects[{obj_idx}].' + '.'.join(
                str(k) for k in keys[2:])
            for path, idx in self._line_map:
                if path == target_path:
                    return idx
            return None

        if section == 'context.modules':
            module_id = keys[1]
            mod_idx = module_id if isinstance(module_id, int) else None
            if mod_idx is None:
                mod_idx = self.get_module_index(module_id)
            if mod_idx < 0:
                return None
            target_path = f'context.modules[{mod_idx}].' + '.'.join(
                str(k) for k in keys[2:])
            for path, idx in self._line_map:
                if path == target_path:
                    return idx
            return None

        return None

    def _find_module_line_start(self, index):
        modules = self._data.get('context.modules', [])
        if index < 0 or index >= len(modules):
            return None
        target_name = modules[index].get('name', '')
        count = 0
        depth = 0
        for idx, line in enumerate(self._raw_lines):
            stripped = line.strip()
            if stripped.startswith('{'):
                depth += 1
                if depth == 1:
                    if target_name in stripped:
                        if count == index:
                            return idx
                        count += 1
            if stripped.startswith('}') or stripped.rstrip(',').startswith('}'):
                depth -= 1
        return None

    def _find_module_line_end(self, index):
        start = self._find_module_line_start(index)
        if start is None:
            return None
        depth = 0
        for idx in range(start, len(self._raw_lines)):
            stripped = self._raw_lines[idx].strip()
            if stripped.startswith('{'):
                depth += 1
            elif stripped.startswith('}') or stripped.rstrip(',').startswith('}'):
                depth -= 1
                if depth == 0:
                    return idx
        return None

    # ─── Module serialization (for add_rtp_sink) ─────────────────

    def _serialize_module(self, mod):
        name = mod.get('name', '')
        lines = []
        ind = '    '
        lines.append(f'{ind}{{ name = {name}')
        args = mod.get('args', {})
        if args:
            lines.append(f'{ind}    args = {{')
            for k, v in args.items():
                if k == 'stream.props':
                    lines.append(f'{ind}        stream.props = {{')
                    if isinstance(v, dict):
                        for pk, pv in v.items():
                            lines.append(f'{ind}            {pk} = {format_value(pv)}')
                    lines.append(f'{ind}        }}')
                elif k == 'stream.rules':
                    lines.append(f'{ind}        stream.rules = [')
                    if isinstance(v, list):
                        for rule in v:
                            lines += self._serialize_rule(rule, ind + '        ')
                    lines.append(f'{ind}        ]')
                else:
                    lines.append(f'{ind}        {k} = {format_value(v)}')
            lines.append(f'{ind}    }}')
        flags = mod.get('flags', [])
        if flags:
            flags_str = ' '.join(str(f) for f in flags)
            lines.append(f'{ind}    flags = [ {flags_str} ]')
        lines.append(f'{ind}}},')
        return lines

    def _serialize_rule(self, rule, indent):
        lines = []
        lines.append(f'{indent}{{')
        indent2 = indent + '    '

        matches = rule.get('matches', [])
        if matches:
            lines.append(f'{indent2}matches = [')
            for m in matches:
                indent3 = indent2 + '    '
                lines.append(f'{indent3}{{')
                for mk, mv in m.items():
                    lines.append(f'{indent3}    {mk} = {format_value(mv)}')
                lines.append(f'{indent3}}},')
            lines.append(f'{indent2}]')

        actions = rule.get('actions', {})
        if actions:
            lines.append(f'{indent2}actions = {{')
            for ak, av in actions.items():
                indent3 = indent2 + '    '
                if isinstance(av, dict) and av:
                    lines.append(f'{indent3}{ak} = {{')
                    for ak2, av2 in av.items():
                        lines.append(f'{indent3}    {ak2} = {format_value(av2)}')
                    lines.append(f'{indent3}}}')
                else:
                    lines.append(f'{indent3}{ak} = {{}}')
            lines.append(f'{indent2}}}')

        lines.append(f'{indent}}},')
        return lines
