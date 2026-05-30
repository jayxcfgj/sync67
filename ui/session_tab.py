"""Session Tab – Quick-Start, System-Status, Versions, Routing-Tools."""

import os
import subprocess
import re
import shutil
import stat
import sys
import pwd

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QProgressBar, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

from core.version import __version__, __app_name__
from ui.pipewire_tab import _user_env


def _fix_flatpak_dirs():
    """Fix stale root-owned flatpak dirs in user's runtime dir (von vorherigen root-Aufrufen)."""
    sudo_uid = os.environ.get('SUDO_UID', '1000')
    try:
        pw = pwd.getpwuid(int(sudo_uid))
        uid, gid = pw.pw_uid, pw.pw_gid
        flatpak_dir = f'/run/user/{uid}/.flatpak'
        if not os.path.isdir(flatpak_dir):
            return
        for root, dirs, files in os.walk(flatpak_dir):
            for name in dirs + files:
                path = os.path.join(root, name)
                try:
                    if os.stat(path).st_uid == 0:
                        os.chown(path, uid, gid)
                except (PermissionError, FileNotFoundError):
                    pass
    except (KeyError, PermissionError, OSError):
        pass


def _set_user_uid():
    """Setzt UID/GID auf den echten User (nicht root) im Child-Process vor exec()."""
    sudo_uid = os.environ.get('SUDO_UID')
    if sudo_uid:
        try:
            pw = pwd.getpwuid(int(sudo_uid))
            os.setgid(pw.pw_gid)
            os.setuid(pw.pw_uid)
        except (KeyError, PermissionError, OSError):
            pass


def _flatpak_env():
    """User-Env ohne SUDO_*-Variablen (flatpak erkennt sonst sudo)."""
    env = _user_env()
    for key in ('SUDO_UID', 'SUDO_USER', 'SUDO_GID', 'SUDO_COMMAND'):
        env.pop(key, None)
    return env


