from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QTextEdit, QGroupBox)
from PyQt6.QtCore import QProcess, QProcessEnvironment
from PyQt6.QtGui import QFont
import os
import pwd
import traceback

class AES67Tab(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.process = None
        self.is_running = False

    def init_ui(self):
        layout = QVBoxLayout()

        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start pipewire-aes67")
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
        self.start_btn.clicked.connect(self.start_aes67)
        button_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop pipewire-aes67")
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
        self.stop_btn.clicked.connect(self.stop_aes67)
        button_layout.addWidget(self.stop_btn)

        config_group = QGroupBox("Configuration")
        config_layout = QHBoxLayout()
        self.config_btn = QPushButton("Config öffnen")
        self.config_btn.clicked.connect(self.open_config)
        config_layout.addWidget(self.config_btn)
        config_layout.addStretch()
        config_group.setLayout(config_layout)

        layout.addLayout(button_layout)
        layout.addWidget(config_group)

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
        layout.addWidget(QLabel("AES67 Output:"))
        layout.addWidget(self.terminal_output)

        self.setLayout(layout)

    def start_aes67(self):
        try:
            self.terminal_output.clear()
            self.terminal_output.append("Starting pipewire-aes67 (mit System-Clock)...")

            user_home = self._get_user_home()
            uid = int(os.getenv('SUDO_UID', str(os.getuid())))
            runtime_dir = f"/run/user/{uid}"
            bus_address = f"unix:path={runtime_dir}/bus"

            # Create temp config that disables PHC access
            # App läuft als root, kann /dev/ptp0 öffnen, aber PHC liefert Timestamp 0.
            # System-User kriegt Permission denied → Fallback auf System-Clock (funktioniert).
            orig_config = os.path.join(user_home, ".config/pipewire/pipewire-aes67.conf")
            tmp_config = "/dev/shm/pipewire-aes67-override.conf"
            with open(orig_config, "r") as f:
                config_content = f.read()
            # clock.interface auskommentieren → kein PHC-Zugriff → System-Clock wird verwendet
            config_content = config_content.replace(
                "            clock.interface = \"enx6c6e0709c56d\"",
                "            #clock.interface = \"enx6c6e0709c56d\""
            )
            with open(tmp_config, "w") as f:
                f.write(config_content)

            env = QProcessEnvironment.systemEnvironment()
            env.insert("HOME", user_home)
            env.insert("XDG_RUNTIME_DIR", runtime_dir)
            env.insert("DBUS_SESSION_BUS_ADDRESS", bus_address)

            self.terminal_output.append(f"Using XDG_RUNTIME_DIR={runtime_dir}")

            self.process = QProcess()
            self.process.setProcessEnvironment(env)
            self.process.readyReadStandardOutput.connect(self.handle_stdout)
            self.process.readyReadStandardError.connect(self.handle_stderr)
            self.process.finished.connect(self.process_finished)

            self.process.start("pipewire-aes67", ["-c", tmp_config, "-v"])
            self.is_running = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)

        except Exception as e:
            self.terminal_output.append(f"Error: {str(e)}")
            self.terminal_output.append(traceback.format_exc())

    def stop_aes67(self):
        if self.is_running and self.process:
            self.terminal_output.append("Stopping pipewire-aes67...")
            self.process.terminate()
            if not self.process.waitForFinished(3000):
                self.terminal_output.append("Process did not terminate gracefully, forcing...")
                self.process.kill()
                self.process.waitForFinished()
            self.is_running = False
            self.process = None
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.terminal_output.append("pipewire-aes67 stopped.")

    def open_config(self):
        home = self._get_user_home()
        config_path = os.path.join(home, ".config/pipewire/pipewire-aes67.conf")
        if os.path.exists(config_path):
            self.terminal_output.append(f"Opening config: {config_path}")
            QProcess.startDetached("xdg-open", [config_path])
        else:
            self.terminal_output.append(
                f"Config nicht gefunden unter: {config_path}"
            )
            self.terminal_output.append(
                "Lege eine Config-Datei an oder kopiere sie von /usr/share/pipewire/pipewire-aes67.conf"
            )

    def _get_user_home(self):
        sudo_user = os.environ.get('SUDO_USER')
        if sudo_user:
            return pwd.getpwnam(sudo_user).pw_dir
        return os.path.expanduser("~")

    def handle_stdout(self):
        process = self.sender()
        if process is None:
            process = self.process
        if process is None:
            return
        data = process.readAllStandardOutput()
        stdout = bytes(data).decode('utf-8', errors='replace')
        self.terminal_output.insertPlainText(stdout)
        self.terminal_output.ensureCursorVisible()

    def handle_stderr(self):
        process = self.sender()
        if process is None:
            process = self.process
        if process is None:
            return
        data = process.readAllStandardError()
        stderr = bytes(data).decode('utf-8', errors='replace')
        self.terminal_output.insertPlainText(stderr)
        self.terminal_output.ensureCursorVisible()

    def process_finished(self, exit_code, exit_status):
        self.is_running = False
        self.process = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.terminal_output.append(f"pipewire-aes67 exited with code {exit_code}")
