from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QCheckBox, QPushButton, QGroupBox, QFormLayout,
                               QScrollArea, QWidget)
from PyQt6.QtCore import Qt, QSettings

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PTP Start Options")
        self.setMinimumSize(450, 500)
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
        self.gro_check.setToolTip("Prevents the NIC from coalescing received packets.\n"
            "Reduces latency and is recommended for PTP timestamp accuracy.")
        self.gso_check = QCheckBox("Disable Generic Segmentation Offset (gso off)")
        self.gso_check.setToolTip("Prevents the NIC from segmenting large packets.\n"
            "Avoids PTP frames being delayed behind segmented bulk traffic.")
        self.tso_check = QCheckBox("Disable TCP Segmentation Offload (tso off)")
        self.tso_check.setToolTip("Prevents the NIC from offloading TCP segmentation.\n"
            "Same rationale as GSO – keeps PTP frames from being queued.")
        self.sg_check = QCheckBox("Disable Scatter-Gather (sg off)")
        self.sg_check.setToolTip("Disables scatter-gather DMA.\n"
            "Required on Intel i210/i211 NICs where SG interferes\n"
            "with PTP TX timestamp delivery.")
        self.rx_usecs_check = QCheckBox("Set rx-usecs to 0 (no interrupt coalescing)")
        self.rx_usecs_check.setToolTip("Sets NIC interrupt coalescing to 0.\n"
            "Every received packet triggers an immediate interrupt,\n"
            "minimizing latency. Recommended for PTP and audio.")
        self.multicast_check = QCheckBox("Enable Multicast (multicast on)")
        self.multicast_check.setToolTip("Enables multicast reception on the interface.\n"
            "PTP uses multicast MAC addresses for Sync and Announce.\n"
            "Must be enabled for PTP to work.")
        self.phc_reset_check = QCheckBox("Reset PHC clock to system time (phc_ctl set)")
        self.phc_reset_check.setToolTip("Resets the PTP Hardware Clock to system time.\n"
            "Many NICs (especially USB adapters) start PHC at epoch 0\n"
            "after boot, causing a multi-year PTP offset.\n"
            "Safe to always enable.")
        self.mcast_event_check = QCheckBox("Join PTP event multicast (01:1B:19:00:00:00)")
        self.mcast_event_check.setToolTip("Joins the PTP event multicast group.\n"
            "Some USB NIC drivers (ASIX AX88xxx) do not auto-join\n"
            "PTP multicast groups. Harmless on other NICs.")
        self.mcast_pdelay_check = QCheckBox("Join PTP peer delay multicast (01:80:C2:00:00:0E)")
        self.mcast_pdelay_check.setToolTip("Joins the PTP peer delay multicast group.\n"
            "Required for peer delay measurement on some USB NICs.\n"
            "Same rationale as event multicast.")
        self.wol_check = QCheckBox("Disable Wake-on-LAN (wol d)")
        self.wol_check.setToolTip("Disables Wake-on-LAN.\n"
            "On Intel i210/i211 NICs, WoL shares PHY resources with\n"
            "PTP TX timestamping. With WoL on, timestamps may not\n"
            "reach the app, causing 'master sync timeout'.")

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

        # ── System Clock Services ──────────────────────────────────
        services_group = QGroupBox("System Clock Services (stopped during PTP use, NOT restarted after stop)")
        services_layout = QFormLayout()

        self.timesyncd_check = QCheckBox("Stop systemd-timesyncd")
        self.timesyncd_check.setToolTip(
            "Stops systemd-timesyncd (NTP client).\n"
            "Competes with phc2sys for CLOCK_REALTIME.\n"
            "Note: Service is NOT automatically restarted when PTP stops.\n"
            "It will be available again after reboot."
        )
        self.timesyncd_check.setChecked(True)

        self.chronyd_check = QCheckBox("Stop chronyd")
        self.chronyd_check.setToolTip(
            "Stops chronyd (NTP client).\n"
            "Alternative to systemd-timesyncd. Can step or slew CLOCK_REALTIME.\n"
            "Note: Service is NOT automatically restarted when PTP stops.\n"
            "It will be available again after reboot."
        )
        self.chronyd_check.setChecked(True)

        self.ntpd_check = QCheckBox("Stop ntpd")
        self.ntpd_check.setToolTip(
            "Stops ntpd (NTP daemon).\n"
            "Classic NTP implementation. Can step CLOCK_REALTIME.\n"
            "Note: Service is NOT automatically restarted when PTP stops.\n"
            "It will be available again after reboot."
        )
        self.ntpd_check.setChecked(True)

        self.sys_time_wait_check = QCheckBox("Stop systemd-time-wait-sync")
        self.sys_time_wait_check.setToolTip(
            "Stops systemd-time-wait-sync.\n"
            "Waits for initial clock sync at boot. Can apply\n"
            "a one-time step to CLOCK_REALTIME.\n"
            "Note: Service is NOT automatically restarted when PTP stops.\n"
            "It will be available again after reboot."
        )
        self.sys_time_wait_check.setChecked(True)

        services_layout.addRow(self.timesyncd_check)
        services_layout.addRow(self.chronyd_check)
        services_layout.addRow(self.ntpd_check)
        services_layout.addRow(self.sys_time_wait_check)

        services_group.setLayout(services_layout)
        content_layout.addWidget(services_group)
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
        settings.setValue("stop_timesyncd", self.timesyncd_check.isChecked())
        settings.setValue("stop_chronyd", self.chronyd_check.isChecked())
        settings.setValue("stop_ntpd", self.ntpd_check.isChecked())
        settings.setValue("stop_sys_time_wait", self.sys_time_wait_check.isChecked())

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
        self.timesyncd_check.setChecked(settings.value("stop_timesyncd", True, type=bool))
        self.chronyd_check.setChecked(settings.value("stop_chronyd", True, type=bool))
        self.ntpd_check.setChecked(settings.value("stop_ntpd", True, type=bool))
        self.sys_time_wait_check.setChecked(settings.value("stop_sys_time_wait", True, type=bool))