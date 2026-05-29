from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QComboBox, QPushButton, QTextEdit, QGroupBox,
                               QFormLayout, QScrollArea)
from PyQt6.QtCore import Qt, QProcess, QSettings
from PyQt6.QtGui import QFont
import os
import subprocess
import re
import shutil
import traceback
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

    def init_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)

        interface_group = QGroupBox("Network Interface")
        interface_layout = QFormLayout()

        self.interface_combo = QComboBox()
        self.interface_combo.setMinimumWidth(200)
        interface_layout.addRow("Interface:", self.interface_combo)

        self.settings_btn = QPushButton("Start Options")
        self.settings_btn.clicked.connect(self.open_settings)
        interface_layout.addRow("", self.settings_btn)

        interface_group.setLayout(interface_layout)
        layout.addWidget(interface_group)

        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("START PTP")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.start_btn.clicked.connect(self.start_ptp)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("STOP PTP")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_ptp)
        button_layout.addWidget(self.stop_btn)

        button_layout.addWidget(QLabel(" Sync Status:"))
        self.status_light = QLabel()
        self.status_light.setFixedSize(24, 24)
        self.status_light.setStyleSheet("background-color: gray; border-radius: 12px;")
        button_layout.addWidget(self.status_light)
        self.state_label = QLabel("")
        self.state_label.setStyleSheet("color: #cccccc; font-size: 12px; padding-left: 4px;")
        self.state_label.setMinimumWidth(100)
        button_layout.addWidget(self.state_label)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        ptp4l_group = QGroupBox("PTP4L Configuration")
        ptp4l_layout = QHBoxLayout(ptp4l_group)
        self.ptp4l_open_btn = QPushButton("Open Config")
        self.ptp4l_open_btn.clicked.connect(self.open_ptp4l_config)
        self.ptp4l_edit_btn = QPushButton("PTP4L Config Editor")
        self.ptp4l_edit_btn.clicked.connect(self.open_ptp4l_editor)
        ptp4l_layout.addWidget(self.ptp4l_open_btn)
        ptp4l_layout.addWidget(self.ptp4l_edit_btn)
        ptp4l_layout.addStretch()
        layout.addWidget(ptp4l_group)

        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setFont(QFont("Courier New", 10))
        self.terminal_output.setStyleSheet("""
            QTextEdit {
                background-color: #000000;
                color: #E0E0E0;
                border: 1px solid #333333;
            }
        """)
        layout.addWidget(QLabel("PTP Output:"))
        layout.addWidget(self.terminal_output)

        scroll.setWidget(content)
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.addWidget(scroll)

        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)

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
                commands.append("sudo phc_ctl /dev/ptp0 set")
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

    def run_commands(self, commands, iface):
        self.command_queue = commands.copy()
        self.iface = iface
        self.run_next_command()

    def run_next_command(self):
        cmd = self.command_queue.pop(0)
        self.terminal_output.append(f"Running: {cmd}")
        self.process.start("bash", ["-c", cmd])

    def handle_stdout(self):
        process = self.sender()
        if process is None:
            process = self.process
        data = process.readAllStandardOutput()
        stdout = bytes(data).decode('utf-8', errors='replace')
        self.terminal_output.insertPlainText(stdout)
        self.terminal_output.ensureCursorVisible()
        self.parse_ptp_output(stdout)

    def handle_stderr(self):
        process = self.sender()
        if process is None:
            process = self.process
        data = process.readAllStandardError()
        stderr = bytes(data).decode('utf-8', errors='replace')
        self.terminal_output.insertPlainText(stderr)
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
        self.terminal_output.append(f"Running: {ptp_cmd}")
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
