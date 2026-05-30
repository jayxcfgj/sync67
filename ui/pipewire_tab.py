"""PipeWire Tab – Sample Rate, Quantum, pw-top Node-Tabelle mit Tree-Struktur."""

import re
import os
import pwd
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QGridLayout, QProgressBar,
    QTableWidget, QTableWidgetItem, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer, QSettings
from PyQt6.QtGui import QFont, QColor, QBrush

_PW_TOP = '/usr/bin/pw-top'
_PW_META = '/usr/bin/pw-metadata'


def _user_env():
    """Returns an env dict pointing to the actual user (not root),
    so PipeWire socket and D-Bus are reachable."""
    env = os.environ.copy()
    sudo_uid = os.environ.get('SUDO_UID')
    if sudo_uid:
        uid = int(sudo_uid)
        try:
            pw_entry = pwd.getpwuid(uid)
            home = pw_entry.pw_dir
            user = pw_entry.pw_name
        except KeyError:
            uid = 1000
            home = f'/home/{os.environ.get("SUDO_USER", "user")}'
            user = os.environ.get('SUDO_USER', 'user')
        env['HOME'] = home
        env['USER'] = user
        env['LOGNAME'] = user
        env['XDG_RUNTIME_DIR'] = f'/run/user/{uid}'
        env['DBUS_SESSION_BUS_ADDRESS'] = f'unix:path=/run/user/{uid}/bus'
    return env


