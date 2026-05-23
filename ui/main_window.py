from PyQt6.QtWidgets import QMainWindow, QTabWidget, QPushButton
from PyQt6.QtCore import Qt
from ui.ptp_tab import PTPTab
from ui.aes67_tab import AES67Tab
from ui.pipewire_tab import PipeWireTab
from ui.session_tab import SessionTab
from ui.about_dialog import AboutDialog

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("sync67")
        self.setGeometry(200, 200, 900, 700)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.ptp_tab = PTPTab()
        self.tabs.addTab(self.ptp_tab, "PTP")

        self.aes67_tab = AES67Tab()
        self.tabs.addTab(self.aes67_tab, "AES67")

        self.pipewire_tab = PipeWireTab()
        self.tabs.addTab(self.pipewire_tab, "PipeWire")

        self.session_tab = SessionTab(self.ptp_tab, self.aes67_tab, self.pipewire_tab)
        self.tabs.addTab(self.session_tab, "Session")

        # About-Button in der Tab-Leiste (rechts)
        about_btn = QPushButton("\u2139")
        about_btn.setFixedSize(28, 28)
        about_btn.setToolTip("About sync67")
        about_btn.clicked.connect(lambda: AboutDialog(self).exec())
        self.tabs.setCornerWidget(about_btn, Qt.Corner.TopRightCorner)
