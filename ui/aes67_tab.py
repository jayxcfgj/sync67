from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QTextEdit, QGroupBox, QCheckBox)
from PyQt6.QtCore import QProcess, QProcessEnvironment
from PyQt6.QtGui import QFont
import os
import pwd
import shutil
import traceback

from core.aes67_config import AES67Config


class AES67Tab(QWidget):
    def __init__(self):
        super().__init__()
        self.config = None
        self.process = None
        self.is_running = False
        self._init_config()
        self.init_ui()

    def _init_config(self):
        user_home = self._get_user_home()
        self.config_path = os.path.join(user_home, ".config/pipewire/pipewire-aes67.conf")
        self.default_config_path = "/usr/share/pipewire/pipewire-aes67.conf"
        try:
            self.config = AES67Config()
            self.config.load(self.config_path)
        except FileNotFoundError:
            self.config = None

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
        self.config_btn = QPushButton("Open Config")
        self.config_btn.clicked.connect(self.open_config)
        config_layout.addWidget(self.config_btn)

        self.editor_btn = QPushButton("AES67 Config Editor")
        self.editor_btn.clicked.connect(self.open_config_editor)
        config_layout.addWidget(self.editor_btn)

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
                color: #E0E0E0;
                border: 1px solid #333333;
            }
        """)
        output_header = QHBoxLayout()
        output_header.addWidget(QLabel("AES67 Output:"))
        output_header.addStretch()
        self.verbose_cb = QCheckBox("Verbose output (-v)")
        output_header.addWidget(self.verbose_cb)
        layout.addLayout(output_header)
        layout.addWidget(self.terminal_output)

        self.setLayout(layout)

    def start_aes67(self):
        try:
            self.terminal_output.clear()

            user_home = self._get_user_home()
            uid = int(os.getenv('SUDO_UID', str(os.getuid())))
            runtime_dir = f"/run/user/{uid}"
            bus_address = f"unix:path={runtime_dir}/bus"

            # Config existence check → copy default if missing
            if not os.path.exists(self.config_path):
                if os.path.exists(self.default_config_path):
                    shutil.copy(self.default_config_path, self.config_path)
                    self.terminal_output.append(
                        "No user config found. Default copied to:\n"
                        f"  {self.config_path}"
                    )
                else:
                    self.terminal_output.append(
                        "ERROR: Neither user config nor default config found."
                    )
                    return
                self._init_config()

            # Use the user config directly (editor handles any overrides)
            use_config = self.config_path

            # Check system-clock override in config
            if self.config:
                clock_intf = self.config.get(
                    'context.objects', 0, 'args', 'clock.interface'
                )
                if clock_intf:
                    self.terminal_output.append(
                        f"Starte pipewire-aes67 mit Interface-Clock {clock_intf}..."
                    )
                else:
                    self.terminal_output.append(
                        "Starte pipewire-aes67 (System-Clock)..."
                    )
            else:
                self.terminal_output.append("Starte pipewire-aes67...")

            env = QProcessEnvironment.systemEnvironment()
            env.insert("HOME", user_home)
            env.insert("XDG_RUNTIME_DIR", runtime_dir)
            env.insert("DBUS_SESSION_BUS_ADDRESS", bus_address)

            self.terminal_output.append(f"Config: {use_config}")
            self.terminal_output.append(f"XDG_RUNTIME_DIR={runtime_dir}")

            self.process = QProcess()
            self.process.setProcessEnvironment(env)
            self.process.readyReadStandardOutput.connect(self.handle_stdout)
            self.process.readyReadStandardError.connect(self.handle_stderr)
            self.process.finished.connect(self.process_finished)

            args = ["-c", use_config]
            if self.verbose_cb.isChecked():
                args.append("-v")
            self.process.start("pipewire-aes67", args)
            self.is_running = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.verbose_cb.setEnabled(False)

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
            self.verbose_cb.setEnabled(True)
            self.terminal_output.append("pipewire-aes67 stopped.")

    def open_config(self):
        if os.path.exists(self.config_path):
            self.terminal_output.append(f"Opening config: {self.config_path}")
            QProcess.startDetached("xdg-open", [self.config_path])
        else:
            self.terminal_output.append(
                f"Config not found at: {self.config_path}"
            )
            self.terminal_output.append(
                "Create a config file or copy it from\n"
                f"  {self.default_config_path}"
            )

    def open_config_editor(self):
        if not os.path.exists(self.config_path):
            if os.path.exists(self.default_config_path):
                shutil.copy(self.default_config_path, self.config_path)
                self.terminal_output.append("Default config copied.")
            else:
                self.terminal_output.append("No config found.")
                return
            self._init_config()

        if self.config is None:
            self._init_config()
        if self.config is None:
            self.terminal_output.append("Config could not be loaded.")
            return

        from ui.aes67_settings_dialog import AES67SettingsDialog
        dialog = AES67SettingsDialog(self.config, self)
        if dialog.exec() == AES67SettingsDialog.DialogCode.Accepted:
            self.terminal_output.append("Config saved via editor.")
            self._init_config()

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
        self.verbose_cb.setEnabled(True)
        self.terminal_output.append(f"pipewire-aes67 exited with code {exit_code}")
