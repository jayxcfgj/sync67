from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QComboBox, QPushButton, QTextEdit, QGroupBox,
                               QFormLayout, QScrollArea)
from PyQt6.QtCore import Qt, QProcess, QSettings, QTimer
from PyQt6.QtGui import QFont, QTextCursor
import os
import subprocess
import re
import shutil
import traceback

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
from pathlib import Path

class PTPTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_interfaces()
        self.ptp_process = None
        self.is_ptp_running = False
        self._ptp_offset = None
        self._ptp_state = ""

        self.phc2sys_process = None
        self.is_phc2sys_running = False
        self._phc2sys_offset = None

    def init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        # ── Two-column top section ───────────────────────────────
        top_row = QHBoxLayout()

        # ── Left: PTP4L ──────────────────────────────────────────
        ptp4l_group = QGroupBox("PTP4L")
        ptp4l_inner = QVBoxLayout(ptp4l_group)

        iface_form = QFormLayout()
        self.interface_combo = QComboBox()
        self.interface_combo.setMinimumWidth(200)
        iface_form.addRow("Interface:", self.interface_combo)
        ptp4l_inner.addLayout(iface_form)

        self.settings_btn = QPushButton("Start Options")
        self.settings_btn.clicked.connect(self.open_settings)
        ptp4l_inner.addWidget(self.settings_btn)

        self.ptp4l_edit_btn = QPushButton("PTP4L Config Editor")
        self.ptp4l_edit_btn.clicked.connect(self.open_ptp4l_editor)
        ptp4l_inner.addWidget(self.ptp4l_edit_btn)

        ptp4l_inner.addStretch()

        ptp4l_btn_row = QHBoxLayout()
        self.start_btn = QPushButton("START PTP")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: white;
                border: none; padding: 8px 16px;
                font-size: 14px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.start_btn.clicked.connect(self.start_ptp)
        ptp4l_btn_row.addWidget(self.start_btn)

        self.stop_btn = QPushButton("STOP PTP")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336; color: white;
                border: none; padding: 8px 16px;
                font-size: 14px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #da190b; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
        """)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_ptp)
        ptp4l_btn_row.addWidget(self.stop_btn)

        ptp4l_btn_row.addWidget(QLabel("Sync:"))
        self.status_light = QLabel()
        self.status_light.setFixedSize(20, 20)
        self.status_light.setStyleSheet("background-color: gray; border-radius: 10px;")
        ptp4l_btn_row.addWidget(self.status_light)
        self.state_label = QLabel("")
        self.state_label.setStyleSheet("color: #cccccc; font-size: 11px; padding-left: 2px;")
        self.state_label.setMinimumWidth(80)
        ptp4l_btn_row.addWidget(self.state_label)
        ptp4l_btn_row.addStretch()
        ptp4l_inner.addLayout(ptp4l_btn_row)

        top_row.addWidget(ptp4l_group)

        # ── Right: phc2sys ───────────────────────────────────────
        phc2sys_group = QGroupBox("phc2sys")
        phc2sys_inner = QVBoxLayout(phc2sys_group)

        # Offset label at the top (matching Interface position)
        self.phc2sys_offset_label = QLabel("Offset: \u2014")
        self.phc2sys_offset_label.setStyleSheet("color: #cccccc; font-size: 12px; padding: 4px 0;")
        phc2sys_inner.addWidget(self.phc2sys_offset_label)

        self.phc2sys_config_btn = QPushButton("phc2sys Config...")
        self.phc2sys_config_btn.clicked.connect(self.open_phc2sys_config)
        phc2sys_inner.addWidget(self.phc2sys_config_btn)

        phc2sys_inner.addStretch()

        phc2sys_btn_row = QHBoxLayout()
        self.phc2sys_start_btn = QPushButton("Start phc2sys")
        self.phc2sys_start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: white;
                border: none; padding: 8px 16px;
                font-size: 14px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #555555; color: #888888; }
        """)
        self.phc2sys_start_btn.clicked.connect(self.start_phc2sys)
        phc2sys_btn_row.addWidget(self.phc2sys_start_btn)

        self.phc2sys_stop_btn = QPushButton("Stop phc2sys")
        self.phc2sys_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336; color: white;
                border: none; padding: 8px 16px;
                font-size: 14px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #da190b; }
            QPushButton:disabled { background-color: #cccccc; color: #666666; }
        """)
        self.phc2sys_stop_btn.setEnabled(False)
        self.phc2sys_stop_btn.clicked.connect(self.stop_phc2sys)
        phc2sys_btn_row.addWidget(self.phc2sys_stop_btn)

        phc2sys_btn_row.addWidget(QLabel("Status:"))
        self.phc2sys_light = QLabel()
        self.phc2sys_light.setFixedSize(20, 20)
        self.phc2sys_light.setStyleSheet("background-color: gray; border-radius: 10px;")
        phc2sys_btn_row.addWidget(self.phc2sys_light)
        self.phc2sys_state_label = QLabel("\u2014")
        self.phc2sys_state_label.setStyleSheet("color: #cccccc; font-size: 11px; padding-left: 2px;")
        self.phc2sys_state_label.setMinimumWidth(80)
        phc2sys_btn_row.addWidget(self.phc2sys_state_label)
        phc2sys_btn_row.addStretch()
        phc2sys_inner.addLayout(phc2sys_btn_row)

        top_row.addWidget(phc2sys_group)
        layout.addLayout(top_row)

        # ── Terminals (QSplitter) ────────────────────────────────
        from PyQt6.QtWidgets import QSplitter
        self.terminal_splitter = QSplitter(Qt.Orientation.Vertical)

        # ptp4l terminal
        ptp4l_terminal_wrap = QVBoxLayout()
        ptp4l_terminal_wrap.addWidget(QLabel("PTP4L Output:"))
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setFont(QFont("Courier New", 10))
        self.terminal_output.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.terminal_output.setStyleSheet("""
            QTextEdit {
                background-color: #000000;
                color: #E0E0E0;
                border: 1px solid #333333;
            }
        """)
        ptp4l_terminal_wrap.addWidget(self.terminal_output)
        ptp4l_container = QWidget()
        ptp4l_container.setLayout(ptp4l_terminal_wrap)
        self.terminal_splitter.addWidget(ptp4l_container)

        # phc2sys terminal
        phc2sys_terminal_wrap = QVBoxLayout()
        phc2sys_terminal_wrap.addWidget(QLabel("phc2sys Output:"))
        self.phc2sys_terminal = QTextEdit()
        self.phc2sys_terminal.setReadOnly(True)
        self.phc2sys_terminal.setFont(QFont("Courier New", 10))
        self.phc2sys_terminal.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.phc2sys_terminal.setStyleSheet("""
            QTextEdit {
                background-color: #000000;
                color: #E0E0E0;
                border: 1px solid #333333;
            }
        """)
        phc2sys_terminal_wrap.addWidget(self.phc2sys_terminal)
        phc2sys_container = QWidget()
        phc2sys_container.setLayout(phc2sys_terminal_wrap)
        self.terminal_splitter.addWidget(phc2sys_container)

        layout.addWidget(self.terminal_splitter)

        scroll.setWidget(content)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)

        self.phc2sys_process = QProcess()
        self.phc2sys_process.readyReadStandardOutput.connect(self._phc2sys_handle_stdout)
        self.phc2sys_process.readyReadStandardError.connect(self._phc2sys_handle_stderr)
        self.phc2sys_process.finished.connect(self._phc2sys_finished)

        self._phc2sys_sync_check = QTimer()
        self._phc2sys_sync_check.timeout.connect(self._phc2sys_check_sync)
        self._phc2sys_sync_check.start(2000)

    def load_interfaces(self):
        try:
            result = subprocess.run(['ip', 'link', 'show'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                interfaces = re.findall(r'^\d+: (\w+):', result.stdout, re.MULTILINE)
                interfaces = [iface for iface in interfaces if iface != 'lo']
                self.interface_combo.addItems(interfaces)
            else:
                self.interface_combo.addItem("Error loading interfaces")
        except Exception as e:
            self.interface_combo.addItem(f"Error: {str(e)}")
        # Gespeichertes Interface wiederherstellen
        settings = QSettings("sync67", "ptp_settings")
        saved = settings.value("selected_interface", "", type=str)
        if saved:
            idx = self.interface_combo.findText(saved)
            if idx >= 0:
                self.interface_combo.setCurrentIndex(idx)
        # Änderungen speichern
        self.interface_combo.currentIndexChanged.connect(self._save_interface)

    def _save_interface(self):
        settings = QSettings("sync67", "ptp_settings")
        settings.setValue("selected_interface", self.interface_combo.currentText())

    def open_settings(self):
        from ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec()

    def _ensure_uds_dir(self):
        try:
            from core.ptp4l_config import PTP4LConfig
            cfg = PTP4LConfig()
            cfg.load("/etc/linuxptp/ptp4l.conf")
            for key in ("uds_address", "uds_ro_address"):
                val = cfg.get(key)
                if val:
                    parent = os.path.dirname(str(val))
                    if parent:
                        os.makedirs(parent, exist_ok=True)
        except Exception:
            pass

    def start_ptp(self):
        try:
            iface = self.interface_combo.currentText()
            if not iface or iface.startswith("Error"):
                self.terminal_output.append("Please select a valid network interface")
                return

            self.terminal_output.clear()
            self.terminal_output.append(f"Starting PTP on interface {iface}...")

            # Check if we have cached sudo credentials
            sudo_check = QProcess()
            sudo_check.start("sudo", ["-n", "true"])
            sudo_check.waitForFinished(5000)
            if sudo_check.exitCode() != 0:
                self.terminal_output.append("No cached sudo credentials.")
                self.terminal_output.append("Run 'sudo -v' in a terminal first, then click START PTP again.")
                return

            self._ensure_uds_dir()

            settings = QSettings("sync67", "ptp_settings")
            gro_off = settings.value("gro_off", True, type=bool)
            gso_off = settings.value("gso_off", True, type=bool)
            tso_off = settings.value("tso_off", True, type=bool)
            sg_off = settings.value("sg_off", True, type=bool)
            rx_usecs_0 = settings.value("rx_usecs_0", True, type=bool)
            multicast_on = settings.value("multicast_on", True, type=bool)
            phc_reset = settings.value("phc_reset", True, type=bool)
            mcast_event = settings.value("mcast_event", True, type=bool)
            mcast_pdelay = settings.value("mcast_pdelay", True, type=bool)
            wol_d = settings.value("wol_d", True, type=bool)

            commands = []
            if phc_reset:
                phc_dev = self._get_phc_device(iface)
                if phc_dev:
                    commands.append(f"sudo phc_ctl {phc_dev} set")
                else:
                    self.terminal_output.insertPlainText(
                        f"⚠ Could not determine PHC device for {iface}, skipping phc_ctl\n"
                    )
            if wol_d:
                commands.append(f"sudo ethtool -s {iface} wol d")
            if gro_off:
                commands.append(f"sudo ethtool -K {iface} gro off")
            if gso_off:
                commands.append(f"sudo ethtool -K {iface} gso off")
            if tso_off:
                commands.append(f"sudo ethtool -K {iface} tso off")
            if sg_off:
                commands.append(f"sudo ethtool -K {iface} sg off")
            if rx_usecs_0:
                commands.append(f"sudo ethtool -C {iface} rx-usecs 0")
            if mcast_event:
                commands.append(f"sudo ip maddr add 01:1B:19:00:00:00 dev {iface}")
            if mcast_pdelay:
                commands.append(f"sudo ip maddr add 01:80:C2:00:00:0E dev {iface}")
            if multicast_on:
                commands.append(f"sudo ip link set {iface} multicast on")

            if commands:
                self.run_commands(commands, iface)
            else:
                self._start_ptp4l(iface)

        except Exception as e:
            self.terminal_output.append(f"Error: {str(e)}")
            self.terminal_output.append(traceback.format_exc())

    def _get_phc_device(self, iface):
        """Determine the PHC device for a network interface via ethtool -T.

        Returns e.g. '/dev/ptp1' or None if no PHC is associated /
        ethtool not available.
        """
        try:
            proc = QProcess()
            proc.start('ethtool', ['-T', iface])
            proc.waitForFinished(5000)
            out = bytes(proc.readAllStandardOutput()).decode('utf-8', errors='replace')
            m = re.search(r'PTP Hardware Clock:\s*(\d+)', out)
            if m:
                return f'/dev/ptp{m.group(1)}'
        except Exception:
            pass
        return None

    def run_commands(self, commands, iface):
        self.command_queue = commands.copy()
        self.iface = iface
        self.run_next_command()

    def run_next_command(self):
        cmd = self.command_queue.pop(0)
        self.terminal_output.insertPlainText(f"\nRunning: {cmd}\n")
        _trim_terminal(self.terminal_output)
        scrollbar = self.terminal_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        self.process.start("bash", ["-c", cmd])

    def handle_stdout(self):
        process = self.sender()
        if process is None:
            process = self.process
        data = process.readAllStandardOutput()
        stdout = bytes(data).decode('utf-8', errors='replace')
        self.terminal_output.insertPlainText(stdout)
        _trim_terminal(self.terminal_output)
        self.terminal_output.ensureCursorVisible()
        self.parse_ptp_output(stdout)

    def handle_stderr(self):
        process = self.sender()
        if process is None:
            process = self.process
        data = process.readAllStandardError()
        stderr = bytes(data).decode('utf-8', errors='replace')
        self.terminal_output.insertPlainText(stderr)
        _trim_terminal(self.terminal_output)
        self.terminal_output.ensureCursorVisible()
        self.parse_ptp_output(stderr)

    def parse_ptp_output(self, text):
        offset_patterns = [
            r'rms\s+(-?\d+)',
            r'offset\s+(-?\d+)'
        ]
        value = None
        for pattern in offset_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    val = int(match.group(1))
                    value = abs(val)
                    break
                except ValueError:
                    pass
        if value is not None:
            self._ptp_offset = value

        state_patterns = [
            (r'to MASTER on ', "MASTER"),
            (r'to SLAVE on ', "SLAVE"),
            (r'to UNCALIBRATED on ', "UNCALIBRATED"),
            (r'to FAULTY on ', "FAULTY"),
            (r'to LISTENING on ', "LISTENING"),
        ]
        for pat, state in state_patterns:
            if re.search(pat, text):
                self._ptp_state = state
                break

        self.update_status_light(value)

    def update_status_light(self, value=None):
        if self._ptp_state == "MASTER":
            color = "#2196F3"
            tip = "Grand Master – no PTP peer detected"
            label_text = "Grand Master"
        elif self._ptp_state == "FAULTY":
            color = "#ff0000"
            tip = "FAULTY – link or PTP error"
            label_text = "FAULTY"
        elif self._ptp_state == "LISTENING":
            color = "gray"
            tip = "Listening for PTP messages..."
            label_text = "Listening..."
        elif self._ptp_state == "UNCALIBRATED":
            color = "orange"
            tip = "Uncalibrated – acquiring sync"
            label_text = "Uncalibrated..."
        elif value is not None and self._ptp_state == "SLAVE":
            label_text = f"Slave ({value}ns)"
            if value <= 200:
                color = "green"
                tip = f"Sync: {value}ns (very good)"
            elif value <= 1000:
                color = "yellow"
                tip = f"Sync: {value}ns (okay)"
            else:
                color = "red"
                tip = f"Sync: {value}ns (problematic)"
        else:
            color = "gray"
            tip = "Sync Status: waiting"
            label_text = ""

        self.status_light.setStyleSheet(f"background-color: {color}; border-radius: 12px;")
        self.status_light.setToolTip(tip)
        self.state_label.setText(label_text)

    def process_finished(self, exit_code, exit_status):
        if self.command_queue:
            self.run_next_command()
        else:
            self._start_ptp4l(self.iface)

    def _start_ptp4l(self, iface):
        ptp_cmd = f"sudo ptp4l -f /etc/linuxptp/ptp4l.conf -i {iface} -m -l 6 -H"
        self.terminal_output.insertPlainText(f"\nRunning: {ptp_cmd}\n")
        _trim_terminal(self.terminal_output)
        scrollbar = self.terminal_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        self.ptp_process = QProcess()
        self.ptp_process.readyReadStandardOutput.connect(self.handle_stdout)
        self.ptp_process.readyReadStandardError.connect(self.handle_stderr)
        self.ptp_process.finished.connect(self.ptp_process_finished)
        self.is_ptp_running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.ptp_process.start("bash", ["-c", ptp_cmd])

    def _reset_status(self):
        self._ptp_state = ""
        self._ptp_offset = None
        self.status_light.setStyleSheet("background-color: gray; border-radius: 12px;")
        self.status_light.setToolTip("Sync Status: stopped")
        self.state_label.setText("")

    def ptp_process_finished(self, exit_code, exit_status):
        # Stop phc2sys first if ptp4l died
        if self.is_phc2sys_running:
            self.stop_phc2sys()
        self.is_ptp_running = False
        self.ptp_process = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._reset_status()
        if exit_code == 0:
            self.terminal_output.append("PTP process completed successfully.")
        else:
            self.terminal_output.append(f"PTP process exited with code: {exit_code}")

    def stop_ptp(self):
        # Stop phc2sys first if running
        if self.is_phc2sys_running:
            self.stop_phc2sys()
        if self.is_ptp_running and self.ptp_process:
            self.terminal_output.append("Stopping PTP...")
            self.ptp_process.terminate()
            if not self.ptp_process.waitForFinished(3000):
                self.terminal_output.append("PTP did not terminate gracefully, forcing...")
                self.ptp_process.kill()
                self.ptp_process.waitForFinished()
            self.is_ptp_running = False
            self.ptp_process = None
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self._reset_status()
            self.terminal_output.append("PTP stopped.")

    # ── phc2sys ──────────────────────────────────────────────────

    def open_phc2sys_config(self):
        from ui.phc2sys_config_dialog import Phc2sysConfigDialog
        dialog = Phc2sysConfigDialog(self)
        dialog.exec()

    def _can_start_phc2sys(self):
        return self.is_ptp_running and self._ptp_state in ('SLAVE', 'MASTER')

    def start_phc2sys(self):
        if self.is_phc2sys_running:
            return
        if not self._can_start_phc2sys():
            self.phc2sys_terminal.append("PTP must be running and synced before starting phc2sys.")
            return

        from ui.phc2sys_config_dialog import Phc2sysConfigDialog
        dlg = Phc2sysConfigDialog(self)
        args = dlg.build_command()
        if not args:
            self.phc2sys_terminal.append("phc2sys: using config file – not implemented yet.")
            return

        cmd = ['sudo', 'phc2sys'] + args
        cmd_str = ' '.join(cmd)
        self.phc2sys_terminal.clear()
        self.phc2sys_terminal.append(f"Running: {cmd_str}\n")

        self.phc2sys_process = QProcess()
        self.phc2sys_process.readyReadStandardOutput.connect(self._phc2sys_handle_stdout)
        self.phc2sys_process.readyReadStandardError.connect(self._phc2sys_handle_stderr)
        self.phc2sys_process.finished.connect(self._phc2sys_finished)
        self.is_phc2sys_running = True
        self.phc2sys_start_btn.setEnabled(False)
        self.phc2sys_stop_btn.setEnabled(True)
        self.phc2sys_process.start('bash', ['-c', cmd_str])

    def stop_phc2sys(self):
        if not self.is_phc2sys_running or not self.phc2sys_process:
            return
        self.phc2sys_terminal.append("\nStopping phc2sys...")
        self.phc2sys_process.terminate()
        if not self.phc2sys_process.waitForFinished(3000):
            self.phc2sys_process.kill()
            self.phc2sys_process.waitForFinished()
        self._phc2sys_reset()
        self.phc2sys_terminal.append("phc2sys stopped.")

    def _phc2sys_handle_stdout(self):
        data = self.phc2sys_process.readAllStandardOutput()
        text = bytes(data).decode('utf-8', errors='replace')
        self.phc2sys_terminal.insertPlainText(text)
        _trim_terminal(self.phc2sys_terminal)
        self.phc2sys_terminal.ensureCursorVisible()
        self._phc2sys_parse_output(text)

    def _phc2sys_handle_stderr(self):
        data = self.phc2sys_process.readAllStandardError()
        text = bytes(data).decode('utf-8', errors='replace')
        self.phc2sys_terminal.insertPlainText(text)
        _trim_terminal(self.phc2sys_terminal)
        self.phc2sys_terminal.ensureCursorVisible()
        self._phc2sys_parse_output(text)

    def _phc2sys_parse_output(self, text):
        # phc2sys offset output: "offset -42" or "rms 42 max 87"
        m = re.search(r'rms\s+(\d+)\s+max\s+(\d+)', text)
        if m:
            self._phc2sys_offset = int(m.group(2))
        else:
            m = re.search(r'offset\s+(-?\d+)', text)
            if m:
                self._phc2sys_offset = abs(int(m.group(1)))
        self._update_phc2sys_status()

    def _update_phc2sys_status(self):
        offset = self._phc2sys_offset
        if offset is None:
            color = 'gray'
            label = '\u2014'
        elif offset <= 10:
            color = '#4caf50'
            label = f'{offset} ns'
        elif offset <= 50:
            color = '#ffc107'
            label = f'{offset} ns'
        else:
            color = '#f44336'
            label = f'{offset} ns'

        self.phc2sys_light.setStyleSheet(
            f'background-color: {color}; border-radius: 10px;')
        if offset is not None:
            self.phc2sys_offset_label.setText(f'Offset: {label}')
            self.phc2sys_state_label.setText(label)
        else:
            self.phc2sys_offset_label.setText('Offset: \u2014')
            self.phc2sys_state_label.setText('\u2014')

    def _phc2sys_reset(self):
        self.is_phc2sys_running = False
        self.phc2sys_process = None
        self._phc2sys_offset = None
        self.phc2sys_start_btn.setEnabled(self._can_start_phc2sys())
        self.phc2sys_stop_btn.setEnabled(False)
        self._update_phc2sys_status()

    def _phc2sys_finished(self, exit_code, exit_status):
        self._phc2sys_reset()
        if exit_code == 0:
            self.phc2sys_terminal.append("phc2sys completed.")
        else:
            self.phc2sys_terminal.append(f"phc2sys exited with code: {exit_code}")

    def _phc2sys_check_sync(self):
        """Enable/disable phc2sys start button based on PTP sync state."""
        can_start = self._can_start_phc2sys()
        if not self.is_phc2sys_running:
            self.phc2sys_start_btn.setEnabled(can_start)
            if not can_start:
                self.phc2sys_start_btn.setToolTip(
                    'PTP must be running and in SLAVE/MASTER state first.')
            else:
                self.phc2sys_start_btn.setToolTip('')

    # ── PTP4L ────────────────────────────────────────────────────

    def open_ptp4l_config(self):
        ptp4l_path = "/etc/linuxptp/ptp4l.conf"
        if Path(ptp4l_path).exists():
            self.terminal_output.append(f"Opening config: {ptp4l_path}")
            QProcess.startDetached("xdg-open", [ptp4l_path])
        else:
            self.terminal_output.append(f"Config not found: {ptp4l_path}")

    def open_ptp4l_editor(self):
        ptp4l_path = "/etc/linuxptp/ptp4l.conf"
        if not Path(ptp4l_path).exists():
            self.terminal_output.append(f"Config not found: {ptp4l_path}")
            return

        from core.ptp4l_config import PTP4LConfig
        from ui.ptp4l_config_dialog import PTP4LConfigDialog

        try:
            cfg = PTP4LConfig()
            cfg.load(ptp4l_path)
            dialog = PTP4LConfigDialog(cfg, self)
            if dialog.exec() == PTP4LConfigDialog.DialogCode.Accepted:
                self.terminal_output.append("PTP4L config saved.")
        except Exception as e:
            self.terminal_output.append(f"Error loading PTP4L config: {e}")
            import traceback as tb
            self.terminal_output.append(tb.format_exc())
