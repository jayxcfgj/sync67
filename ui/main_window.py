from PyQt6.QtWidgets import QMainWindow, QTabWidget
from ui.ptp_tab import PTPTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("sync67")
        self.setGeometry(200, 200, 800, 600)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.ptp_tab = PTPTab()
        self.tabs.addTab(self.ptp_tab, "PTP")
