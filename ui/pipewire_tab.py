"""PipeWire Tab – Sample Rate, Quantum, pw-top Node-Tabelle mit Tree-Struktur."""

import re
import os
import pwd
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QGroupBox, QGridLayout, QProgressBar,
    QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QBrush

_PW_TOP = '/usr/bin/pw-top'
_PW_META = '/usr/bin/pw-metadata'


def _user_env():
    """Gibt ein Environment-Dict zurück, das auf den eigentlichen User
    zeigt (nicht root), damit PipeWire-Socket und D-Bus erreichbar sind."""
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
        self.init_ui()
        self._timer.start(2000)
        QTimer.singleShot(300, self._update_all)

    # ─── UI ───────────────────────────────────────────────────

    def init_ui(self):
        layout = QVBoxLayout(self)

        # ── Sample Rate ──
        rg = QGroupBox('Sample Rate')
        g = QGridLayout(rg)
        self.rate_combo = QComboBox()
        for v in (48000, 96000, 192000):
            self.rate_combo.addItem(str(v), v)
        self.rate_apply = QPushButton('Apply')
        self.rate_apply.clicked.connect(lambda: self._set_metadata('clock.rate', self.rate_combo.currentText()))
        self.rate_reset = QPushButton('Reset')
        self.rate_reset.clicked.connect(lambda: self._set_metadata('clock.rate', '0'))
        self.rate_refresh = QPushButton('\u21bb')
        self.rate_refresh.clicked.connect(self._refresh_rate)
        self.rate_status = QLabel('Aktuell: \u2014')
        self.rate_status.setStyleSheet('color: #aaa;')
        g.addWidget(QLabel('Samplerate:'), 0, 0)
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
        self.q_apply.clicked.connect(lambda: self._set_metadata('clock.quantum', self.q_combo.currentText()))
        self.q_reset = QPushButton('Reset')
        self.q_reset.clicked.connect(lambda: self._set_metadata('clock.quantum', '0'))
        self.q_refresh = QPushButton('\u21bb')
        self.q_refresh.clicked.connect(self._refresh_quantum)
        self.q_status = QLabel('Aktuell: \u2014')
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
        lat_v.addWidget(QLabel('Quantum [Samples] = Latenz [ms] \u00d7 Rate [kHz]'))
        sh.addLayout(lat_v)
        sh.addStretch()

        xv = QVBoxLayout()
        xv.addWidget(QLabel('Xruns'))
        self.xruns_label = QLabel('0')
        self.xruns_label.setStyleSheet('font-size: 20px; font-weight: bold; color: #e0e0e0;')
        self.xruns_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.xruns_label.mousePressEvent = lambda e: self._reset_xruns()
        self.xruns_label.setToolTip('Klicken zum Zur\u00fccksetzen')
        xv.addWidget(self.xruns_label)
        xv.addWidget(QLabel('klick \u2192 reset'))
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
        tg = QGroupBox('Nodes (alle 2s)')
        tl = QVBoxLayout(tg)
        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            'ID', 'Status', 'Name', 'Quantum', 'Format', 'CH',
            'DSP', 'Waiting', 'Busy', 'Xruns'
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setShowGrid(False)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #1e1e1e; alternate-background-color: #252525; border: none; font-size: 11px; }
            QHeaderView::section { background-color: #2b2b2b; color: #aaa; padding: 4px 6px; border: none; border-bottom: 1px solid #444; font-weight: bold; font-size: 10px; }
        """)
        tl.addWidget(self.table)
        layout.addWidget(tg)

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
        QTimer.singleShot(200, self._refresh_rate if 'rate' in key else self._refresh_quantum)

    def _refresh_rate(self):
        out = self._run([_PW_META, '-n', 'settings', '0', 'clock.rate'])
        if out is None:
            self.rate_status.setText('Aktuell: \u2014 (pw-metadata nicht gefunden)')
            return
        # Debug: Zeige Output (nützlich bei Fehlersuche)
        debug_out = out[:200] if out else 'None'
        val = None
        # Versuche verschiedene Regex-Formate
        for pat in [
            r"key:'clock\.rate'.*?value:'(\d+)'",
            r"clock\.rate[=\s]+(\d+)",
            r"value:'(\d+)'",
            r"value=(\d+)",
            r"'(\d+)'",
            r'(\d+)',
        ]:
            m = re.search(pat, out, re.DOTALL) if out else None
            if m:
                try:
                    val = int(m.group(1))
                    break
                except ValueError:
                    continue
        if val is not None:
            self._current_rate = val
            idx = self.rate_combo.findData(val)
            if idx >= 0:
                self.rate_combo.setCurrentIndex(idx)
            else:
                self.rate_combo.setCurrentText(str(val))
            self.rate_status.setText(f'Aktuell: {val} Hz')
        else:
            self.rate_status.setText(f'Aktuell: \u2014 (kein Wert)')
        self._update_latency()

    def _refresh_quantum(self):
        out = self._run([_PW_META, '-n', 'settings', '0', 'clock.quantum'])
        if out is None:
            self.q_status.setText('Aktuell: \u2014 (pw-metadata nicht gefunden)')
            return
        debug_out = out[:200] if out else 'None'
        val = None
        for pat in [
            r"key:'clock\.quantum'.*?value:'(\d+)'",
            r"clock\.quantum[=\s]+(\d+)",
            r"value:'(\d+)'",
            r"value=(\d+)",
            r"'(\d+)'",
            r'(\d+)',
        ]:
            m = re.search(pat, out, re.DOTALL) if out else None
            if m:
                try:
                    val = int(m.group(1))
                    break
                except ValueError:
                    continue
        if val is not None:
            self._current_quantum = val
            idx = self.q_combo.findData(val)
            if idx >= 0:
                self.q_combo.setCurrentIndex(idx)
            else:
                self.q_combo.setCurrentText(str(val))
            self.q_status.setText(f'Aktuell: {val} Samples')
        else:
            self.q_status.setText(f'Aktuell: \u2014 (kein Wert)')
        self._update_latency()

    def _update_latency(self):
        if self._current_quantum > 0 and self._current_rate > 0:
            ms = self._current_quantum * 1000 / self._current_rate
            khz = self._current_rate / 1000
            self.latency_label.setText(f'{ms:.1f} ms')
            self.latency_label.setToolTip(
                f'Quantum [Samples] = Latenz [ms] \u00d7 Abtastrate [kHz]\n'
                f'{self._current_quantum} = {ms:.1f}ms \u00d7 {khz}kHz'
            )
        else:
            self.latency_label.setText('\u2014')

    def _reset_xruns(self):
        self._xruns_offset = getattr(self, '_current_total_xruns', 0)
        self.xruns_label.setText('0')
        self.xruns_label.setStyleSheet('font-size: 20px; font-weight: bold; color: #e0e0e0;')

    # ─── pw-top ──────────────────────────────────────────────

    def _update_all(self):
        self._refresh_rate()
        self._refresh_quantum()
        self._fetch_pwtop()

    def _fetch_pwtop(self):
        out = self._run([_PW_TOP, '-b', '-n', '2'])
        if not out or not out.strip():
            out = self._run([_PW_TOP, '-b', '-n', '1'])
        if not out or not out.strip():
            self.table.setRowCount(1)
            self.table.setItem(0, 0, QTableWidgetItem('Keine pw-top-Daten'))
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

        # Nodes parsen (ab dem letzten Header bis Ende oder nächstem Header)
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
            self.table.setItem(0, 0, QTableWidgetItem('Keine Nodes gefunden'))
            return

        tree = self._build_tree(nodes)
        self._fill_table(tree)
        self._update_status(nodes)

    def _parse_pwtop_line(self, line):
        """Parst eine pw-top Datenzeile via Split bei 2+ Leerzeichen.
        Das ist robuster als Fixed-Width, weil Spalten-Positionen
        zwischen pw-top Versionen variieren können."""
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
            (node['dsp_str'], dc),
            (node['waiting'], None),
            (node['busy'], None),
            (node['xruns'], None),
        ]

        for col, (text, color) in enumerate(items):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if color:
                item.setForeground(QBrush(color))
            self.table.setItem(row, col, item)

        # DSP-Balken
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(round(dsp)))
        bar.setTextVisible(False)
        bar.setFixedHeight(14)
        bar.setStyleSheet(f"""
            QProgressBar {{ background-color: #333; border: none; border-radius: 2px; }}
            QProgressBar::chunk {{ background-color: {dc.name()}; border-radius: 2px; }}
        """)
        self.table.setCellWidget(row, 6, bar)

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
        display = max(0, total_err - self._xruns_offset)
        self.xruns_label.setText(str(display))
        self.xruns_label.setStyleSheet(
            'font-size: 20px; font-weight: bold; color: #f44336;' if display > 0
            else 'font-size: 20px; font-weight: bold; color: #e0e0e0;'
        )
        self._update_latency()
