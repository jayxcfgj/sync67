from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                               QComboBox, QPushButton, QTextEdit, QGroupBox,
                               QFormLayout)
from PyQt6.QtCore import Qt, QProcess, QSettings
from PyQt6.QtGui import QFont
import subprocess
import re

class PTPTab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.load_interfaces()
        self.ptp_process = None
        self.is_ptp_running = False
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Interface selection group
        interface_group = QGroupBox("Network Interface")
        interface_layout = QFormLayout()
        
        self.interface_combo = QComboBox()
        self.interface_combo.setMinimumWidth(200)
        interface_layout.addRow("Interface:", self.interface_combo)
        
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.clicked.connect(self.open_settings)
        interface_layout.addRow("", self.settings_btn)
        
        interface_group.setLayout(interface_layout)
        layout.addWidget(interface_group)
        
        # Control buttons
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
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # Terminal output
        self.terminal_output = QTextEdit()
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setFont(QFont("Courier New", 10))
        self.terminal_output.setStyleSheet("""
            QTextEdit {
                background-color: #000000;
                color: #00FF00;
                border: 1px solid #333333;
            }
        """)
        layout.addWidget(QLabel("PTP Output:"))
        layout.addWidget(self.terminal_output)
        
        self.setLayout(layout)
        
        # Process for running commands
        self.process = QProcess()
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self.process_finished)
        
    def load_interfaces(self):
        """Get list of network interfaces"""
        try:
            # Use ip link to get interfaces
            result = subprocess.run(['ip', 'link', 'show'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Parse output to get interface names
                # Pattern: [number]: <interface>: <flags>...
                interfaces = re.findall(r'^\d+: (\w+):', result.stdout, re.MULTILINE)
                # Filter out loopback
                interfaces = [iface for iface in interfaces if iface != 'lo']
                self.interface_combo.addItems(interfaces)
            else:
                self.interface_combo.addItem("Error loading interfaces")
        except Exception as e:
            self.interface_combo.addItem(f"Error: {str(e)}")
            
    def open_settings(self):
        """Open settings dialog"""
        from ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self)
        dialog.exec()
        
    def start_ptp(self):
        """Start PTP process with selected interface"""
        iface = self.interface_combo.currentText()
        if not iface or iface.startswith("Error"):
            self.terminal_output.append("Please select a valid network interface")
            return
            
        # Clear terminal
        self.terminal_output.clear()
        self.terminal_output.append(f"Starting PTP on interface {iface}...")
        
        # Preemptively get sudo rights
        self.terminal_output.append("Requesting sudo privileges...")
        sudo_process = QProcess()
        sudo_process.start("sudo", ["-v"])
        sudo_process.waitForFinished(-1)
        if sudo_process.exitCode() != 0:
            self.terminal_output.append("Failed to obtain sudo privileges")
            return
        
        # Get settings
        settings = QSettings("sync67", "ptp_settings")
        gro_off = settings.value("gro_off", True, type=bool)
        gso_off = settings.value("gso_off", True, type=bool)
        tso_off = settings.value("tso_off", True, type=bool)
        sg_off = settings.value("sg_off", True, type=bool)
        rx_usecs_0 = settings.value("rx_usecs_0", True, type=bool)
        multicast_on = settings.value("multicast_on", True, type=bool)
        
        # Build ethtool/ip commands
        commands = []
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
        if multicast_on:
            commands.append(f"sudo ip link set {iface} multicast on")
            
        # Run configuration commands first
        self.run_commands(commands, iface)
        
        
    def run_commands(self, commands, iface):
        """Run a list of commands sequentially, then start ptp4l"""
        self.command_queue = commands.copy()
        self.iface = iface
        self.run_next_command()
        
    def run_next_command(self):
        """Run the next command in queue"""
        cmd = self.command_queue.pop(0)
        self.terminal_output.append(f"Running: {cmd}")
        self.process.start("bash", ["-c", cmd])
        
    def handle_stdout(self):
        """Handle standard output from process"""
        data = self.process.readAllStandardOutput()
        stdout = bytes(data).decode('utf-8', errors='replace')
        self.terminal_output.insertPlainText(stdout)
        self.terminal_output.ensureCursorVisible()
        
    def handle_stderr(self):
        """Handle standard error from process"""
        data = self.process.readAllStandardError()
        stderr = bytes(data).decode('utf-8', errors='replace')
        self.terminal_output.insertPlainText(stderr)
        self.terminal_output.ensureCursorVisible()
        
    def process_finished(self, exit_code, exit_status):
        """Handle process finished"""
        self.terminal_output.append(f"\nProcess finished with exit code: {exit_code}")
        # If this was a config command, run next one
        if self.command_queue:
            self.run_next_command()
        else:
            # ptp4l process finished (either completed or was stopped)
            self.is_ptp_running = False
            self.ptp_process = None
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            if exit_code == 0:
                self.terminal_output.append("PTP process completed successfully.")
            else:
                self.terminal_output.append(f"PTP process exited with code: {exit_code}")

    def stop_ptp(self):
        """Stop the PTP process"""
        if self.is_ptp_running and self.ptp_process:
            self.terminal_output.append("Stopping PTP...")
            self.ptp_process.terminate()
            # Wait a bit for graceful termination
            if not self.ptp_process.waitForFinished(3000):  # 3 seconds timeout
                self.terminal_output.append("PTP did not terminate gracefully, forcing...")
                self.ptp_process.kill()
                self.ptp_process.waitForFinished()
            self.is_ptp_running = False
            self.ptp_process = None
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.terminal_output.append("PTP stopped.")