class SessionTab(QWidget):
    def __init__(self, ptp_tab, aes67_tab, pipewire_tab):
        super().__init__()
        self.ptp = ptp_tab
        self.aes67 = aes67_tab
        self.pw = pipewire_tab
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_status)
        self._waiting_for_ptp = False
        self._ptp_wait_timer = QTimer(self)
        self._ptp_wait_timer.timeout.connect(self._check_ptp_and_start_aes67)
        self.init_ui()
        self._timer.start(2000)

    def init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        # ── Quick-Start ──
        qs_group = QGroupBox('Quick-Start')
        qs_layout = QHBoxLayout(qs_group)
        self.start_btn = QPushButton('\u25b6 Session Start')
        self.start_btn.setStyleSheet('''
            QPushButton { background-color: #4CAF50; color: white; border: none;
                          padding: 10px 24px; font-size: 16px; border-radius: 4px; }
            QPushButton:hover { background-color: #45a049; }
        ''')
        self.start_btn.clicked.connect(self._session_start)

        self.stop_btn = QPushButton('\u25a0 Session Stop')
        self.stop_btn.setStyleSheet('''
            QPushButton { background-color: #f44336; color: white; border: none;
                          padding: 10px 24px; font-size: 16px; border-radius: 4px; }
            QPushButton:hover { background-color: #da190b; }
            QPushButton:disabled { background-color: #555; color: #888; }
        ''')
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._session_stop)

        qs_layout.addWidget(self.start_btn)
        qs_layout.addWidget(self.stop_btn)
        qs_layout.addStretch()
        layout.addWidget(qs_group)

        self.session_state_label = QLabel('')
        self.session_state_label.setStyleSheet('color: #888; font-size: 11px; padding-left: 4px;')
        layout.addWidget(self.session_state_label)

        # ── System Status ──
        ss_group = QGroupBox('System Status')
        ss_grid = QGridLayout(ss_group)

        self.ptp_status = QLabel('\u25cf PTP: \u2014')
        self.ptp_status.setStyleSheet('font-size: 13px;')
        self.ptp_sync_label = QLabel('')
        self.ptp_sync_label.setStyleSheet('color: #888; font-size: 11px;')

        self.aes67_status = QLabel('\u25cf AES67: \u2014')
        self.aes67_status.setStyleSheet('font-size: 13px;')

        self.pw_status = QLabel('\u25cf PipeWire: \u2014')
        self.pw_status.setStyleSheet('font-size: 13px;')

        ss_grid.addWidget(self.ptp_status, 0, 0)
        ss_grid.addWidget(self.ptp_sync_label, 0, 1)
        ss_grid.addWidget(self.aes67_status, 1, 0, 1, 2)
        ss_grid.addWidget(self.pw_status, 2, 0, 1, 2)
        layout.addWidget(ss_group)

        # ── Sync / Xruns / DSP ──
        metrics = QHBoxLayout()

        # Sync-Ampel
        sync_box = QVBoxLayout()
        sync_box.addWidget(QLabel('PTP Sync'))
        self.sync_light = QLabel()
        self.sync_light.setFixedSize(32, 32)
        self.sync_light.setStyleSheet('background-color: gray; border-radius: 16px;')
        self.sync_label = QLabel('\u2014')
        self.sync_label.setStyleSheet('font-size: 11px; color: #888;')
        sync_box.addWidget(self.sync_light)
        sync_box.addWidget(self.sync_label)
        metrics.addLayout(sync_box)
        metrics.addStretch()

        # Xruns
        xruns_box = QVBoxLayout()
        xruns_box.addWidget(QLabel('Xruns (PipeWire)'))
        self.xruns_label = QLabel('0')
        self.xruns_label.setStyleSheet('font-size: 22px; font-weight: bold; color: #e0e0e0;')
        self.xruns_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.xruns_label.mousePressEvent = lambda e: self._reset_xruns()
        self.xruns_label.setToolTip('Click to reset')
        xruns_box.addWidget(self.xruns_label)
        xruns_box.addWidget(QLabel('click \u2192 reset'))
        metrics.addLayout(xruns_box)
        metrics.addStretch()

        # DSP Load
        dsp_box = QVBoxLayout()
        dsp_box.addWidget(QLabel('DSP Load'))
        self.dsp_label = QLabel('0%')
        self.dsp_label.setStyleSheet('font-size: 14px; font-weight: bold;')
        self.dsp_bar = QProgressBar()
        self.dsp_bar.setRange(0, 100)
        self.dsp_bar.setValue(0)
        self.dsp_bar.setFixedHeight(14)
        self.dsp_bar.setTextVisible(False)
        dsp_box.addWidget(self.dsp_label)
        dsp_box.addWidget(self.dsp_bar)
        metrics.addLayout(dsp_box)

        layout.addLayout(metrics)

        # ── Versions ──
        ver_group = QGroupBox('Versions')
        ver_layout = QVBoxLayout(ver_group)

        def get_ver(cmd, flag='--version'):
            try:
                r = subprocess.run([cmd, flag], capture_output=True, text=True, timeout=3)
                out = (r.stdout or r.stderr or '').strip()
                m = re.search(r'(\d+\.\d+\.?\d*)', out)
                return m.group(1) if m else ''
            except Exception:
                return ''

        pw_ver = get_ver('pipewire')
        ptp_ver = get_ver('ptp4l', '-v')
        py_ver = f'{sys.version_info.major}.{sys.version_info.minor}'
        from PyQt6.QtCore import PYQT_VERSION_STR

        MIN_VERSIONS = {
            'PipeWire': '1.1',
            'LinuxPTP': '4.0',
        }

        def _parse_version(v):
            parts = v.split('.')
            try:
                return tuple(int(x) for x in parts)
            except ValueError:
                return ()

        def ver_line(name, ver, min_ver=None, ok_color='#4caf50'):
            ok = bool(ver) and (min_ver is None or _parse_version(ver) >= _parse_version(min_ver))
            mark = '\u2713' if ok else '\u2717'
            color = ok_color if ok else '#f44336'
            v = ver or '\u2014'
            req = f' <span style="color: #888;">(min {min_ver})</span>' if min_ver else ''
            lbl = QLabel(
                f'<span style="color: {color};">{mark}</span> {name}  {v}{req}'
            )
            lbl.setTextFormat(Qt.TextFormat.RichText)
            ver_layout.addWidget(lbl)

        ver_line('PipeWire', pw_ver, MIN_VERSIONS.get('PipeWire'))
        ver_line('LinuxPTP', ptp_ver, MIN_VERSIONS.get('LinuxPTP'))
        ver_line('Python', py_ver)
        ver_line('PyQt6', PYQT_VERSION_STR)

        about_line = QHBoxLayout()
        sync_lbl = QLabel(f'{__app_name__} v{__version__}')
        sync_lbl.setStyleSheet('color: #888; font-size: 10px;')
        self.about_btn = QPushButton('\u2139 About')
        self.about_btn.setFixedWidth(80)
        from ui.about_dialog import AboutDialog
        self.about_btn.clicked.connect(lambda: AboutDialog(self).exec())
        about_line.addWidget(sync_lbl)
        about_line.addStretch()
        about_line.addWidget(self.about_btn)
        ver_layout.addLayout(about_line)

        layout.addWidget(ver_group)

        # ── Routing Tools ──
        rt_group = QGroupBox('Routing Tools')
        rt_layout = QHBoxLayout(rt_group)

        _APPIMAGE_DIRS = [
            os.path.expanduser('~/Applications'),
            os.path.expanduser('~/.local/bin'),
            '/opt',
            '/usr/local/bin',
        ]

        def _find_tool(cmd):
            """Findet ein Tool via PATH, Flatpak oder AppImage."""
            if shutil.which(cmd):
                return ('native', [cmd])
            try:
                r = subprocess.run(
                    ['flatpak', 'list', '--columns=application'],
                    capture_output=True, text=True, timeout=5
                )
                for line in r.stdout.splitlines():
                    if cmd.lower() in line.lower():
                        return ('flatpak', ['flatpak', 'run', line.strip()])
            except Exception:
                pass
            for d in _APPIMAGE_DIRS:
                if not os.path.isdir(d):
                    continue
                try:
                    for f in os.listdir(d):
                        if f.lower().endswith('.appimage') and cmd.lower() in f.lower():
                            path = os.path.join(d, f)
                            os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
                            return ('appimage', [path])
                except (PermissionError, FileNotFoundError):
                    pass
            return None

        def make_tool_btn(name, cmd):
            btn = QPushButton(f'\u26a1 {name}')
            found = _find_tool(cmd)
            if found:
                mode, args = found
                if mode == 'flatpak':
                    label = f'{cmd} ({mode})'
                    def _launch_flatpak(app_id):
                        _fix_flatpak_dirs()
                        subprocess.Popen(
                            ['flatpak', 'run', app_id],
                            env=_flatpak_env(),
                            preexec_fn=_set_user_uid
                        )
                    btn.clicked.connect(
                        lambda checked, a=args: _launch_flatpak(a[-1])
                    )
                else:
                    label = cmd
                    btn.clicked.connect(
                        lambda checked, a=args: subprocess.Popen(
                            a, env=_user_env()
                        )
                    )
                btn.setToolTip(f'{label} \u00f6ffnen')
            else:
                btn.setToolTip(f'{cmd} not found (PATH/Flatpak/AppImage)')
                btn.setEnabled(False)
                btn.setStyleSheet('color: #666;')
            return btn

        rt_layout.addWidget(make_tool_btn('qpwgraph', 'qpwgraph'))
        rt_layout.addWidget(make_tool_btn('helvum', 'helvum'))
        rt_layout.addWidget(make_tool_btn('coppwr', 'coppwr'))
        rt_layout.addWidget(make_tool_btn('Cable', 'cable'))
        rt_layout.addStretch()
        layout.addWidget(rt_group)

        layout.addStretch()

        scroll.setWidget(content)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    # ─── Session Start / Stop ─────────────────────────────

    def _session_start(self):
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.session_state_label.setText('Starting PTP...')

        # 1. PTP starten
        if hasattr(self.ptp, 'start_ptp'):
            self.ptp.start_ptp()
        # 2. Auf PTP-Sync warten, dann AES67 starten
        self._waiting_for_ptp = True
        self._ptp_wait_timer.start(500)

    def _check_ptp_and_start_aes67(self):
        ptp_running = getattr(self.ptp, 'is_ptp_running', False)
        if not ptp_running:
            self.session_state_label.setText('PTP failed to start or exited.')
            self._ptp_wait_timer.stop()
            self._waiting_for_ptp = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            return

        ptp_state = getattr(self.ptp, '_ptp_state', '')
        ptp_offset = getattr(self.ptp, '_ptp_offset', None)
        ptp_ready = (
            ptp_state == 'MASTER' or
            (ptp_state == 'SLAVE' and ptp_offset is not None and ptp_offset <= 1000)
        )
        if not ptp_ready:
            self.session_state_label.setText(
                f'Waiting for PTP sync... (state: {ptp_state or "INIT"}, '
                f'offset: {f"{ptp_offset}ns" if ptp_offset is not None else "?"})'
            )
            return

        # PTP sync ready → start AES67
        self._ptp_wait_timer.stop()
        self._waiting_for_ptp = False
        self.session_state_label.setText('PTP sync OK, starting AES67...')
        if hasattr(self.aes67, 'start_aes67'):
            self.aes67.start_aes67()
        QTimer.singleShot(3000, lambda: self.session_state_label.setText(''))

    def _session_stop(self):
        if self._waiting_for_ptp:
            self._ptp_wait_timer.stop()
            self._waiting_for_ptp = False
        if hasattr(self.aes67, 'stop_aes67'):
            self.aes67.stop_aes67()
        if hasattr(self.ptp, 'stop_ptp'):
            self.ptp.stop_ptp()
        self.session_state_label.setText('')
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    # ─── Status-Updates ──────────────────────────────────

    def _update_status(self):
        # PTP
        ptp_running = getattr(self.ptp, 'is_ptp_running', False)
        if ptp_running:
            self.ptp_status.setText('\u25cf PTP: RUNNING')
            self.ptp_status.setStyleSheet('font-size: 13px; color: #4caf50;')
        else:
            self.ptp_status.setText('\u25cf PTP: stopped')
            self.ptp_status.setStyleSheet('font-size: 13px; color: #888;')

        # PTP Sync-Light
        offset = getattr(self.ptp, '_ptp_offset', None)
        if offset is not None and ptp_running:
            self.ptp_sync_label.setText(f'Interface: {self.ptp.interface_combo.currentText()}  \u00b1{offset}ns')
            if offset <= 200:
                color = '#4caf50'
            elif offset <= 1000:
                color = '#ffc107'
            else:
                color = '#f44336'
            self.sync_light.setStyleSheet(f'background-color: {color}; border-radius: 16px;')
            self.sync_label.setText(f'\u00b1{offset} ns')
        else:
            self.sync_light.setStyleSheet('background-color: gray; border-radius: 16px;')
            self.sync_label.setText('\u2014')

        # AES67
        aes67_running = getattr(self.aes67, 'is_running', False)
        if aes67_running:
            self.aes67_status.setText('\u25cf AES67: RUNNING')
            self.aes67_status.setStyleSheet('font-size: 13px; color: #4caf50;')
        else:
            self.aes67_status.setText('\u25cf AES67: stopped')
            self.aes67_status.setStyleSheet('font-size: 13px; color: #888;')

        # PipeWire
        rate = getattr(self.pw, '_current_rate', 0)
        quantum = getattr(self.pw, '_current_quantum', 0)
        self.pw_status.setText(
            f'\u25cf PipeWire: {rate} Hz  \u00b7 {quantum} Samples'
        )
        if rate > 0:
            self.pw_status.setStyleSheet('font-size: 13px; color: #4caf50;')
            # Xruns aus dem PipeWire-Tab
            xruns_text = self.pw.xruns_label.text() if hasattr(self.pw, 'xruns_label') else '0'
            self.xruns_label.setText(xruns_text)
            if xruns_text != '0':
                self.xruns_label.setStyleSheet('font-size: 22px; font-weight: bold; color: #f44336;')
            else:
                self.xruns_label.setStyleSheet('font-size: 22px; font-weight: bold; color: #e0e0e0;')
            # DSP
            dsp_text = self.pw.dsp_label.text() if hasattr(self.pw, 'dsp_label') else '0%'
            self.dsp_label.setText(dsp_text)
            dsp_val = int(self.pw.dsp_bar.value()) if hasattr(self.pw, 'dsp_bar') else 0
            self.dsp_bar.setValue(dsp_val)
            if dsp_val < 50:
                c = '#4caf50'
            elif dsp_val < 80:
                c = '#ffc107'
            else:
                c = '#f44336'
            self.dsp_bar.setStyleSheet(f"""
                QProgressBar {{ background-color: #333; border: none; border-radius: 2px; min-height: 14px; }}
                QProgressBar::chunk {{ background-color: {c}; border-radius: 2px; }}
            """)
            self.dsp_label.setStyleSheet(f'font-size: 14px; font-weight: bold; color: {c};')
        else:
            self.pw_status.setStyleSheet('font-size: 13px; color: #888;')

    def _reset_xruns(self):
        if hasattr(self.pw, '_reset_xruns'):
            self.pw._reset_xruns()
