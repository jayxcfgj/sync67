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
    r'^(?P<indent>\s*)(?P<key>context\.[\w\-]+)\s*=\s*(?P<brace>[\[\{])\s*$'
)
_KV_RE = re.compile(
    r'^(?P<indent>\s*)(?P<key>[\w.\-*]+)\s*=\s*(?P<value>(?!\s*[\{\[]).+?)\s*,?\s*$'
)
_BLOCK_START_RE = re.compile(
    r'^(?P<indent>\s*)(?P<key>[\w.\-*]+)\s*=\s*(?P<brace>[\[\{])\s*$'
)
_INLINE_ARRAY_RE = re.compile(
    r'^(?P<indent>\s*)(?P<key>[\w.\-*]+)\s*=\s*(?P<values>\[.+?\])\s*,?\s*$'
)


def parse_value(val_str):
    val_str = val_str.strip()
    if not val_str.startswith('"'):
        if '#' in val_str:
            val_str = val_str.split('#')[0].strip()
        if ';' in val_str:
            val_str = val_str.split(';')[0].strip()
    val_str = val_str.rstrip(',')
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


def _parse_array_content(val_str):
    """Parse ["CH1", "CH2"] into ['"CH1"', '"CH2"'] (quote-embedded items)."""
    val_str = val_str.strip()
    if val_str.startswith('[') and val_str.endswith(']'):
        inner = val_str[1:-1].strip()
        if not inner:
            return []
        items = []
        current = []
        in_quote = False
        for ch in inner:
            if ch == '"':
                in_quote = not in_quote
            if ch == ',' and not in_quote:
                items.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)
        if current:
            items.append(''.join(current).strip())
        return [parse_value(item) for item in items if item]
    return parse_value(val_str)


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
    # Quote strings that contain spaces or special characters
    val = str(value)
    if ' ' in val or '"' in val or val.startswith('#') or '=' in val or '.' in val:
        if not val.startswith('"'):
            val = '"' + val.replace('"', '\\"') + '"'
    return val


def _join_path(prefix, keys):
    """Join a key tuple into _line_map path notation.

    Integer keys become '[i]' (list indices), string keys are
    dot-separated: ('args', 'stream.rules', 0, 'actions')
    -> 'args.stream.rules[0].actions'
    """
    out = prefix
    for k in keys:
        if isinstance(k, int):
            out += f'[{k}]'
        elif out:
            out += '.' + str(k)
        else:
            out = str(k)
    return out


