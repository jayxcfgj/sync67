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
        self.gro_check.setToolTip("Prevents the NIC from coalescing received packets. "
            "Reduces latency and is recommended for PTP timestamp accuracy.")
        self.gso_check = QCheckBox("Disable Generic Segmentation Offset (gso off)")
        self.gso_check.setToolTip("Prevents the NIC from segmenting large packets in hardware. "
            "Avoids PTP frames being delayed behind segmented bulk traffic.")
        self.tso_check = QCheckBox("Disable TCP Segmentation Offload (tso off)")
        self.tso_check.setToolTip("Prevents the NIC from offloading TCP segmentation. "
            "Same rationale as GSO – ensures PTP frames are not queued behind large segments.")
        self.sg_check = QCheckBox("Disable Scatter-Gather (sg off)")
        self.sg_check.setToolTip("Disables scatter-gather DMA. "
            "Required on some Intel i210/i211 NICs where SG interferes with PTP TX timestamp delivery. "
            "May increase CPU load slightly.")
        self.rx_usecs_check = QCheckBox("Set rx-usecs to 0 (no interrupt coalescing)")
        self.rx_usecs_check.setToolTip("Sets the NIC interrupt coalescing timer to 0. "
            "Every received packet triggers an immediate interrupt, minimizing latency. "
            "Recommended for PTP and real-time audio.")
        self.multicast_check = QCheckBox("Enable Multicast (multicast on)")
        self.multicast_check.setToolTip("Enables multicast reception on the interface. "
            "PTP uses multicast MAC addresses (01:1B:19:00:00:00) for Sync and Announce messages. "
            "Must be enabled for PTP to work.")
        self.phc_reset_check = QCheckBox("Reset PHC clock to system time (phc_ctl set)")
        self.phc_reset_check.setToolTip("Resets the PTP Hardware Clock (PHC) to the current system time. "
            "Many NICs (especially USB adapters) start their PHC at epoch 0 after boot, "
            "causing a multi-year offset that PTP cannot correct. "
            "Safe to always enable.")
        self.mcast_event_check = QCheckBox("Join PTP event multicast (01:1B:19:00:00:00)")
        self.mcast_event_check.setToolTip("Explicitly joins the PTP event multicast group. "
            "Some USB NIC drivers (e.g., ASIX AX88xxx) do not automatically join PTP multicast groups. "
            "Harmless on NICs that handle this correctly.")
        self.mcast_pdelay_check = QCheckBox("Join PTP peer delay multicast (01:80:C2:00:00:0E)")
        self.mcast_pdelay_check.setToolTip("Explicitly joins the PTP peer delay multicast group. "
            "Required for peer delay measurement on some USB NICs. Same rationale as the event multicast.")
        self.wol_check = QCheckBox("Disable Wake-on-LAN (wol d)")
        self.wol_check.setToolTip("Disables Wake-on-LAN. "
            "On Intel i210/i211 NICs, WoL shares PHY resources with PTP TX timestamping. "
            "When WoL is enabled, TX timestamps may not reach the application, "
            "causing 'master sync timeout' or 'delay timeout'.")

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