class PipeWireTab(QWidget):
    def __init__(self):
        super().__init__()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_all)
        self._xruns_offset = 0
        self._current_rate = 0
        self._current_quantum = 0
        self._last_nodes = []
        self.init_ui()
        self._timer.start(2000)
        QTimer.singleShot(300, self._update_all)

    # ─── UI ───────────────────────────────────────────────────

    def init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        # ── Sample Rate ──
        rg = QGroupBox('Sample Rate')
        g = QGridLayout(rg)
        self.rate_combo = QComboBox()
        for v in (48000, 96000, 192000):
            self.rate_combo.addItem(str(v), v)
        self.rate_apply = QPushButton('Apply')
        self.rate_apply.clicked.connect(lambda: self._set_metadata('clock.force-rate', self.rate_combo.currentText()))
        self.rate_reset = QPushButton('Reset')
        self.rate_reset.clicked.connect(lambda: self._set_metadata('clock.force-rate', '0'))
        self.rate_refresh = QPushButton('\u21bb')
        self.rate_refresh.clicked.connect(self._refresh_rate)
        self.rate_status = QLabel('Current: \u2014')
        self.rate_status.setStyleSheet('color: #aaa;')
        g.addWidget(QLabel('Sample Rate:'), 0, 0)
        g.addWidget(self.rate_combo, 0, 1)
        g.addWidget(self.rate_apply, 0, 2)
        g.addWidget(self.rate_reset, 0, 3)
        g.addWidget(self.rate_refresh, 0, 4)
        g.addWidget(self.rate_status, 1, 0, 1, 5)
        layout.addWidget(rg)

        # ── Quantum ──
        qg = QGroupBox('Quantum')
        g = QGridLayout(qg)
        self.q_combo = QComboBox()
        for v in (16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192):
            self.q_combo.addItem(str(v), v)
        self.q_combo.setEditable(True)
        self.q_apply = QPushButton('Apply')
        self.q_apply.clicked.connect(lambda: self._set_metadata('clock.force-quantum', self.q_combo.currentText()))
        self.q_reset = QPushButton('Reset')
        self.q_reset.clicked.connect(lambda: self._set_metadata('clock.force-quantum', '0'))
        self.q_refresh = QPushButton('\u21bb')
        self.q_refresh.clicked.connect(self._refresh_quantum)
        self.q_status = QLabel('Current: \u2014')
        self.q_status.setStyleSheet('color: #aaa;')
        g.addWidget(QLabel('Quantum:'), 0, 0)
        g.addWidget(self.q_combo, 0, 1)
        g.addWidget(self.q_apply, 0, 2)
        g.addWidget(self.q_reset, 0, 3)
        g.addWidget(self.q_refresh, 0, 4)
        g.addWidget(self.q_status, 1, 0, 1, 5)
        layout.addWidget(qg)

        # ── Status ──
        sg = QGroupBox('Status')
        sh = QHBoxLayout(sg)

        lat_v = QVBoxLayout()
        QLabel('Latenz', font=QFont('', 10, weight=75)).setParent(None)
        lat_v.addWidget(QLabel('Latenz'))
        self.latency_label = QLabel('\u2014')
        self.latency_label.setStyleSheet('font-size: 20px; font-weight: bold; color: #e0e0e0;')
        lat_v.addWidget(self.latency_label)
        lat_v.addWidget(QLabel('Quantum [Samples] = Latency [ms] \u00d7 Rate [kHz]'))
        sh.addLayout(lat_v)
        sh.addStretch()

        xv = QVBoxLayout()
        xv.addWidget(QLabel('Xruns'))
        self.xruns_label = QLabel('0')
        self.xruns_label.setStyleSheet('font-size: 20px; font-weight: bold; color: #e0e0e0;')
        self.xruns_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.xruns_label.mousePressEvent = lambda e: self._reset_xruns()
        self.xruns_label.setToolTip('Click to reset')
        xv.addWidget(self.xruns_label)
        xv.addWidget(QLabel('click \u2192 reset'))
        sh.addLayout(xv)
        sh.addStretch()

        dv = QVBoxLayout()
        dv.addWidget(QLabel('DSP Load'))
        self.dsp_label = QLabel('0%')
        self.dsp_label.setStyleSheet('font-size: 16px; font-weight: bold;')
        self.dsp_bar = QProgressBar()
        self.dsp_bar.setRange(0, 100)
        self.dsp_bar.setValue(0)
        self.dsp_bar.setFixedHeight(16)
        self.dsp_bar.setTextVisible(False)
        dv.addWidget(self.dsp_label)
        dv.addWidget(self.dsp_bar)
        sh.addLayout(dv)
        layout.addWidget(sg)

        # ── Tabelle ──
        tg = QGroupBox('Nodes (every 2s)')
        tl = QVBoxLayout(tg)
        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels([
            'ID', 'Status', 'Name', 'Quantum', 'Format', 'CH',
            'DSP', 'Waiting', 'Busy', 'Xruns', 'Rate'
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setShowGrid(False)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #1e1e1e; alternate-background-color: #252525; border: none; font-size: 11px; }
            QHeaderView::section { background-color: #2b2b2b; color: #aaa; padding: 4px 6px; border: none; border-bottom: 1px solid #444; font-weight: bold; font-size: 10px; }
        """)
        tl.addWidget(self.table)
        # Spaltenbreiten speichern/wiederherstellen
        settings = QSettings("sync67", "pipewire_tab")
        saved_widths = settings.value("column_widths")
        if saved_widths:
            widths = [int(w) for w in saved_widths.split(',')]
            for i, w in enumerate(widths):
                if i < self.table.columnCount():
                    self.table.setColumnWidth(i, w)
        self.table.horizontalHeader().sectionResized.connect(self._save_column_widths)
        layout.addWidget(tg)

        scroll.setWidget(content)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    def _save_column_widths(self):
        settings = QSettings("sync67", "pipewire_tab")
        widths = ','.join(str(self.table.columnWidth(i)) for i in range(self.table.columnCount()))
        settings.setValue("column_widths", widths)

    # ─── subprocess Helfer ───────────────────────────────────

    def _run(self, cmd, timeout=5):
        try:
            r = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                env=_user_env()
            )
            out = r.stdout
            if not out.strip():
                out = r.stderr
            return out
        except FileNotFoundError:
            return None
        except Exception:
            return None

    # ─── pw-metadata: Rate ───────────────────────────────────

    def _set_metadata(self, key, value):
        self._run([_PW_META, '-n', 'settings', '0', key, str(value)])
        if 'rate' in key:
            self._refresh_rate()
        else:
            self._refresh_quantum()

    def _refresh_rate(self):
        key = 'clock.force-rate'
        try:
            out = self._run([_PW_META, '-n', 'settings', '0', key])
        except Exception:
            out = None
        if out is None or not isinstance(out, str):
            try:
                r = subprocess.run(
                    [_PW_META, '-n', 'settings', '0', key],
                    capture_output=True, text=True, timeout=5
                )
                out = r.stdout or r.stderr or ''
            except Exception:
                self.rate_status.setText('Current: \u2014 (Error)')
                return
        # Fallback: clock.rate wenn force-rate leer/0
        if not out or 'value:\'0\'' in out or 'value:0' in out:
            fb = self._run([_PW_META, '-n', 'settings', '0', 'clock.rate'])
            if fb and 'value' in fb:
                out = fb
        val = None
        for pat in [
            r"value[=:]'?(\d+)'?",
            r"=\s*(\d+)\s*$",
            r"'(\d+)'",
        ]:
            if not out:
                continue
            m = re.search(pat, out, re.DOTALL)
            if m:
                try:
                    val = int(m.group(1))
                    break
                except ValueError:
                    continue
        if val is not None:
            self._current_rate = val
            if val == 0:
                effective = self._get_effective_rate()
                if effective and effective > 0:
                    self.rate_combo.setCurrentText(str(effective))
                    self.rate_status.setText(f'Effective: {effective} Hz (Metadata: Default)')
                    self._current_rate = effective
                else:
                    self.rate_combo.setCurrentText('')
                    self.rate_status.setText('Current: Default (not set)')
            else:
                idx = self.rate_combo.findData(val)
                if idx >= 0:
                    self.rate_combo.setCurrentIndex(idx)
                else:
                    self.rate_combo.setCurrentText(str(val))
                self.rate_status.setText(f'Current: {val} Hz')
        else:
            preview = (out or '')[:100].strip().replace('\n', ' ')
            self.rate_status.setText(f'No value: {preview}')
        self._update_latency()

    def _refresh_quantum(self):
        key = 'clock.force-quantum'
        try:
            out = self._run([_PW_META, '-n', 'settings', '0', key])
        except Exception:
            out = None
        if out is None or not isinstance(out, str):
            try:
                r = subprocess.run(
                    [_PW_META, '-n', 'settings', '0', key],
                    capture_output=True, text=True, timeout=5
                )
                out = r.stdout or r.stderr or ''
            except Exception:
                self.q_status.setText('Current: \u2014 (Error)')
                return
        # Narrensichere Extraktion: Alle Zahlen finden, die letzte nach 'value:' nehmen
        val = None
        if out:
            # Suche value:'Zahl' oder value=Zahl oder value:Zahl
            m = re.search(r"value[=:]'?(\d+)'?", out)
            if m:
                val = int(m.group(1))
            else:
                # Fallback: letzte Zahl im Output (meist der Wert)
                nums = re.findall(r'(\d+)', out)
                if nums:
                    # Die letzte Zahl vermeidet "metadata 32" und "id:0"
                    val = int(nums[-1])
        if val is not None:
            self._current_quantum = val
            if val == 0:
                # Metadata = 0 (Default) → effektiven Wert aus pw-top holen
                effective = self._get_effective_quantum()
                if effective and effective > 0:
                    self.q_combo.setCurrentText(str(effective))
                    self.q_status.setText(f'Effective: {effective} Samples (Metadata: Default)')
                    self._current_quantum = effective
                else:
                    self.q_combo.setCurrentText('')
                    self.q_status.setText('Current: Default (not set)')
            else:
                idx = self.q_combo.findData(val)
                if idx >= 0:
                    self.q_combo.setCurrentIndex(idx)
                else:
                    self.q_combo.setCurrentText(str(val))
                self.q_status.setText(f'Current: {val} Samples')
        else:
            preview = (out or '')[:100].strip().replace('\n', ' ')
            self.q_status.setText(f'No value: {preview}')
        self._update_latency()
        self._update_latency()

    def _update_latency(self):
        if self._current_quantum > 0 and self._current_rate > 0:
            ms = self._current_quantum * 1000 / self._current_rate
            khz = self._current_rate / 1000
            self.latency_label.setText(f'{ms:.1f} ms')
            self.latency_label.setToolTip(
                f'Quantum [Samples] = Latency [ms] \u00d7 Sample Rate [kHz]\n'
                f'{self._current_quantum} = {ms:.1f}ms \u00d7 {khz}kHz'
            )
        else:
            self.latency_label.setText('\u2014')

    def _reset_xruns(self):
        self._xruns_offset = getattr(self, '_current_total_xruns', 0)
        self.xruns_label.setText('0')
        self.xruns_label.setStyleSheet('font-size: 20px; font-weight: bold; color: #e0e0e0;')

    # ─── pw-top ──────────────────────────────────────────────

    @property
    def aes67_dsp(self):
        total_wait = 0.0
        total_busy = 0.0
        for n in self._last_nodes:
            if n.get('is_child'):
                continue
            name = n.get('name', '').lower()
            if 'rtp' not in name and 'aes67' not in name and 'ptp' not in name:
                continue
            txt = n.get('waiting', '---')
            if txt.strip() not in ('---', '\u2014', ''):
                txt = txt.strip().replace(',', '.')
                m = re.match(r'([\d.]+)\s*(us|ms|s)?', txt)
                if m:
                    v = float(m.group(1))
                    u = m.group(2) or ''
                    if u == 'ms':
                        v *= 1000
                    elif u == 's':
                        v *= 1_000_000
                    total_wait += v
            txt = n.get('busy', '---')
            if txt.strip() not in ('---', '\u2014', ''):
                txt = txt.strip().replace(',', '.')
                m = re.match(r'([\d.]+)\s*(us|ms|s)?', txt)
                if m:
                    v = float(m.group(1))
                    u = m.group(2) or ''
                    if u == 'ms':
                        v *= 1000
                    elif u == 's':
                        v *= 1_000_000
                    total_busy += v
        if total_wait + total_busy == 0:
            return 0.0
        return total_busy / (total_wait + total_busy) * 100

    def _update_all(self):
        self._refresh_rate()
        self._fetch_pwtop()
        self._update_rate_from_pwtop()
        self._update_quantum_from_pwtop()

    def _fetch_pwtop(self):
        out = self._run([_PW_TOP, '-b', '-n', '2'])
        if not out or not out.strip():
            out = self._run([_PW_TOP, '-b', '-n', '1'])
        if not out or not out.strip():
            self.table.setRowCount(1)
            self.table.setItem(0, 0, QTableWidgetItem('No pw-top data'))
            return

        lines = out.split('\n')

        # Zweiten Datenblock finden (nach dem zweiten Header)
        # pw-top -n 2 gibt: [Header1 + Daten1] + [Header2 + Daten2]
        # Wir wollen nur Daten2 (die aktuellen Running-States)
        headers = []
        for i, line in enumerate(lines):
            if re.match(r'^S\s+ID\s+QUANT', line):
                headers.append(i)
            elif 'QUANT' in line and 'RATE' in line and line.strip().startswith('S'):
                headers.append(i)

        if len(headers) < 2:
            # Fallback: nur ein Header gefunden → ganzen Output nehmen
            header_idx = headers[0] if headers else 0
        else:
            header_idx = headers[-1]  # letzten Header nehmen (2. Iteration)

        # Parse nodes (from last header to end or next header)
        nodes = []
        for line in lines[header_idx + 1:]:
            if not line.strip():
                continue
            if re.match(r'^S\s+ID\s+QUANT', line):
                break
            if 'QUANT' in line and 'RATE' in line:
                break
            node = self._parse_pwtop_line(line)
            if node:
                nodes.append(node)

        if not nodes:
            self.table.setRowCount(1)
            self.table.setItem(0, 0, QTableWidgetItem('No nodes found'))
            return

        tree = self._build_tree(nodes)
        self._fill_table(tree)
        self._last_nodes = nodes
        self._update_status(nodes)

    def _parse_pwtop_line(self, line):
        """Parst eine pw-top Datenzeile via Split bei 2+ Leerzeichen.
        Das ist robuster als Fixed-Width, weil Spalten-Positionen
        may vary between pw-top versions."""
        parts = re.split(r'\s{2,}', line)
        if len(parts) < 9:
            return None

        s = parts[0].strip()  # State: erster Buchstabe
        state = {'R': 'Running', 'S': 'Idle', 'C': 'Closed', 'I': 'Idle'}.get(s, s)

        # Bei 10+ Teilen ist parts[-2]=FORMAT, parts[-1]=NAME (Running-Nodes)
        # Bei 10 Teilen ohne FORMAT ist parts[-1]=NAME (Closed-Nodes)
        if len(parts) >= 11:
            fmt_raw = parts[-2].strip()
            raw_name = parts[-1].strip()
        else:
            fmt_raw = ''
            raw_name = parts[-1].strip() if len(parts) > 9 else ''
        name_clean = raw_name.lstrip('+ ')
        is_child = raw_name.startswith('+')

        fmt_parts = fmt_raw.split()
        fmt = fmt_parts[0] if fmt_parts else '\u2014'
        ch = fmt_parts[1] if len(fmt_parts) > 1 else '\u2014'

        def parse_time(t):
            t = t.strip()
            if t in ('---', '\u2014', ''):
                return 0.0
            t = t.replace(',', '.')
            m = re.match(r'([\d.]+)\s*(us|ms|s)?', t)
            if m:
                v = float(m.group(1))
                u = m.group(2) or ''
                if u == 'ms': v *= 1000
                elif u == 's': v *= 1_000_000
                return v
            return 0.0

        wait_raw = parts[4].strip() if len(parts) > 4 else '---'
        busy_raw = parts[5].strip() if len(parts) > 5 else '---'
        wait_us = parse_time(wait_raw)
        busy_us = parse_time(busy_raw)
        dsp = (busy_us / (wait_us + busy_us) * 100) if (wait_us + busy_us) > 0 else 0.0

        return {
            'id': parts[1].strip(),
            'state': state,
            'name': name_clean,
            'is_child': is_child,
            'quantum': parts[2].strip() if len(parts) > 2 else '0',
            'rate': parts[3].strip() if len(parts) > 3 else '0',
            'format': fmt,
            'channels': ch,
            'dsp': dsp,
            'dsp_str': f'{dsp:.1f}%',
            'waiting': wait_raw,
            'busy': busy_raw,
            'xruns': parts[8].strip() if len(parts) > 8 else '0',
        }

    def _build_tree(self, nodes):
        tree = []
        parent = None
        for n in nodes:
            if n['is_child'] and parent is not None:
                parent.setdefault('children', []).append(n)
            else:
                parent = n
                n.setdefault('children', [])
                tree.append(n)
        return tree

    def _fill_table(self, tree):
        total = sum(1 + len(n.get('children', [])) for n in tree)
        self.table.setRowCount(total)
        row = 0
        for n in tree:
            row = self._insert_row(row, n, 0)
            for ch in n.get('children', []):
                row = self._insert_row(row, ch, 1)

    def _insert_row(self, row, node, indent):
        name = node['name']
        if indent > 0:
            name = '    \u2514\u2500 ' + name

        dsp = node['dsp']
        if dsp < 30:
            dc = QColor('#4caf50')
        elif dsp < 70:
            dc = QColor('#ffc107')
        else:
            dc = QColor('#f44336')

        state_color = {'Running': QColor('#4caf50'),
                       'Idle': QColor('#888'),
                       'Closed': QColor('#666')}.get(node['state'], QColor('#aaa'))

        items = [
            (node['id'], None),
            (node['state'], state_color),
            (name, QColor('#999') if indent > 0 else None),
            (node['quantum'], None),
            (node['format'], None),
            (node['channels'], None),
            ('', None),
            (node['waiting'], None),
            (node['busy'], None),
            (node['xruns'], None),
            (node['rate'], None),
        ]

        for col, (text, color) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if color:
                item.setForeground(QBrush(color))
            self.table.setItem(row, col, item)

        # DSP-Balken + Prozentzahl nebeneinander
        dsp_widget = QWidget()
        dsp_layout = QHBoxLayout(dsp_widget)
        dsp_layout.setContentsMargins(2, 0, 2, 0)
        dsp_layout.setSpacing(3)

        dsp_label = QLabel(node['dsp_str'])
        dsp_label.setStyleSheet(f'color: {dc.name()}; font-weight: bold; font-size: 10px;')
        dsp_label.setFixedWidth(38)

        dsp_bar = QProgressBar()
        dsp_bar.setRange(0, 100)
        dsp_bar.setValue(int(round(dsp)))
        dsp_bar.setTextVisible(False)
        dsp_bar.setFixedHeight(12)
        dsp_bar.setStyleSheet(f"""
            QProgressBar {{ background-color: #333; border: none; border-radius: 2px; }}
            QProgressBar::chunk {{ background-color: {dc.name()}; border-radius: 2px; }}
        """)

        dsp_layout.addWidget(dsp_label)
        dsp_layout.addWidget(dsp_bar, 1)
        self.table.setCellWidget(row, 6, dsp_widget)

        return row + 1

    # ─── Status ──────────────────────────────────────────────

    def _update_status(self, nodes):
        running = [n for n in nodes if n['state'] == 'Running']

        def to_us(txt):
            t = txt.strip()
            if t in ('---', '\u2014', ''):
                return 0.0
            t = t.replace(',', '.')
            m = re.match(r'([\d.]+)\s*(us|ms|s)?', t)
            if m:
                v = float(m.group(1))
                u = m.group(2) or ''
                if u == 'ms':
                    v *= 1000
                elif u == 's':
                    v *= 1_000_000
                return v
            return 0.0

        total_wait = sum(to_us(n['waiting']) for n in running)
        total_busy = sum(to_us(n['busy']) for n in running)

        dsp_pct = (total_busy / (total_wait + total_busy) * 100) if (total_wait + total_busy) > 0 else 0.0

        self.dsp_label.setText(f'{dsp_pct:.0f}%')
        self.dsp_bar.setValue(int(round(dsp_pct)))

        if dsp_pct < 50:
            c = '#4caf50'
        elif dsp_pct < 80:
            c = '#ffc107'
        else:
            c = '#f44336'
        self.dsp_bar.setStyleSheet(f"""
            QProgressBar {{ background-color: #333; border: none; border-radius: 2px; min-height: 16px; }}
            QProgressBar::chunk {{ background-color: {c}; border-radius: 2px; }}
        """)
        self.dsp_label.setStyleSheet(f'font-size: 16px; font-weight: bold; color: {c};')

        # Xruns
        total_err = 0
        for n in nodes:
            try:
                total_err += int(n['xruns'])
            except ValueError:
                pass
        self._current_total_xruns = total_err

    def _update_rate_from_pwtop(self):
        """Timer-Update: Nur wenn Metadata=0 (Default), sonst Metadata-Wert anzeigen."""
        meta_val = self._read_metadata_value('clock.rate')
        if meta_val is not None and meta_val > 0:
            # Metadata ist gesetzt → Metadata-Wert anzeigen
            self._current_rate = meta_val
            idx = self.rate_combo.findData(meta_val)
            self.rate_combo.setCurrentIndex(idx) if idx >= 0 else self.rate_combo.setCurrentText(str(meta_val))
            self.rate_status.setText(f'Current: {meta_val} Hz')
            self._update_latency()
            return
        effective = self._get_effective_rate()
        if effective > 0:
            self._current_rate = effective
            idx = self.rate_combo.findData(effective)
            self.rate_combo.setCurrentIndex(idx) if idx >= 0 else self.rate_combo.setCurrentText(str(effective))
            self.rate_status.setText(f'Effective: {effective} Hz')
            self._update_latency()

    def _update_quantum_from_pwtop(self):
        meta_val = self._read_metadata_value('clock.quantum')
        if meta_val is not None and meta_val > 0:
            self._current_quantum = meta_val
            idx = self.q_combo.findData(meta_val)
            self.q_combo.setCurrentIndex(idx) if idx >= 0 else self.q_combo.setCurrentText(str(meta_val))
            self.q_status.setText(f'Current: {meta_val} Samples')
            self._update_latency()
            return
        effective = self._get_effective_quantum()
        if effective > 0:
            self._current_quantum = effective
            self.q_combo.setCurrentText(str(effective))
            self.q_status.setText(f'Effective: {effective} Samples')
            self._update_latency()

    def _read_metadata_value(self, key):
        """Reads a pw-metadata value. Returns int or None."""
        # Für force-fähige Keys zuerst die force-Version versuchen
        keys = [key]
        if 'quantum' in key:
            keys = ['clock.force-quantum', 'clock.quantum']
        elif 'rate' in key:
            keys = ['clock.force-rate', 'clock.rate']
        for k in keys:
            try:
                out = self._run([_PW_META, '-n', 'settings', '0', k])
            except Exception:
                continue
            if not out:
                continue
            m = re.search(r"value[=:]'?(\d+)'?", out)
            if m:
                return int(m.group(1))
            nums = re.findall(r'(\d+)', out)
            if nums:
                return int(nums[-1])
        return None

    def _get_effective_rate(self):
        if not hasattr(self, '_last_nodes') or not self._last_nodes:
            return 0
        for n in self._last_nodes:
            if n['state'] == 'Running':
                try:
                    r = int(n['rate'])
                    if r > 0:
                        return r
                except (ValueError, TypeError):
                    continue
        return 0

    def _get_effective_quantum(self):
        """Ermittelt das effektive Quantum aus den pw-top Nodes
        (erstes Running-Node-Quantum wird genommen)."""
        if not hasattr(self, '_last_nodes') or not self._last_nodes:
            return 0
        for n in self._last_nodes:
            if n['state'] == 'Running':
                try:
                    q = int(n['quantum'])
                    if q > 0:
                        return q
                except (ValueError, TypeError):
                    continue
        return 0

    def _sync_quantum_from_nodes(self):
        """Extrahiert die effektive Quantum-Einstellung aus den
        aktuellen pw-top Nodes (statt aus pw-metadata).
        Zeigt den Quantum-Wert des ersten Running-Nodes an.
        """
        if not hasattr(self, '_last_nodes') or not self._last_nodes:
            return
        running = [n for n in self._last_nodes if n['state'] == 'Running']
        if not running:
            # Keine aktiven Nodes → Default anzeigen
            self._current_quantum = 0
            self.q_combo.setCurrentText('')
            self.q_status.setText('Current: \u2014 (no active nodes)')
            self._update_latency()
            return
        # Quantum vom ersten Running-Node nehmen
        for node in running:
            try:
                q = int(node['quantum'])
                if q > 0:
                    self._current_quantum = q
                    idx = self.q_combo.findData(q)
                    if idx >= 0:
                        self.q_combo.setCurrentIndex(idx)
                    else:
                        self.q_combo.setCurrentText(str(q))
                    self.q_status.setText(f'Current: {q} Samples')
                    self._update_latency()
                    return
            except ValueError:
                continue
        # Fallback: kein brauchbares Quantum gefunden
        self.q_status.setText('Current: \u2014 (no quantum)')
        display = max(0, total_err - self._xruns_offset)
        self.xruns_label.setText(str(display))
        self.xruns_label.setStyleSheet(
            'font-size: 20px; font-weight: bold; color: #f44336;' if display > 0
            else 'font-size: 20px; font-weight: bold; color: #e0e0e0;'
        )
        self._update_latency()
