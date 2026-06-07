from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QTextEdit, QGroupBox, QCheckBox,
                               QScrollArea, QGridLayout, QProgressBar)
from PyQt6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt
from PyQt6.QtGui import QFont, QColor, QTextCharFormat
import os
import pwd
import shutil
import time
import traceback

from core.aes67_config import AES67Config, ConfigParseError
from core.aes67_log_parser import AES67LogParser, LOG_PATTERNS

_MAX_TERMINAL_LINES = 5000


def _trim_terminal(edit, max_lines=_MAX_TERMINAL_LINES):
    doc = edit.document()
    if doc.blockCount() > max_lines:
        cursor = edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        remove = doc.blockCount() - max_lines + 100
        for _ in range(remove):
            cursor.movePosition(cursor.MoveOperation.Down, cursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.deleteChar()


_COLOR_MAP = {
    'error': QColor('#f44336'),
    'warning': QColor('#ffc107'),
    'info': QColor('#E0E0E0'),
}


class AES67Tab(QWidget):
    def __init__(self, ptp_tab=None, pipewire_tab=None):
        super().__init__()
        self.config = None
        self.process = None
        self.is_running = False
        self.ptp_tab = ptp_tab
        self.pipewire_tab = pipewire_tab
        self._init_config()
        self.parser = AES67LogParser()
        self._stdout_buffer = ''
        self._stderr_buffer = ''
        self._write_timer = QTimer(self)
        self._write_timer.setInterval(50)
        self._write_timer.timeout.connect(self._flush_terminal)
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(200)
        self._update_timer.timeout.connect(self._update_status_panel)
        self._last_warning_time = 0.0
        self._health_quiet_seconds = 30
        self.init_ui()
        self.ptp_check_timer = QTimer()
        self.ptp_check_timer.timeout.connect(self._check_ptp_state)
        self.ptp_check_timer.start(1000)
        self._check_ptp_state()

    def _init_config(self):
        user_home = self._get_user_home()
        self.config_path = os.path.join(user_home, ".config/pipewire/pipewire-aes67.conf")
        self.default_config_path = "/usr/share/pipewire/pipewire-aes67.conf"
        try:
            self.config = AES67Config()
            self.config.load(self.config_path)
        except FileNotFoundError:
            self.config = None
        except ConfigParseError:
            try:
                self.config = AES67Config()
                self.config.load(self.default_config_path)
                self.config._loaded_path = self.config_path
            except (ConfigParseError, FileNotFoundError):
                self.config = None

    def init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        # ── Top row: Buttons (left) + Status panel (fills remaining) ──
        top_row = QHBoxLayout()

        btn_col = QVBoxLayout()
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start pipewire-aes67")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: white; border: none;
                padding: 8px 14px; font-size: 14px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
        """)
        self.start_btn.setToolTip("PTP clock not ready.\nWait for synchronization \u22641000ns or Grand Master.")
        self.start_btn.clicked.connect(self.start_aes67)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop pipewire-aes67")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336; color: white; border: none;
                padding: 8px 14px; font-size: 14px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #da190b; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
        """)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_aes67)
        btn_row.addWidget(self.stop_btn)
        btn_col.addLayout(btn_row)

        # Config group unter den Buttons
        config_group = QGroupBox("Configuration")
        config_layout = QHBoxLayout()
        self.config_btn = QPushButton("Open Config")
        self.config_btn.clicked.connect(self.open_config)
        config_layout.addWidget(self.config_btn)
        self.editor_btn = QPushButton("AES67 Config Editor")
        self.editor_btn.clicked.connect(self.open_config_editor)
        config_layout.addWidget(self.editor_btn)
        config_layout.addStretch()
        config_group.setLayout(config_layout)
        config_group.setStyleSheet("QGroupBox { font-size: 11px; }")
        btn_col.addWidget(config_group)

        # DSP Load
        dsp_group = QGroupBox("DSP Load")
        dsp_group.setObjectName("AES67Dsp")
        dsp_group.setMinimumWidth(220)
        dsp_group.setStyleSheet("""
            QGroupBox#AES67Dsp { font-size: 11px; padding: 2px 4px; border: 1px solid #555; border-radius: 4px; margin-top: 14px; }
            QGroupBox#AES67Dsp::title { subcontrol-origin: margin; left: 6px; padding: 0 2px; }
        """)
        dsp_layout = QVBoxLayout(dsp_group)
        dsp_layout.setContentsMargins(4, 4, 4, 4)
        dsp_layout.setSpacing(4)
        self.aes67_dsp_label = QLabel("0%")
        self.aes67_dsp_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #888;")
        self.aes67_dsp_bar = QProgressBar()
        self.aes67_dsp_bar.setRange(0, 100)
        self.aes67_dsp_bar.setValue(0)
        self.aes67_dsp_bar.setFixedHeight(14)
        self.aes67_dsp_bar.setTextVisible(False)
        self.aes67_dsp_bar.setStyleSheet("QProgressBar { background-color: #333; border: none; border-radius: 2px; }")
        dsp_layout.addWidget(self.aes67_dsp_label)
        dsp_layout.addWidget(self.aes67_dsp_bar)

        btn_col.addStretch()

        top_row.addLayout(btn_col)

        # ── Status panel (flexible width) ──
        status_group = QGroupBox("AES67 Stream Health")
        status_group.setObjectName("AES67StreamHealth")
        status_group.setStyleSheet("""
            QGroupBox#AES67StreamHealth {
                font-size: 13px; font-weight: bold; color: #e0e0e0;
                border: 1px solid #555; border-radius: 6px;
                margin-top: 12px; padding-top: 16px;
            }
            QGroupBox#AES67StreamHealth::title {
                subcontrol-origin: margin;
                left: 10px; padding: 0 6px;
            }
        """)
        status_grid = QGridLayout()
        status_grid.setSpacing(3)
        status_grid.setColumnStretch(0, 0)
        status_grid.setColumnStretch(1, 1)

        self.health_label = QLabel("\u25cf Idle")
        self.health_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #888;")
        status_grid.addWidget(self.health_label, 0, 0, 1, 2)

        self._counter_labels = {}
        self._reset_btns = {}
        row = 1
        for p in LOG_PATTERNS:
            lbl = QLabel(f"{p['label']}:")
            lbl.setStyleSheet("font-size: 11px; color: #aaa;")
            val = QLabel("0")
            val.setStyleSheet("font-size: 11px; font-weight: bold; color: #e0e0e0;")
            self._counter_labels[p['key']] = val
            rbtn = QPushButton("\u21ba")
            rbtn.setFixedSize(24, 20)
            rbtn.setToolTip(f"Reset {p['label']}")
            rbtn.setStyleSheet("font-size: 10px; border: 1px solid #555; border-radius: 3px;")
            rbtn.clicked.connect(lambda checked, k=p['key']: self._reset_counter(k))
            self._reset_btns[p['key']] = rbtn
            vb = QHBoxLayout()
            vb.setSpacing(24)
            vb.addWidget(val)
            vb.addWidget(rbtn)
            vb.addStretch()
            status_grid.addWidget(lbl, row, 0)
            status_grid.addLayout(vb, row, 1)
            row += 1

        other_lbl = QLabel("Other:")
        other_lbl.setStyleSheet("font-size: 11px; color: #aaa;")
        self._other_val = QLabel("0")
        self._other_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #e0e0e0;")
        other_rbtn = QPushButton("\u21ba")
        other_rbtn.setFixedSize(24, 20)
        other_rbtn.setToolTip("Reset Other")
        other_rbtn.setStyleSheet("font-size: 10px; border: 1px solid #555; border-radius: 3px;")
        other_rbtn.clicked.connect(lambda: self._reset_counter('other'))
        vb = QHBoxLayout()
        vb.setSpacing(24)
        vb.addWidget(self._other_val)
        vb.addWidget(other_rbtn)
        vb.addStretch()
        status_grid.addWidget(other_lbl, row, 0)
        status_grid.addLayout(vb, row, 1)
        row += 1

        sep = QLabel("\u2500" * 28)
        sep.setStyleSheet("color: #555; font-size: 8px;")

        self._last_summary = QLabel("")
        self._last_summary.setWordWrap(True)
        self._last_summary.setStyleSheet("font-size: 11px; color: #e0e0e0; padding: 0 4px 1px 4px;")
        self._last_advice = QLabel("")
        self._last_advice.setWordWrap(True)
        self._last_advice.setStyleSheet("font-size: 10px; color: #888; padding: 0 4px 1px 4px;")

        right_col = QVBoxLayout()
        right_col.setSpacing(2)
        right_col.addWidget(dsp_group)
        right_col.addSpacing(4)
        right_col.addWidget(sep)
        right_col.addWidget(self._last_summary)
        right_col.addWidget(self._last_advice)
        right_col.addStretch()

        status_inner = QHBoxLayout()
        status_inner.addLayout(status_grid, stretch=0)
        status_inner.addSpacing(8)
        status_inner.addLayout(right_col, stretch=1)

        status_group.setLayout(status_inner)
        top_row.addWidget(status_group, stretch=1)

        layout.addLayout(top_row)

        # ── Verbose checkbox + Output header ──
        out_header = QHBoxLayout()
        self.verbose_cb = QCheckBox("Verbose output (-v)")
        self.verbose_cb.setStyleSheet("font-size: 11px;")
        out_header.addWidget(self.verbose_cb)
        out_header.addSpacing(8)
        out_header.addWidget(QLabel("AES67 Output:"))
        out_header.addStretch()
        layout.addLayout(out_header)

        # ── Terminal ──
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setFont(QFont("Courier New", 10))
        self.terminal_output.setStyleSheet("""
            QTextEdit {
                background-color: #000000; color: #E0E0E0;
                border: 1px solid #333333;
            }
        """)
        layout.addWidget(self.terminal_output, stretch=1)

        scroll.setWidget(content)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

    def _reset_counter(self, key):
        self.parser.reset_counter(key)
        self._update_status_panel()

    def _update_status_panel(self):
        # DSP Load from PipeWire tab
        if self.pipewire_tab is not None:
            dsp_val = int(round(self.pipewire_tab.aes67_dsp))
            self.aes67_dsp_label.setText(f"{dsp_val}%")
            self.aes67_dsp_bar.setValue(dsp_val)
            c = '#4caf50' if dsp_val < 50 else '#ffc107' if dsp_val < 80 else '#f44336'
            self.aes67_dsp_label.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {c};")
            self.aes67_dsp_bar.setStyleSheet(f"""
                QProgressBar {{ background-color: #333; border: none; border-radius: 2px; min-height: 14px; }}
                QProgressBar::chunk {{ background-color: {c}; border-radius: 2px; }}
            """)

        if not self.is_running:
            self.health_label.setText("\u25cf Idle")
            self.health_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #888;")
            for p in LOG_PATTERNS:
                self._counter_labels[p['key']].setText(str(self.parser.counters[p['key']]))
            self._other_val.setText(str(self.parser.other_count))
            return

        # Auto-Reset Health nach 30s ohne neue Warnungen/Fehler
        if (self.parser.severity_counts['warning'] > 0 or self.parser.severity_counts['error'] > 0):
            quiet = time.monotonic() - self._last_warning_time
            if quiet > self._health_quiet_seconds:
                self.parser.severity_counts['warning'] = 0
                self.parser.severity_counts['error'] = 0
        sev = self.parser.aggregate_severity
        color_map = {'info': '#4caf50', 'warning': '#ffc107', 'error': '#f44336'}
        sev_labels = {'info': 'OK', 'warning': 'Warnings', 'error': 'Errors'}
        self.health_label.setText(f"\u25cf {sev_labels[sev]}")
        self.health_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color_map[sev]};")

        for p in LOG_PATTERNS:
            self._counter_labels[p['key']].setText(str(self.parser.counters[p['key']]))
            if self.parser.counters[p['key']] > 0:
                self._counter_labels[p['key']].setStyleSheet(
                    f"font-size: 11px; font-weight: bold; color: {color_map['warning'] if p['severity'] == 'warning' else color_map['error']};"
                )
            else:
                self._counter_labels[p['key']].setStyleSheet("font-size: 11px; font-weight: bold; color: #e0e0e0;")
        self._other_val.setText(str(self.parser.other_count))

        last = self.parser.last_info
        if last:
            ts = f"[{last.get('timestamp', '')}] " if last.get('timestamp') else ""
            self._last_summary.setText(f"{ts}{last['summary']}")
            if last['advice']:
                self._last_advice.setText(f"\U0001f4a1 {last['advice']}")
            else:
                self._last_advice.setText("")
        else:
            self._last_summary.setText("No warnings yet.")
            self._last_advice.setText("")

    def _append_colored(self, text):
        """Fügt Text mit Farbcodierung ins Terminal ein (Error=rot, Warning=gelb)."""
        for line in text.split('\n'):
            sev = self.parser.parse_line(line)
            if sev and sev[0] in ('warning', 'error'):
                self._last_warning_time = time.monotonic()
            cursor = self.terminal_output.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            fmt = QTextCharFormat()
            if sev:
                fmt.setForeground(_COLOR_MAP.get(sev[0], _COLOR_MAP['info']))
            else:
                fmt.setForeground(_COLOR_MAP['info'])
            cursor.insertText(line + '\n', fmt)
            self.terminal_output.setTextCursor(cursor)
        self.terminal_output.ensureCursorVisible()
        _trim_terminal(self.terminal_output)

    def _flush_terminal(self):
        if self._stdout_buffer:
            self._append_colored(self._stdout_buffer)
            self._stdout_buffer = ''
        if self._stderr_buffer:
            self._append_colored(self._stderr_buffer)
            self._stderr_buffer = ''
        self._write_timer.stop()

    def _queue_stdout(self, text):
        self._stdout_buffer += text
        if not self._write_timer.isActive():
            self._write_timer.start()

    def _queue_stderr(self, text):
        self._stderr_buffer += text
        if not self._write_timer.isActive():
            self._write_timer.start()

    def _check_ptp_state(self):
        if self.is_running:
            return
        if self.ptp_tab is None:
            self.start_btn.setEnabled(True)
            self.start_btn.setToolTip("")
            return
        ptp_ready = (
            getattr(self.ptp_tab, 'is_ptp_running', False) and (
                getattr(self.ptp_tab, '_ptp_state', '') == 'MASTER' or
                (
                    getattr(self.ptp_tab, '_ptp_state', '') == 'SLAVE' and
                    getattr(self.ptp_tab, '_ptp_offset', None) is not None and
                    getattr(self.ptp_tab, '_ptp_offset', None) <= 1000
                )
            )
        )
        self.start_btn.setEnabled(ptp_ready)
        if not ptp_ready:
            self.start_btn.setToolTip(
                "PTP clock not ready.\n"
                "Wait for PTP synchronization (offset \u22641000ns or Grand Master)."
            )
        else:
            self.start_btn.setToolTip("")

    def start_aes67(self):
        try:
            self.parser.reset_all()
            self.terminal_output.clear()
            self._update_status_panel()
            self._update_timer.start()

            user_home = self._get_user_home()
            uid = int(os.getenv('SUDO_UID', str(os.getuid())))
            runtime_dir = f"/run/user/{uid}"
            bus_address = f"unix:path={runtime_dir}/bus"

            if not os.path.exists(self.config_path):
                if os.path.exists(self.default_config_path):
                    shutil.copy(self.default_config_path, self.config_path)
                    self._queue_stdout(
                        "No user config found. Default copied to:\n"
                        f"  {self.config_path}\n"
                    )
                else:
                    self._queue_stdout(
                        "ERROR: Neither user config nor default config found.\n"
                    )
                    return
                self._init_config()

            use_config = self.config_path

            if self.config:
                clock_intf = self.config.get(
                    'context.objects', 0, 'args', 'clock.interface'
                )
                if clock_intf:
                    self._queue_stdout(
                        f"Starte pipewire-aes67 mit Interface-Clock {clock_intf}...\n"
                    )
                else:
                    self._queue_stdout(
                        "Starte pipewire-aes67 (System-Clock)...\n"
                    )
            else:
                self._queue_stdout("Starte pipewire-aes67...\n")

            env = QProcessEnvironment.systemEnvironment()
            env.insert("HOME", user_home)
            env.insert("XDG_RUNTIME_DIR", runtime_dir)
            env.insert("DBUS_SESSION_BUS_ADDRESS", bus_address)

            self._queue_stdout(f"Config: {use_config}\n")
            self._queue_stdout(f"XDG_RUNTIME_DIR={runtime_dir}\n")

            self.process = QProcess()
            self.process.setProcessEnvironment(env)
            self.process.readyReadStandardOutput.connect(self._on_stdout)
            self.process.readyReadStandardError.connect(self._on_stderr)
            self.process.finished.connect(self.process_finished)

            args = ["-c", use_config]
            if self.verbose_cb.isChecked():
                args.append("-v")
            self.process.start("pipewire-aes67", args)
            self.is_running = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.verbose_cb.setEnabled(False)
            self.ptp_check_timer.stop()

        except Exception as e:
            self._queue_stdout(f"Error: {str(e)}\n")
            self._queue_stdout(traceback.format_exc())

    def stop_aes67(self):
        if self.is_running and self.process:
            self._queue_stdout("Stopping pipewire-aes67...\n")
            self.process.terminate()
            if not self.process.waitForFinished(3000):
                self._queue_stdout("Process did not terminate gracefully, forcing...\n")
                self.process.kill()
                self.process.waitForFinished()
            self.is_running = False
            self.process = None
            self.stop_btn.setEnabled(False)
            self.verbose_cb.setEnabled(True)
            self._queue_stdout("pipewire-aes67 stopped.\n")
            self._flush_terminal()
            self._update_timer.stop()
            self.ptp_check_timer.start(1000)
            self._check_ptp_state()

    def open_config(self):
        if os.path.exists(self.config_path):
            self._queue_stdout(f"Opening config: {self.config_path}\n")
            QProcess.startDetached("xdg-open", [self.config_path])
        else:
            self._queue_stdout(
                f"Config not found at: {self.config_path}\n"
            )
            self._queue_stdout(
                "Create a config file or copy it from\n"
                f"  {self.default_config_path}\n"
            )

    def open_config_editor(self):
        if not os.path.exists(self.config_path):
            if os.path.exists(self.default_config_path):
                shutil.copy(self.default_config_path, self.config_path)
                self._queue_stdout("Default config copied.\n")
            else:
                self._queue_stdout("No config found.\n")
                return
            self._init_config()

        if self.config is None:
            self._init_config()
        if self.config is None:
            self._queue_stdout("Config could not be loaded.\n")
            return

        from ui.aes67_settings_dialog import AES67SettingsDialog
        dialog = AES67SettingsDialog(self.config, self)
        if dialog.exec() == AES67SettingsDialog.DialogCode.Accepted:
            self._queue_stdout("Config saved via editor.\n")
            self._init_config()

    def _get_user_home(self):
        sudo_user = os.environ.get('SUDO_USER')
        if sudo_user:
            return pwd.getpwnam(sudo_user).pw_dir
        return os.path.expanduser("~")

    def _on_stdout(self):
        data = self.sender().readAllStandardOutput()
        text = bytes(data).decode('utf-8', errors='replace')
        self._queue_stdout(text)

    def _on_stderr(self):
        data = self.sender().readAllStandardError()
        text = bytes(data).decode('utf-8', errors='replace')
        self._queue_stderr(text)

    def process_finished(self, exit_code, exit_status):
        self.is_running = False
        self.process = None
        self.stop_btn.setEnabled(False)
        self.verbose_cb.setEnabled(True)
        self._queue_stdout(f"pipewire-aes67 exited with code {exit_code}\n")
        self._flush_terminal()
        self._update_timer.stop()
        self.ptp_check_timer.start(1000)
        self._check_ptp_state()
        self._reset_display()

    def _reset_display(self):
        self.aes67_dsp_label.setText("0%")
        self.aes67_dsp_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #888;")
        self.aes67_dsp_bar.setValue(0)
        self.aes67_dsp_bar.setStyleSheet(
            "QProgressBar { background-color: #333; border: none; border-radius: 2px; min-height: 14px; }"
        )
        self.health_label.setText("\u25cf Idle")
        self.health_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #888;")
        for p in LOG_PATTERNS:
            self._counter_labels[p['key']].setText("0")
            self._counter_labels[p['key']].setStyleSheet("font-size: 11px; font-weight: bold; color: #e0e0e0;")
        self._other_val.setText("0")
        self._other_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #e0e0e0;")
        self._last_summary.clear()
        self._last_advice.clear()
