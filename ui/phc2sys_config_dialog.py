"""phc2sys Config Dialog – 4 tabs, Persist via /etc/linuxptp/phc2sys.conf + QSettings."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QCheckBox, QComboBox, QPushButton,
    QWidget, QScrollArea, QMessageBox
)
from PyQt6.QtCore import Qt, QSettings

import os

from core.phc2sys_config import Phc2sysConfig, CONFIG_PATH
from core.phc2sys_config_meta import BUILTIN_DEFAULTS


_PHC_CACHE = None


def _load_phc_devices():
    global _PHC_CACHE
    if _PHC_CACHE is not None:
        return _PHC_CACHE
    devices = []
    try:
        for entry in os.listdir('/sys/class/ptp/'):
            if entry.startswith('ptp'):
                devices.append(f'/dev/{entry}')
    except Exception:
        pass
    _PHC_CACHE = sorted(devices)
    return _PHC_CACHE


class Phc2sysConfigDialog(QDialog):
    def __init__(self, config: Phc2sysConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle('phc2sys Configuration')
        self.setMinimumSize(380, 250)
        self.resize(480, 380)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self._qset = QSettings('sync67', 'phc2sys_settings')
        self._widgets = {}
        self._init_ui()

    # ── Helpers ──────────────────────────────────────────────────

    def _default_text(self, default):
        if isinstance(default, bool):
            return 'Default: checked' if default else 'Default: unchecked'
        return f'Default: {default}' if default != '' else 'Default: (empty)'

    def _config_default(self, key):
        return BUILTIN_DEFAULTS.get(key, 0)

    def _make_scroll(self, layout):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setMinimumSize(0, 0)
        content.setLayout(layout)
        scroll.setWidget(content)
        return scroll

    def _add_row(self, layout, label_text, widget, default):
        container = QWidget()
        cl = QVBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(2)
        cl.addWidget(QLabel(label_text))
        cl.addWidget(widget)
        dl = QLabel(self._default_text(default))
        dl.setStyleSheet('color: gray; font-size: 10px;')
        cl.addWidget(dl)
        layout.addWidget(container)

    def _reg(self, key, widget, default, label='', tooltip='',
             choices=None, minv=None, maxv=None, step=None):
        widget.setToolTip(tooltip)
        if isinstance(widget, QDoubleSpinBox):
            if minv is not None: widget.setMinimum(minv)
            if maxv is not None: widget.setMaximum(maxv)
            if step is not None: widget.setSingleStep(step)
            widget.setDecimals(1)
        elif isinstance(widget, QSpinBox):
            if minv is not None: widget.setMinimum(minv)
            if maxv is not None: widget.setMaximum(maxv)
            if step is not None: widget.setSingleStep(step)
        elif isinstance(widget, QComboBox) and choices:
            widget.clear()
            widget.addItems(choices)
        self._widgets[key] = (widget, default)

    def _widget_value(self, key):
        w, _ = self._widgets.get(key, (None, None))
        if w is None:
            return None
        if isinstance(w, QCheckBox):
            return w.isChecked()
        if isinstance(w, (QSpinBox, QDoubleSpinBox)):
            return w.value()
        if isinstance(w, QComboBox):
            return w.currentText()
        if isinstance(w, QLineEdit):
            return w.text()
        return None

    # ── Config / QSettings helpers ───────────────────────────────

    def _load_widget(self, key, cfg_key=None, store='config'):
        w, default = self._widgets.get(key, (None, None))
        if w is None:
            return
        if store == 'config':
            val = self.config.get(cfg_key or key)
            if val is None:
                val = self._config_default(cfg_key or key)
        else:
            val = self._qset.value(key, default)
        self._set_widget_value(w, val)

    def _save_widget(self, key, cfg_key=None, store='config'):
        val = self._widget_value(key)
        if store == 'config':
            self.config.set(cfg_key or key, val)
        else:
            self._qset.setValue(key, val)

    @staticmethod
    def _set_widget_value(w, val):
        if isinstance(w, QCheckBox):
            w.setChecked(bool(val) if not isinstance(val, bool) else val)
        elif isinstance(w, QSpinBox):
            w.setValue(int(val))
        elif isinstance(w, QDoubleSpinBox):
            w.setValue(float(val))
        elif isinstance(w, QComboBox):
            idx = w.findText(str(val))
            if idx >= 0:
                w.setCurrentIndex(idx)
            elif isinstance(val, int) and val < w.count():
                w.setCurrentIndex(val)
        elif isinstance(w, QLineEdit):
            w.setText(str(val) if val else '')

    # ── UI ───────────────────────────────────────────────────────

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self._create_quick_tab()
        self._create_servo_tab()
        self._create_advanced_tab()
        self._create_manual_tab()
        layout.addWidget(self.tabs)

        btn_layout = QHBoxLayout()
        reset_btn = QPushButton('Reset to Defaults')
        reset_btn.clicked.connect(self._on_reset)
        btn_layout.addWidget(reset_btn)
        btn_layout.addStretch()
        save_btn = QPushButton('Save')
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    # ── Tabs ─────────────────────────────────────────────────────

    def _create_quick_tab(self):
        lo = QVBoxLayout()
        lo.setSpacing(2)

        self._reg('auto_mode', QCheckBox(), True,
                  label='Auto mode (-a)',
                  tooltip='Automatically read clocks from running ptp4l\n'
                          'and follow port state changes.\n'
                          'When OFF, manual source/sink must be configured.')
        self._load_widget('auto_mode', store='qset')
        self._add_row(lo, 'Auto mode (-a)', self._widgets['auto_mode'][0], True)

        self._reg('sync_realtime', QComboBox(), 'single (-r)',
                  choices=['off', 'single (-r)', 'double (-rr)'],
                  tooltip='-r: synchronize system clock to PHC.\n'
                          '-rr: also consider system clock as time source.')
        self._load_widget('sync_realtime', store='qset')
        self._add_row(lo, 'Sync system clock', self._widgets['sync_realtime'][0], 'single (-r)')

        self._reg('wait_ptp4l', QCheckBox(), True,
                  label='Wait for ptp4l (-w)',
                  tooltip='Wait until ptp4l is synchronized.\n'
                          'Auto-learns UTC offset from ptp4l.\n'
                          'Only in manual mode.')
        self._load_widget('wait_ptp4l', store='qset')
        self._add_row(lo, 'Wait for ptp4l (-w)', self._widgets['wait_ptp4l'][0], True)

        self._reg('update_interval', QDoubleSpinBox(), 1.0,
                  label='Update interval (seconds)',
                  minv=0.01, maxv=10.0, step=0.1,
                  tooltip='Time between sink updates.\n'
                          '1.0 s = 1 Hz (default).\n'
                          '0.2 s = 5 Hz (faster).')
        # Convert stored update_interval (seconds) from config
        val = self.config.get('update_interval')
        if val is None:
            val = self._config_default('update_interval')
        self._set_widget_value(self._widgets['update_interval'][0], val)
        self._add_row(lo, 'Update interval (s)', self._widgets['update_interval'][0], 1.0)

        lo.addStretch()
        self.tabs.addTab(self._make_scroll(lo), 'Quick')

    def _create_servo_tab(self):
        lo = QVBoxLayout()
        lo.setSpacing(2)

        self._reg('clock_servo', QComboBox(), 'pi',
                  choices=['pi', 'linreg', 'ntpshm', 'nullf', 'refclock_sock'],
                  tooltip='Clock servo algorithm.\n'
                          'pi = PI controller (default).\n'
                          'linreg = linear regression.')
        self._load_widget('clock_servo', store='config')
        self._add_row(lo, 'Clock servo', self._widgets['clock_servo'][0], 'pi')

        self._reg('pi_proportional_const', QDoubleSpinBox(), 0.7,
                  minv=0.01, maxv=10.0, step=0.1,
                  tooltip='Proportional gain (-P).')
        self._load_widget('pi_proportional_const', store='config')
        self._add_row(lo, 'PI proportional const', self._widgets['pi_proportional_const'][0], 0.7)

        self._reg('pi_integral_const', QDoubleSpinBox(), 0.3,
                  minv=0.01, maxv=10.0, step=0.1,
                  tooltip='Integral gain (-I).')
        self._load_widget('pi_integral_const', store='config')
        self._add_row(lo, 'PI integral const', self._widgets['pi_integral_const'][0], 0.3)

        self._reg('step_threshold', QDoubleSpinBox(), 0.0,
                  minv=0.0, maxv=1.0, step=0.01,
                  tooltip='Step threshold in seconds (-S).\n'
                          '0.0 = no stepping after startup.')
        self._load_widget('step_threshold', store='config')
        self._add_row(lo, 'Step threshold (s)', self._widgets['step_threshold'][0], 0.0)

        self._reg('first_step_threshold', QDoubleSpinBox(), 0.00002,
                  minv=0.0, maxv=1.0, step=0.00001,
                  tooltip='First step threshold in seconds (-F).\n'
                          'Default: 0.00002 (20 µs).')
        self._load_widget('first_step_threshold', store='config')
        self._add_row(lo, 'First step threshold (s)', self._widgets['first_step_threshold'][0], 0.00002)

        self._reg('sanity_freq_limit', QSpinBox(), 200000000,
                  minv=0, maxv=999999999, step=1000000,
                  tooltip='Sanity frequency limit in ppb (-L).')
        self._load_widget('sanity_freq_limit', store='config')
        self._add_row(lo, 'Sanity freq limit (ppb)', self._widgets['sanity_freq_limit'][0], 200000000)

        self._reg('num_readings', QSpinBox(), 5,
                  minv=1, maxv=100, step=1,
                  tooltip='Number of PHC readings per update (-N).')
        self._load_widget('num_readings', store='config')
        self._add_row(lo, 'Num readings', self._widgets['num_readings'][0], 5)

        # summary_updates and ntpshm_segment are CLI-only/config
        self._reg('summary_updates', QSpinBox(), 0,
                  minv=0, maxv=1000, step=1,
                  tooltip='Summary updates (-u). 0 = disabled.')
        self._load_widget('summary_updates', store='qset')
        self._add_row(lo, 'Summary updates (-u)', self._widgets['summary_updates'][0], 0)

        self._reg('ntpshm_segment', QSpinBox(), 0,
                  minv=0, maxv=255, step=1,
                  tooltip='NTP SHM segment (-M).')
        self._load_widget('ntpshm_segment', store='config')
        self._add_row(lo, 'SHM segment', self._widgets['ntpshm_segment'][0], 0)

        lo.addStretch()
        self.tabs.addTab(self._make_scroll(lo), 'Servo')

    def _create_advanced_tab(self):
        lo = QVBoxLayout()
        lo.setSpacing(2)

        self._reg('uds_address', QLineEdit(), '/var/run/ptp4l',
                  tooltip='UDS address (-z). Must match ptp4l.')
        self._load_widget('uds_address', store='config')
        self._add_row(lo, 'UDS address', self._widgets['uds_address'][0], '/var/run/ptp4l')

        self._reg('domainNumber', QSpinBox(), 0,
                  minv=0, maxv=255, step=1,
                  tooltip='PTP domain number (-n).')
        self._load_widget('domainNumber', store='config')
        self._add_row(lo, 'Domain number', self._widgets['domainNumber'][0], 0)

        self._reg('logging_level', QSpinBox(), 6,
                  minv=0, maxv=7, step=1,
                  tooltip='Logging level (-l). 6 = info.')
        self._load_widget('logging_level', store='config')
        self._add_row(lo, 'Logging level', self._widgets['logging_level'][0], 6)

        self._reg('message_tag', QLineEdit(), '',
                  tooltip='Message tag (-t). Prepended to log output.')
        self._load_widget('message_tag', store='config')
        self._add_row(lo, 'Message tag', self._widgets['message_tag'][0], '')

        # kernel_leap: inverted from -x checkbox
        self._reg('kernel_leap', QCheckBox(), True,
                  label='Kernel leap handling',
                  tooltip='Let kernel apply leap seconds.\n'
                          'Uncheck (= -x) to let servo correct slowly.')
        kl = self.config.get('kernel_leap')
        if kl is None:
            kl = self._config_default('kernel_leap')
        self._set_widget_value(self._widgets['kernel_leap'][0], kl)
        self._add_row(lo, 'Kernel leap handling', self._widgets['kernel_leap'][0], True)

        # use_syslog: inverted from -q checkbox
        self._reg('use_syslog', QCheckBox(), True,
                  label='Use syslog',
                  tooltip='Print messages to system log.\n'
                          'Uncheck (= -q) to suppress syslog.')
        self._load_widget('use_syslog', store='config')
        self._add_row(lo, 'Use syslog', self._widgets['use_syslog'][0], True)

        # verbose = -m checkbox
        self._reg('verbose', QCheckBox(), False,
                  label='Verbose (stdout)',
                  tooltip='Print messages to stdout (= -m).\n'
                          'Required for terminal display.')
        self._load_widget('verbose', store='config')
        self._add_row(lo, 'Verbose (-m)', self._widgets['verbose'][0], False)

        self._reg('free_running', QCheckBox(), False,
                  label='Free running',
                  tooltip="Don't adjust the sink clock.\n"
                          'For testing / monitoring only.')
        self._load_widget('free_running', store='config')
        self._add_row(lo, 'Free running', self._widgets['free_running'][0], False)

        self._reg('transportSpecific', QSpinBox(), 0,
                  minv=0, maxv=255, step=1,
                  tooltip='Transport specific field.')
        self._load_widget('transportSpecific', store='config')
        self._add_row(lo, 'Transport specific', self._widgets['transportSpecific'][0], 0)

        self._reg('refclock_sock_address', QLineEdit(), '/var/run/refclock.ptp.sock',
                  tooltip='UNIX socket for refclock_sock servo.')
        self._load_widget('refclock_sock_address', store='config')
        self._add_row(lo, 'Refclock socket', self._widgets['refclock_sock_address'][0],
                      '/var/run/refclock.ptp.sock')

        lo.addStretch()
        self.tabs.addTab(self._make_scroll(lo), 'Advanced')

    def _create_manual_tab(self):
        lo = QVBoxLayout()
        lo.setSpacing(2)

        phc_devices = _load_phc_devices()
        src_choices = phc_devices or ['/dev/ptp0']

        self._reg('source_device', QComboBox(), src_choices[0],
                  choices=src_choices,
                  tooltip='Source clock device (-s).\n'
                          'Used when auto mode is OFF.')
        self._load_widget('source_device', store='qset')
        self._add_row(lo, 'Source device (-s)', self._widgets['source_device'][0], src_choices[0])

        all_sinks = ['CLOCK_REALTIME'] + phc_devices
        self._reg('sink_device', QComboBox(), 'CLOCK_REALTIME',
                  choices=all_sinks,
                  tooltip='Sink clock device (-c).\n'
                          'Default: CLOCK_REALTIME (system clock).')
        self._load_widget('sink_device', store='qset')
        self._add_row(lo, 'Sink device (-c)', self._widgets['sink_device'][0], 'CLOCK_REALTIME')

        self._reg('pps_device', QLineEdit(), '',
                  tooltip='PPS device (-d). Leave empty unless using PPS.')
        self._load_widget('pps_device', store='qset')
        self._add_row(lo, 'PPS device (-d)', self._widgets['pps_device'][0], '')

        # leap_seconds from config (was time_offset in µs, now seconds)
        self._reg('leap_seconds', QSpinBox(), 0,
                  minv=-1000, maxv=1000, step=1,
                  tooltip='UTC-TAI offset in seconds.\n'
                          'Config file equivalent of -O.\n'
                          'Currently 37. Set to 0 for auto-learn.')
        self._load_widget('leap_seconds', store='config')
        self._add_row(lo, 'Leap seconds (-O)', self._widgets['leap_seconds'][0], 0)

        lo.addStretch()
        self.tabs.addTab(self._make_scroll(lo), 'Manual')

    # ── Actions ──────────────────────────────────────────────────

    def _on_save(self):
        # Save config file params
        # Quick tab
        self._save_widget('update_interval', store='config')

        # Servo tab
        self._save_widget('clock_servo', store='config')
        self._save_widget('pi_proportional_const', store='config')
        self._save_widget('pi_integral_const', store='config')
        self._save_widget('step_threshold', store='config')
        self._save_widget('first_step_threshold', store='config')
        self._save_widget('sanity_freq_limit', store='config')
        self._save_widget('num_readings', store='config')
        self._save_widget('ntpshm_segment', store='config')

        # Advanced tab
        self._save_widget('uds_address', store='config')
        self._save_widget('domainNumber', store='config')
        self._save_widget('logging_level', store='config')
        self._save_widget('message_tag', store='config')
        self._save_widget('kernel_leap', store='config')
        self._save_widget('use_syslog', store='config')
        self._save_widget('verbose', store='config')
        self._save_widget('free_running', store='config')
        self._save_widget('transportSpecific', store='config')
        self._save_widget('refclock_sock_address', store='config')

        # Manual tab
        self._save_widget('leap_seconds', store='config')

        # Save CLI-only flags to QSettings
        self._save_widget('auto_mode', store='qset')
        self._save_widget('sync_realtime', store='qset')
        self._save_widget('wait_ptp4l', store='qset')
        self._save_widget('summary_updates', store='qset')
        self._save_widget('source_device', store='qset')
        self._save_widget('sink_device', store='qset')
        self._save_widget('pps_device', store='qset')

        # Persist config file
        self.config.save()
        self.accept()

    def _on_reset(self):
        reply = QMessageBox.warning(
            self, 'Reset to Defaults',
            'Reset all phc2sys parameters to their defaults?\n'
            'This will clear the config file.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.reset_to_default()
            # Reload all config widgets
            for key, (w, default) in self._widgets.items():
                val = self.config.get(key)
                if val is None:
                    val = self._config_default(key)
                self._set_widget_value(w, val)
            # Reset QSettings CLI flags
            for key in ('auto_mode', 'sync_realtime', 'wait_ptp4l',
                        'summary_updates', 'source_device', 'sink_device',
                        'pps_device'):
                w, default = self._widgets.get(key, (None, None))
                if w is not None:
                    self._set_widget_value(w, default)

    # ─── Command Builder ──────────────────────────────────────

    def build_command(self):
        """Build phc2sys command: -f config + CLI-only flags."""

        # Load saved CLI flags from QSettings
        auto = self._qset.value('auto_mode', True, type=bool)
        if auto:
            sync_r = self._qset.value('sync_realtime', 'single (-r)', type=str)
            if sync_r == 'double (-rr)':
                cli_flags = ['-a', '-rr']
            elif sync_r == 'single (-r)':
                cli_flags = ['-a', '-r']
            else:
                cli_flags = ['-a']
        else:
            cli_flags = []
            wait = self._qset.value('wait_ptp4l', True, type=bool)
            if wait:
                cli_flags.append('-w')
            source = self._qset.value('source_device', '', type=str)
            if source:
                cli_flags.extend(['-s', source])
            sink = self._qset.value('sink_device', 'CLOCK_REALTIME', type=str)
            if sink:
                cli_flags.extend(['-c', sink])
            pps = self._qset.value('pps_device', '', type=str)
            if pps:
                cli_flags.extend(['-d', pps])

        # Always print to stdout
        cli_flags.append('-m')

        return ['-f', CONFIG_PATH] + cli_flags
