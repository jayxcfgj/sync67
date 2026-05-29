from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QCheckBox, QPushButton, QGroupBox, QFormLayout,
                               QScrollArea, QWidget)
from PyQt6.QtCore import Qt, QSettings

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PTP Start Options")
        self.setMinimumSize(300, 200)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self.init_ui()
        self.load_settings()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Scroll area for settings content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        
        content = QWidget()
        content.setMinimumSize(0, 0)
        content_layout = QVBoxLayout(content)
        
        settings_group = QGroupBox("Interface Optimization Settings")
        settings_layout = QFormLayout()
        
        self.gro_check = QCheckBox("Disable Generic Receive Offset (gro off)")
        self.gso_check = QCheckBox("Disable Generic Segmentation Offset (gso off)")
        self.tso_check = QCheckBox("Disable TCP Segmentation Offload (tso off)")
        self.sg_check = QCheckBox("Disable Scatter-Gather (sg off)")
        self.rx_usecs_check = QCheckBox("Set rx-usecs to 0 (no interrupt coalescing)")
        self.multicast_check = QCheckBox("Enable Multicast (multicast on)")
        self.phc_reset_check = QCheckBox("Reset PHC clock to system time (phc_ctl set)")
        self.mcast_event_check = QCheckBox("Join PTP event multicast (01:1B:19:00:00:00)")
        self.mcast_pdelay_check = QCheckBox("Join PTP peer delay multicast (01:80:C2:00:00:0E)")
        self.wol_check = QCheckBox("Disable Wake-on-LAN (wol d)")

        # Set all to checked by default
        self.gro_check.setChecked(True)
        self.gso_check.setChecked(True)
        self.tso_check.setChecked(True)
        self.sg_check.setChecked(True)
        self.rx_usecs_check.setChecked(True)
        self.multicast_check.setChecked(True)
        self.phc_reset_check.setChecked(True)
        self.mcast_event_check.setChecked(True)
        self.mcast_pdelay_check.setChecked(True)
        self.wol_check.setChecked(True)

        settings_layout.addRow(self.gro_check)
        settings_layout.addRow(self.gso_check)
        settings_layout.addRow(self.tso_check)
        settings_layout.addRow(self.sg_check)
        settings_layout.addRow(self.rx_usecs_check)
        settings_layout.addRow(self.multicast_check)
        settings_layout.addRow(self.phc_reset_check)
        settings_layout.addRow(self.mcast_event_check)
        settings_layout.addRow(self.mcast_pdelay_check)
        settings_layout.addRow(self.wol_check)

        settings_group.setLayout(settings_layout)
        content_layout.addWidget(settings_group)
        content_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Buttons
        button_layout = QHBoxLayout()
        self.ok_btn = QPushButton("OK")
        self.cancel_btn = QPushButton("Cancel")

        self.ok_btn.clicked.connect(self.accept_settings)
        self.cancel_btn.clicked.connect(self.reject)

        button_layout.addWidget(self.ok_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def accept_settings(self):
        """Save settings and accept"""
        self.save_settings()
        self.accept()

    def save_settings(self):
        """Save checkbox states to settings"""
        settings = QSettings("sync67", "ptp_settings")
        settings.setValue("gro_off", self.gro_check.isChecked())
        settings.setValue("gso_off", self.gso_check.isChecked())
        settings.setValue("tso_off", self.tso_check.isChecked())
        settings.setValue("sg_off", self.sg_check.isChecked())
        settings.setValue("rx_usecs_0", self.rx_usecs_check.isChecked())
        settings.setValue("multicast_on", self.multicast_check.isChecked())
        settings.setValue("phc_reset", self.phc_reset_check.isChecked())
        settings.setValue("mcast_event", self.mcast_event_check.isChecked())
        settings.setValue("mcast_pdelay", self.mcast_pdelay_check.isChecked())
        settings.setValue("wol_d", self.wol_check.isChecked())

    def load_settings(self):
        """Load checkbox states from settings"""
        settings = QSettings("sync67", "ptp_settings")
        self.gro_check.setChecked(settings.value("gro_off", True, type=bool))
        self.gso_check.setChecked(settings.value("gso_off", True, type=bool))
        self.tso_check.setChecked(settings.value("tso_off", True, type=bool))
        self.sg_check.setChecked(settings.value("sg_off", True, type=bool))
        self.rx_usecs_check.setChecked(settings.value("rx_usecs_0", True, type=bool))
        self.multicast_check.setChecked(settings.value("multicast_on", True, type=bool))
        self.phc_reset_check.setChecked(settings.value("phc_reset", True, type=bool))
        self.mcast_event_check.setChecked(settings.value("mcast_event", True, type=bool))
        self.mcast_pdelay_check.setChecked(settings.value("mcast_pdelay", True, type=bool))
        self.wol_check.setChecked(settings.value("wol_d", True, type=bool))