class AES67Config:
    def __init__(self):
        self.default_path = "/usr/share/pipewire/pipewire-aes67.conf"

        self._raw_lines = []     # list of str (preserved from original)
        self._data = {}          # structured parsed data
        self._line_map = []      # list of (path_tuple, line_idx)
        self._obj_ranges = {}    # list of [path] -> [(start_line, end_line)]
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
        if not self._data:
            raise ConfigParseError(
                f"Could not parse any sections in {self._loaded_path}"
            )

    def save(self, path=None, backup=True):
        path = str(path or self._loaded_path)
        if not path:
            raise ConfigWriteError("No path specified")
        try:
            if backup and os.path.exists(path):
                shutil.copy(path, path + '.bak')
        except OSError:
            pass  # non-critical, continue saving
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            text = '\n'.join(self._raw_lines)
            if not text.endswith('\n'):
                text += '\n'
            with open(path, 'w', encoding='utf-8') as f:
                f.write(text)
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
                    found = [v for v in val if isinstance(v, dict) and v.get('name') == key]
                    if not found:
                        found = [v for v in val if isinstance(v, dict) and key in v.get('name', '')]
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
                    found = [v for v in parent if isinstance(v, dict) and (v.get('name') == key or key in v.get('name', ''))]
                    if not found:
                        return False
                    parent = found[0]
                else:
                    return False
            else:
                return False

        leaf_key = keys[-1]
        if not isinstance(parent, dict):
            return False

        is_new = leaf_key not in parent
        if not is_new and parent[leaf_key] == value:
            # already in the desired state – not an error
            return True

        parent[leaf_key] = value

        # Update raw line
        line_idx = self._find_line_idx(keys)
        if line_idx is not None:
            old_line = self._raw_lines[line_idx]
            m = _KV_RE.match(old_line)
            if m:
                indent = m.group('indent')
                new_line = (f"{indent}{leaf_key} = "
                            f"{self._format_like(m.group('value'), value)}")
                self._raw_lines[line_idx] = new_line
            else:
                m2 = _INLINE_ARRAY_RE.match(old_line)
                if m2:
                    indent = m2.group('indent')
                    new_line = (f"{indent}{leaf_key} = "
                                f"{self._format_like(m2.group('values'), value)}")
                    self._raw_lines[line_idx] = new_line
        elif is_new and len(keys) >= 3:
            # Key didn't exist in raw_lines – insert it inside the args block
            section = keys[0]
            obj_spec = keys[1]
            if isinstance(obj_spec, int):
                # Resolve index to factory/name string for raw-line scanning
                if section == 'context.objects':
                    objs = self._data.get('context.objects', [])
                    for i, o in enumerate(objs):
                        if isinstance(o, dict) and o.get('factory') and i == obj_spec:
                            obj_spec = o['factory']
                            break
                elif section == 'context.modules':
                    mods = self._data.get('context.modules', [])
                    for i, m in enumerate(mods):
                        if isinstance(m, dict) and m.get('name') and i == obj_spec:
                            obj_spec = m['name']
                            break
            if isinstance(obj_spec, str) and section in ('context.modules', 'context.objects'):
                insert_at = self._find_sub_block_end(section, obj_spec, 'args')
                if insert_at is not None:
                    # Determine indent from the args = { line
                    indent = '            '
                    for lookback in range(insert_at - 1, -1, -1):
                        raw = self._raw_lines[lookback]
                        if 'args = {' in raw:
                            args_indent = raw[:len(raw) - len(raw.lstrip())]
                            indent = args_indent + '    '
                            break
                    new_line = f"{indent}{leaf_key} = {format_value(value)}"
                    self._raw_lines.insert(insert_at, new_line)
                    # keep _line_map in sync – otherwise later
                    # comment_key/uncomment_key hit shifted lines
                    self._parse()
        self._modified = True
        return True

    @staticmethod
    def _format_like(old_raw, value):
        """format_value(), but keep the quoting style of the existing line."""
        formatted = format_value(value)
        if (old_raw or '').strip().startswith('"') \
                and not formatted.startswith('"'):
            formatted = '"' + formatted + '"'
        return formatted

    def _find_line_idx_raw(self, keys):
        """Find raw line index for key path, including commented lines.

        Tracks brace depth and counts module/object instances to resolve
        integer indices. Unlike _find_line_idx, this does NOT skip
        commented lines.
        """
        if len(keys) < 3:
            return None
        section = keys[0]
        obj_key = keys[1]
        target = keys[-1]
        if section not in ('context.modules', 'context.objects'):
            return None
        id_field = 'name' if section == 'context.modules' else 'factory'
        obj_idx = obj_key if isinstance(obj_key, int) else None
        in_section = False
        in_target = False
        in_args = False
        depth = 0
        obj_count = -1
        for idx, line in enumerate(self._raw_lines):
            stripped = line.strip()
            content = stripped.lstrip('#').lstrip()
            if not content:
                continue
            if not in_section:
                pat = f'{section} = ['
                if content.startswith(pat):
                    in_section = True
                continue
            opens = content.count('{')
            closes = content.count('}')
            if opens > 0 and depth == 0:
                obj_count += 1
            depth += opens - closes
            if opens > 0 and depth > 0 and depth <= opens:
                in_target = False
                in_args = False
                if obj_idx is None:
                    in_target = f'{id_field} = {obj_key}' in content
                else:
                    in_target = obj_count == obj_idx
            if in_target:
                bm = _BLOCK_START_RE.match(content)
                if bm and bm.group('key') == 'args':
                    in_args = True
            if in_target and in_args:
                km = _KV_RE.match(content)
                if km and km.group('key') == target:
                    return idx
                im = _INLINE_ARRAY_RE.match(content)
                if im and im.group('key') == target:
                    return idx
            if depth == 0 and in_target:
                in_target = False
                in_args = False
                if in_section:
                    pass  # end of this object/module
        return None

    def get_raw_value(self, *keys):
        """Read a key's value from _raw_lines even if commented.

        Returns the parsed value (int/float/bool/str) or None if not found.
        Unlike get(), this extracts from commented lines too.
        """
        if len(keys) < 2:
            return None
        line_idx = self._find_line_idx(keys)
        if line_idx is None:
            line_idx = self._find_line_idx_raw(keys)
        if line_idx is None:
            return None
        line = self._raw_lines[line_idx]
        stripped = line.strip().lstrip('#').lstrip()
        m = _KV_RE.match(stripped)
        if not m:
            return None
        val_str = m.group('value')
        if val_str is None:
            return None
        val_str = val_str.rstrip(',')
        try:
            return parse_value(val_str)
        except (ValueError, TypeError):
            return val_str

    def comment_key(self, *keys):
        """Comment out a key's line in _raw_lines by prepending '# '.

        Returns True if a line was commented, False if not found/already commented.
        """
        if len(keys) < 2:
            return False
        line_idx = self._find_line_idx(keys)
        if line_idx is None:
            line_idx = self._find_line_idx_raw(keys)
        if line_idx is None:
            return False
        line = self._raw_lines[line_idx]
        stripped = line.strip()
        if stripped.startswith('#'):
            return False
        indent = line[:len(line) - len(line.lstrip())]
        self._raw_lines[line_idx] = f'{indent}# {stripped}'
        # keep _data/_line_map in sync – a later set() would otherwise
        # treat the key as missing and insert a duplicate line
        self._parse()
        self._modified = True
        return True

    def uncomment_key(self, *keys):
        """Remove leading '# ' from a key's line in _raw_lines.

        Returns True if a line was uncommented, False if not found/already active.
        """
        if len(keys) < 2:
            return False
        line_idx = self._find_line_idx(keys)
        if line_idx is None:
            # commented keys are not in _line_map
            line_idx = self._find_line_idx_raw(keys)
        if line_idx is None:
            return False
        line = self._raw_lines[line_idx]
        stripped = line.strip()
        if not stripped.startswith('#'):
            return False
        uncommented = stripped.lstrip('#').strip()
        indent = line[:len(line) - len(line.lstrip())]
        self._raw_lines[line_idx] = f'{indent}{uncommented}'
        # re-register in _line_map so the following set() rewrites this
        # line in place instead of appending a duplicate
        self._parse()
        self._modified = True
        return True

    def get_default(self, *keys):
        cfg = AES67Config()
        try:
            cfg.load(self.default_path)
        except (ConfigNotFoundError, FileNotFoundError):
            return None
        return cfg.get(*keys)

    def reset_to_default(self, iface=None):
        if not os.path.exists(self.default_path):
            return False
        if not self._loaded_path or self._loaded_path == self.default_path:
            return False
        try:
            # backup the user config we are about to replace
            if os.path.exists(self._loaded_path):
                shutil.copy(self._loaded_path, self._loaded_path + '.bak')
            shutil.copy(self.default_path, self._loaded_path)
        except (OSError, PermissionError) as e:
            raise ConfigWriteError(f"Konnte Default nicht kopieren: {e}") from e
        self._modified = True
        self.load(self._loaded_path)
        self.apply_sync67_defaults(iface)
        # write the defaults to disk (backup already taken above)
        self.save(backup=False)
        return True

    # ─── sync67 documentation defaults ──────────────────────────

    # (id_field, object name, {key: value template})
    # '{iface}' templates are skipped when no interface is given.
    _SYNC67_DEFAULT_RULES = (
        ('factory', 'spa-node-factory', {
            'resync.ms': '48',
            'max_resync': '4',
            'clock.interface': '"{iface}"',
        }),
        ('name', 'libpipewire-module-rt', {
            'rt.prio': '83',
            'rlimits.enabled': 'true',
        }),
        ('name', 'libpipewire-module-rtp-sink', {
            'sess.max-ptime': '4',
            'sess.latency.msec': '12',
            'local.ifname': '{iface}',
        }),
        ('name', 'libpipewire-module-rtp-sap', {
            'sess.latency.msec': '12',
            'local.ifname': '{iface}',
        }),
    )

    def apply_sync67_defaults(self, iface=None):
        """Set the sync67 documentation defaults in _raw_lines.

        Only for freshly copied stock configs (reset / first copy) –
        existing user configs are never touched.
        Returns True if something changed.
        """
        changed = False
        for id_field, obj_name, values in self._SYNC67_DEFAULT_RULES:
            for key, tpl in values.items():
                if '{iface}' in tpl:
                    if not iface:
                        continue
                    value = tpl.format(iface=iface)
                else:
                    value = tpl
                changed |= self._apply_default_value(id_field, obj_name,
                                                     key, value)
        if changed:
            self._parse()
            self._modified = True
        return changed

    def _apply_default_value(self, id_field, obj_name, key, value):
        """Set one key inside every object/module matching obj_name.

        Rewrites the raw line (uncommenting it if needed) or inserts the
        key into the args block when it does not exist yet.
        """
        changed = False
        for start, end in self._find_object_ranges(id_field, obj_name):
            line_idx = self._find_key_line(start, end, key)
            if line_idx is not None:
                line = self._raw_lines[line_idx]
                indent = line[:len(line) - len(line.lstrip())]
                was_commented = line.strip().startswith('#')
                content = line.strip().lstrip('#').strip()
                m = re.match(r'^(?P<head>\s*[\w.\-*]+\s*=\s*)'
                             r'(?P<val>.*?)(?P<comma>,?)\s*$', content)
                if not m:
                    continue
                new_content = m.group('head') + value + m.group('comma')
                if content == new_content and not was_commented:
                    continue
                # always write an active line (stock ships rt.prio commented)
                self._raw_lines[line_idx] = indent + new_content
                changed = True
            else:
                insert_at = self._find_args_close(start, end)
                if insert_at is None:
                    continue
                indent = self._detect_indent(start, end)
                self._raw_lines.insert(insert_at, f'{indent}{key} = {value}')
                changed = True
        return changed

    def _find_object_ranges(self, id_field, obj_name):
        """Yield (start, end) line ranges of all matching objects/modules."""
        ranges = []
        # word-boundary match: 'libpipewire-module-rt' must not match
        # 'libpipewire-module-rtp-sink'
        needle = re.compile(
            rf'{id_field}\s*=\s*{re.escape(obj_name)}(?![\w.-])')
        depth = 0
        start = None
        for i, line in enumerate(self._raw_lines):
            stripped = line.strip()
            if start is None:
                if '{' in stripped and needle.search(stripped):
                    depth = stripped.count('{') - stripped.count('}')
                    if depth <= 0:
                        ranges.append((i, i))  # single-line object
                    else:
                        start = i
                continue
            depth += stripped.count('{') - stripped.count('}')
            if depth <= 0:
                ranges.append((start, i))
                start = None
        return ranges

    def _find_key_line(self, start, end, key):
        """First raw line with 'key =' inside [start, end] (comments allowed)."""
        for i in range(start, end + 1):
            content = self._raw_lines[i].strip()
            if not content:
                continue
            content = content.lstrip('#').strip()
            m = _KV_RE.match(content)
            if m and m.group('key') == key:
                return i
        return None

    def _find_args_close(self, start, end):
        """Line index of the '}' closing the args block, or None."""
        in_args = False
        depth = 0
        for i in range(start, end + 1):
            stripped = self._raw_lines[i].strip()
            if not in_args:
                m = _BLOCK_START_RE.match(stripped)
                if m and m.group('key') == 'args' and m.group('brace') == '{':
                    in_args = True
                    depth = 1
                continue
            depth += stripped.count('{') - stripped.count('}')
            if depth <= 0:
                return i
        return None

    def _detect_indent(self, start, end):
        """Indent used by existing key lines inside the object (fallback 12)."""
        for i in range(start, end + 1):
            m = _KV_RE.match(self._raw_lines[i])
            if m:
                return m.group('indent')
        return '            '

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
        self._make_sink_identity(new_mod, modules)

        # The new block must land INSIDE context.modules, i.e. directly in
        # front of the closing "]" – never at the end of the file.
        insert_at = self._find_section_close('context.modules')
        if insert_at is None:
            return -1

        serialized = self._serialize_module(new_mod)
        for line in reversed(serialized):
            self._raw_lines.insert(insert_at, line)

        # re-parse: _data/_line_map/_obj_ranges must know the new module,
        # otherwise set() silently drops edits and remove() loses lines
        self._parse()
        self._modified = True
        return len(self._data.get('context.modules', [])) - 1

    @staticmethod
    def _unquote(value):
        return str(value).strip('"') if value is not None else ''

    def _make_sink_identity(self, new_mod, modules):
        """Unique node.name / sess.name / multicast IP for a copied sink.

        The stock config explicitly asks for this when creating multiple
        sinks: identical node names collide in PipeWire, identical
        destination addresses merge two streams into one flow.
        """
        existing = [m for m in modules
                    if isinstance(m, dict)
                    and m.get('name') == 'libpipewire-module-rtp-sink']
        args = new_mod.setdefault('args', {})
        props = args.setdefault('stream.props', {})

        used_names = {self._unquote(
            (m.get('args', {}).get('stream.props') or {}).get('node.name'))
            for m in existing}
        used_sess = {self._unquote(m.get('args', {}).get('sess.name'))
                     for m in existing}
        used_ips = {self._unquote(m.get('args', {}).get('destination.ip'))
                    for m in existing}

        n = 2
        while f'rtp-sink{n}' in used_names:
            n += 1
        props['node.name'] = f'"rtp-sink{n}"'

        m = 2
        while f'PipeWire RTP stream {m}' in used_sess:
            m += 1
        args['sess.name'] = f'"PipeWire RTP stream {m}"'

        # unquoted like the stock config (SPA accepts plain addresses)
        args['destination.ip'] = self._next_free_ip(
            args.get('destination.ip'), used_ips)
        args.setdefault('destination.port', 5004)

    @staticmethod
    def _next_free_ip(base, used):
        """First unused multicast address in the same /16 as base.

        AES67 wants administratively scoped 239.x.x.x, Dante-compatible
        streams sit in 239.69.x.x – the second octet of base is kept.
        """
        parts = str(base or '').strip('"').split('.')
        try:
            net = (parts[0], parts[1])
            third_start, fourth_start = int(parts[2]), int(parts[3])
        except (IndexError, ValueError):
            net, third_start, fourth_start = ('239', '69'), 150, 243
        for third in range(third_start, 256):
            start = fourth_start if third == third_start else 1
            for fourth in range(start, 255):
                cand = f'{net[0]}.{net[1]}.{third}.{fourth}'
                if cand not in used:
                    return cand
        return f'{net[0]}.{net[1]}.{third_start}.{fourth_start}'

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

        start = self._find_module_line_start(index)
        end = self._find_module_line_end(index)
        if start is None or end is None:
            return False

        del self._raw_lines[start:end + 1]
        self._parse()
        self._modified = True
        return True

    def get_loaded_path(self):
        return self._loaded_path

    def is_modified(self):
        return self._modified

    def _find_block_range(self, target_key):
        """Findet Start/End-Zeilen eines Blocks anhand eines Key-Worts
        (z.B. 'stream.rules'). Scannt _raw_lines nach key = [  oder key = {.
        Returns (start, end) or (None, None).
        """
        for start, line in enumerate(self._raw_lines):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            # Match: key = [  or key = {
            pat = re.compile(r'^\s*' + re.escape(target_key) + r'\s*=\s*[\[\{]')
            if pat.match(line):
                brace_char = stripped.rstrip()[-1]
                close_char = '}' if brace_char == '{' else ']'
                depth = 1
                for end in range(start + 1, len(self._raw_lines)):
                    s = self._raw_lines[end].strip()
                    opens = s.count(brace_char)
                    closes = s.count(close_char)
                    depth += opens - closes
                    if depth <= 0:
                        return start, end
        return None, None

    def get_raw_block(self, *keys):
        """Extracts raw text for a nested block
        (z.B. stream.rules) aus _raw_lines.
        Returns (start_idx, end_idx, text) or (None, None, None).
        """
        if len(keys) < 2:
            return None, None, None
        target_key = keys[-1]
        start, end = self._find_block_range(target_key)
        if start is None:
            return None, None, None
        lines = self._raw_lines[start:end + 1]
        return start, end, '\n'.join(lines)

    def set_raw_block(self, text, *keys):
        """Replaces raw text for a block (e.g. stream.rules).
        text muss den kompletten Block inkl. Header-Zeile enthalten.
        """
        if len(keys) < 2:
            return False
        target_key = keys[-1]
        start, end = self._find_block_range(target_key)
        if start is None:
            return False
        new_lines = text.split('\n')
        del self._raw_lines[start:end + 1]
        for i, line in enumerate(new_lines):
            self._raw_lines.insert(start + i, line)
        self._modified = True
        return True

    # ─── Parsing ─────────────────────────────────────────────────

    def _parse(self):
        """Parse raw_lines into _data and build _line_map."""
        self._data = {}
        self._line_map = []
        self._obj_ranges = {}
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
        Depth is tracked via ALL { } chars; sub-blocks (key = {...}) are
        handled recursively so their braces don't affect depth here.
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

            # Count ALL braces on this line (used only for unclassified lines)
            opens = stripped.count('{')
            closes = stripped.count('}')

            # Try block-start first (key = { … } sub-block)
            m = _BLOCK_START_RE.match(line)
            if m and m.group('brace') == '{':
                k = m.group('key')
                sub_path = parent_path + '.' + k if parent_path else k
                sub, end_idx = self._parse_braced_block(lines, i + 1, sub_path)
                result[k] = sub
                # sub-block consumed its own braces; do NOT count them here
                i = end_idx + 1
                continue

            # Try array-start (key = [ … ] sub-array)
            m = _BLOCK_START_RE.match(line)
            if m and m.group('brace') == '[':
                k = m.group('key')
                sub_path = parent_path + '.' + k if parent_path else k
                sub, end_idx = self._parse_bracket_block(lines, i + 1, sub_path)
                result[k] = sub
                i = end_idx + 1
                continue

            # Try single-line array (key = [ ... ])
            m = _INLINE_ARRAY_RE.match(line)
            if m:
                k = m.group('key')
                result[k] = _parse_array_content(m.group('values'))
                full_path = parent_path + '.' + k if parent_path else k
                self._line_map.append((full_path, i))
                i += 1
                continue

            # Try key = value
            m = _KV_RE.match(line)
            if m:
                k = m.group('key')
                v = parse_value(m.group('value'))
                result[k] = v
                full_path = parent_path + '.' + k if parent_path else k
                self._line_map.append((full_path, i))
                i += 1
                continue

            # Unclassified line: adjust depth by all braces present
            depth += opens - closes
            if depth <= 0:
                return result, i
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
                    self._record_range(parent_path, i, i)
                    i += 1
                else:
                    # Multi-line object
                    obj_idx = len(result)
                    obj_path = f"{parent_path}[{obj_idx}]"
                    inner, end_idx = self._parse_braced_block(lines, i + 1, obj_path)
                    result.append(inner)
                    self._record_range(parent_path, i, end_idx)
                    i = end_idx + 1
                continue

            # Simple value
            result.append(parse_value(stripped))
            self._record_range(parent_path, i, i)
            i += 1

        return result, i

    def _record_range(self, parent_path, start, end):
        """Remember the raw line span of one array entry (index aligned)."""
        self._obj_ranges.setdefault(parent_path, []).append((start, end))

    def _parse_single_line_object(self, text):
        result = {}
        inner = text.strip()
        if inner.startswith('{'):
            inner = inner[1:]
        inner = inner.rstrip(',').rstrip('}')
        self._parse_inline_kv(inner, result)
        return result

    def _parse_inline_kv(self, text, target):
        pat = re.compile(r'([\w.\-*]+)\s*=\s*("[^"]*"|\[[^\]]*\]|\S+)')
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
        """Find raw line index for key path.
        First tries _line_map lookup. If that fails
        (e.g. after add/remove rtp_sink), falls back to a line scan.
        """
        if len(keys) < 2:
            return None
        section = keys[0]

        # ── _line_map lookup ─────────────────────────────────
        if section in ('context.properties', 'context.spa-libs'):
            target_path = _join_path('', keys)
            for path, idx in self._line_map:
                if path == target_path:
                    return idx
            return self._scan_line_idx(keys)

        if section == 'context.objects':
            obj_id = keys[1]
            obj_idx = obj_id if isinstance(obj_id, int) else None
            if obj_idx is None:
                objs = self._data.get('context.objects', [])
                for i, o in enumerate(objs):
                    if isinstance(o, dict) and o.get('factory') == obj_id:
                        obj_idx = i
                        break
            if obj_idx is None:
                return None
            target_path = _join_path(f'context.objects[{obj_idx}]', keys[2:])
            for path, idx in self._line_map:
                if path == target_path:
                    return idx
            return self._scan_line_idx(keys)

        if section == 'context.modules':
            module_id = keys[1]
            mod_idx = module_id if isinstance(module_id, int) else None
            if mod_idx is None:
                mod_idx = self.get_module_index(module_id)
            if mod_idx < 0:
                return None
            target_path = _join_path(f'context.modules[{mod_idx}]', keys[2:])
            for path, idx in self._line_map:
                if path == target_path:
                    return idx
            return self._scan_line_idx(keys)

        return None

    # ─── Fallback line scan (used when _line_map is stale) ────

    def _scan_line_idx(self, keys):
        """Scan _raw_lines for a key path, accounting for brace depth.
        This is a fallback when _line_map doesn't have the entry
        (e.g. after add/remove rtp_sink).
        """
        if len(keys) < 3:
            return None
        section = keys[0]
        obj_id = keys[1]
        target = keys[-1]

        if section not in ('context.modules', 'context.objects'):
            return None

        id_field = 'name' if section == 'context.modules' else 'factory'
        in_target = False
        in_args = False
        depth = 0

        for idx, line in enumerate(self._raw_lines):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            opens = stripped.count('{')
            closes = stripped.count('}')
            depth += opens - closes

            if opens > 0 and depth > 0 and depth <= opens:
                in_target = False
                in_args = False
                # Check if this line opens a new module/object
                if isinstance(obj_id, int):
                    pass  # would need obj counting – skip for simplicity
                else:
                    pat = f'{id_field} = {obj_id}'
                    if pat in stripped:
                        in_target = True

            if in_target and _BLOCK_START_RE.match(line):
                bm = _BLOCK_START_RE.match(line)
                if bm and bm.group('key') == 'args':
                    in_args = True

            if in_target and in_args:
                km = _KV_RE.match(line)
                if km and km.group('key') == target:
                    return idx
                im = _INLINE_ARRAY_RE.match(line)
                if im and im.group('key') == target:
                    return idx

            if depth == 0 and in_target:
                in_target = False
                in_args = False

        return None

    def get_module_range(self, index):
        """(start_line, end_line) of context.modules[index] as recorded
        by _parse(). Returns None when unknown."""
        ranges = self._obj_ranges.get('context.modules', [])
        if 0 <= index < len(ranges):
            return ranges[index]
        return None

    def _find_module_line_start(self, index):
        rng = self.get_module_range(index)
        return rng[0] if rng else None

    def _find_module_line_end(self, index):
        rng = self.get_module_range(index)
        return rng[1] if rng else None

    def _find_section_close(self, section):
        """Line index of the ']' closing a top level [ ... ] section."""
        ranges = self._obj_ranges.get(section, [])
        start = ranges[-1][1] + 1 if ranges else 0
        for i in range(start, len(self._raw_lines)):
            if self._raw_lines[i].strip() == ']':
                return i
        return None

    def _find_sub_block_end(self, section, obj_spec, sub_block='args'):
        """Find line index of the closing '}' of a sub_block (e.g. 'args').

        Scans _raw_lines for a module/object matching obj_spec, finds its
        ``sub_block = {`` and returns the line index of the matching ``}``.
        Returns None if not found.
        """
        id_field = 'name' if section == 'context.modules' else 'factory'
        found_obj = False
        in_sub = False
        depth = 0
        for idx, line in enumerate(self._raw_lines):
            stripped = line.strip()
            if not found_obj:
                if id_field in stripped and obj_spec in stripped and '{' in stripped:
                    found_obj = True
                continue
            if not in_sub:
                if f'{sub_block} = {{' in stripped:
                    in_sub = True
                    depth = 1
                elif stripped.startswith('}'):
                    return None
                continue
            opens = stripped.count('{')
            closes = stripped.count('}')
            depth += opens - closes
            if depth <= 0:
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
