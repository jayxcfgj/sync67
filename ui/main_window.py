from PyQt6.QtWidgets import QMainWindow, QTabWidget
from ui.ptp_tab import PTPTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("sync67")
        self.setGeometry(100, 100, 800, 600)
        
        # Create tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Add PTP tab
        self.ptp_tab = PTPTab()
        self.tabs.addTab(self.ptp_tab, "PTP")