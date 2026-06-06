"""phc2sys Config Dialog – 4 tabs, enable-checkboxes per parameter."""

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
        self._enable_cbs = {}
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

    def _add_row(self, layout, label_text, widget, default, enable_cb=None):
        row = QHBoxLayout()
        row.setSpacing(4)
        if enable_cb is not None:
            enable_cb.setFixedWidth(20)
            enable_cb.setToolTip(
                'Enable this parameter in the config file.\n'
                'Unchecked = built-in default / not written.'
            )
            row.addWidget(enable_cb)
        inner = QVBoxLayout()
        inner.setSpacing(2)
        inner.addWidget(QLabel(label_text))
        inner.addWidget(widget)
        dl = QLabel(self._default_text(default))
        dl.setStyleSheet('color: gray; font-size: 10px;')
        inner.addWidget(dl)
        row.addLayout(inner)
        layout.addLayout(row)

    def _reg(self, key, widget, default, label='', tooltip='',
             choices=None, minv=None, maxv=None, step=None):
        widget.setToolTip(tooltip)
        if isinstance(widget, QDoubleSpinBox):
            if minv is not None: widget.setMinimum(minv)
            if maxv is not None: widget.setMaximum(maxv)
            if step is not None: widget.setSingleStep(step)
            widget.setDecimals(6)
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
            text = w.text().strip()
            if text == '':
                return None
            try:
                if '.' in text:
                    return float(text)
                return int(text)
            except ValueError:
                return text
        return None

    # ── Config / QSettings helpers ───────────────────────────────

    def _load_config_widget(self, key, cfg_key=None):
        w, default = self._widgets.get(key, (None, None))
        if w is None:
            return
        cb = self._enable_cbs.get(key)
        val = self.config.get(cfg_key or key)
        if val is not None:
            if cb:
                cb.setChecked(True)
                w.setEnabled(True)
            self._set_widget_value(w, val)
        else:
            if cb:
                cb.setChecked(False)
                w.setEnabled(False)
            self._set_widget_value(w, None)

    def _load_qset_widget(self, key, default=None):
        w, _ = self._widgets.get(key, (None, None))
        if w is None:
            return
        if default is None:
            _, default = self._widgets.get(key, (None, None))
            default = default if default is not None else True
        val = self._qset.value(key, default)
        self._set_widget_value(w, val)

    def _save_config_widget(self, key, cfg_key=None):
        w, _ = self._widgets.get(key, (None, None))
        if w is None:
            return
        cb = self._enable_cbs.get(key)
        if cb and not cb.isChecked():
            self.config.delete(cfg_key or key)
            return
        val = self._widget_value(key)
        if val is None:
            self.config.delete(cfg_key or key)
        else:
            self.config.set(cfg_key or key, val)

    def _save_qset_widget(self, key):
        val = self._widget_value(key)
        if val is not None:
            self._qset.setValue(key, val)

    @staticmethod
    def _set_widget_value(w, val):
        if isinstance(w, QCheckBox):
            w.setChecked(bool(val) if val is not None else False)
        elif isinstance(w, QSpinBox):
            w.setValue(int(val) if val is not None else 0)
        elif isinstance(w, QDoubleSpinBox):
            w.setValue(float(val) if val is not None else 0.0)
        elif isinstance(w, QComboBox):
            if val is not None:
                idx = w.findText(str(val))
                if idx >= 0:
                    w.setCurrentIndex(idx)
                elif isinstance(val, int) and val < w.count():
                    w.setCurrentIndex(val)
            else:
                w.setCurrentIndex(0)
        elif isinstance(w, QLineEdit):
            if val is None:
                w.setText('')
            elif isinstance(val, float):
                formatted = f'{val:.10f}'.rstrip('0').rstrip('.')
                w.setText(formatted)
            else:
                w.setText(str(val))

    def _make_config_row(self, layout, key, label_text, widget, default,
                         tooltip='', choices=None, minv=None, maxv=None, step=None):
        cb = QCheckBox()
        self._enable_cbs[key] = cb
        self._reg(key, widget, default, label=label_text, tooltip=tooltip,
                  choices=choices, minv=minv, maxv=maxv, step=step)
        self._load_config_widget(key)
        self._add_row(layout, label_text, widget, default, enable_cb=cb)
        cb.toggled.connect(lambda checked, k=key: (
            self._widgets[k][0].setEnabled(checked)
        ))

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

        # CLI-only params (no enable checkbox, stored in QSettings)
        self._reg('auto_mode', QCheckBox(), True,
                  label='Auto mode (-a)',
                  tooltip='Automatically read clocks from running ptp4l\n'
                          'and follow port state changes.\n'
                          'When OFF, manual source/sink must be configured.')
        self._load_qset_widget('auto_mode')
        self._add_row(lo, 'Auto mode (-a)', self._widgets['auto_mode'][0], True)

        self._reg('sync_realtime', QComboBox(), 'single (-r)',
                  choices=['off', 'single (-r)', 'double (-rr)'],
                  tooltip='-r: synchronize system clock to PHC.\n'
                          '-rr: also consider system clock as time source.')
        self._load_qset_widget('sync_realtime')
        self._add_row(lo, 'Sync system clock', self._widgets['sync_realtime'][0], 'single (-r)')

        self._reg('wait_ptp4l', QCheckBox(), True,
                  label='Wait for ptp4l (-w)',
                  tooltip='Wait until ptp4l is synchronized.\n'
                          'Auto-learns UTC offset from ptp4l.\n'
                          'Only in manual mode.')
        self._load_qset_widget('wait_ptp4l')
        self._add_row(lo, 'Wait for ptp4l (-w)', self._widgets['wait_ptp4l'][0], True)

        # Config param: update_interval
        self._make_config_row(lo, 'update_interval', 'Update interval (s)',
                              QLineEdit(), 1.0, minv=None,
                              tooltip='Time between sink updates.\n'
                                      '1.0 s = 1 Hz (default).\n'
                                      '0.2 s = 5 Hz (faster).')

        lo.addStretch()
        self.tabs.addTab(self._make_scroll(lo), 'Quick')

    def _create_servo_tab(self):
        lo = QVBoxLayout()
        lo.setSpacing(2)

        self._make_config_row(lo, 'clock_servo', 'Clock servo',
                              QComboBox(), 'pi',
                              choices=['pi', 'linreg', 'ntpshm', 'nullf', 'refclock_sock'],
                              tooltip='Clock servo algorithm.\n'
                                      'pi = PI controller (default).\n'
                                      'linreg = linear regression.')

        self._make_config_row(lo, 'pi_proportional_const', 'PI proportional const',
                              QLineEdit(), 0.7, minv=None,
                              tooltip='Proportional gain (-P).')

        self._make_config_row(lo, 'pi_integral_const', 'PI integral const',
                              QLineEdit(), 0.3, minv=None,
                              tooltip='Integral gain (-I).')

        self._make_config_row(lo, 'step_threshold', 'Step threshold (s)',
                              QLineEdit(), 0.0, minv=None,
                              tooltip='Step threshold in seconds (-S).\n'
                                      '0.0 = no stepping after startup.')

        self._make_config_row(lo, 'first_step_threshold', 'First step threshold (s)',
                              QLineEdit(), 0.00002, minv=None,
                              tooltip='First step threshold in seconds (-F).\n'
                                      'Default: 0.00002 (20 \u00b5s).')

        self._make_config_row(lo, 'sanity_freq_limit', 'Sanity freq limit (ppb)',
                              QLineEdit(), 200000000, minv=None,
                              tooltip='Sanity frequency limit in ppb (-L).')

        self._make_config_row(lo, 'num_readings', 'Num readings',
                              QLineEdit(), 5, minv=None,
                              tooltip='Number of PHC readings per update (-N).')

        # summary_updates is CLI-only
        self._reg('summary_updates', QSpinBox(), 0,
                  minv=0, maxv=1000, step=1,
                  tooltip='Summary updates (-u). 0 = disabled.')
        self._load_qset_widget('summary_updates')
        self._add_row(lo, 'Summary updates (-u)', self._widgets['summary_updates'][0], 0)

        self._make_config_row(lo, 'ntpshm_segment', 'SHM segment',
                              QLineEdit(), 0, minv=None,
                              tooltip='NTP SHM segment (-M).')

        lo.addStretch()
        self.tabs.addTab(self._make_scroll(lo), 'Servo')

    def _create_advanced_tab(self):
        lo = QVBoxLayout()
        lo.setSpacing(2)

        self._make_config_row(lo, 'uds_address', 'UDS address',
                              QLineEdit(), '/var/run/ptp4l',
                              tooltip='UDS address (-z). Must match ptp4l.')

        self._make_config_row(lo, 'domainNumber', 'Domain number',
                              QLineEdit(), 0, minv=None,
                              tooltip='PTP domain number (-n).')

        self._make_config_row(lo, 'logging_level', 'Logging level',
                              QLineEdit(), 6, minv=None,
                              tooltip='Logging level (-l). 6 = info.')

        self._make_config_row(lo, 'message_tag', 'Message tag',
                              QLineEdit(), '',
                              tooltip='Message tag (-t). Prepended to log output.')

        # kernel_leap: inverted from -x checkbox
        self._make_config_row(lo, 'kernel_leap', 'Kernel leap handling',
                              QCheckBox(), True,
                              tooltip='Let kernel apply leap seconds.\n'
                                      'Uncheck (= -x) to let servo correct slowly.')

        # use_syslog: inverted from -q checkbox
        self._make_config_row(lo, 'use_syslog', 'Use syslog',
                              QCheckBox(), True,
                              tooltip='Print messages to system log.\n'
                                      'Uncheck (= -q) to suppress syslog.')

        # verbose = -m checkbox
        self._make_config_row(lo, 'verbose', 'Verbose (-m)',
                              QCheckBox(), False,
                              tooltip='Print messages to stdout (= -m).\n'
                                      'Required for terminal display.')

        self._make_config_row(lo, 'free_running', 'Free running',
                              QCheckBox(), False,
                              tooltip="Don't adjust the sink clock.\n"
                                      'For testing / monitoring only.')

        self._make_config_row(lo, 'transportSpecific', 'Transport specific',
                              QLineEdit(), 0, minv=None,
                              tooltip='Transport specific field.')

        self._make_config_row(lo, 'refclock_sock_address', 'Refclock socket',
                              QLineEdit(), '/var/run/refclock.ptp.sock',
                              tooltip='UNIX socket for refclock_sock servo.')

        lo.addStretch()
        self.tabs.addTab(self._make_scroll(lo), 'Advanced')

    def _create_manual_tab(self):
        lo = QVBoxLayout()
        lo.setSpacing(2)

        phc_devices = _load_phc_devices()
        src_choices = phc_devices or ['/dev/ptp0']

        # CLI-only params (QSettings)
        self._reg('source_device', QComboBox(), src_choices[0],
                  choices=src_choices,
                  tooltip='Source clock device (-s).\n'
                          'Used when auto mode is OFF.')
        self._load_qset_widget('source_device')
        self._add_row(lo, 'Source device (-s)', self._widgets['source_device'][0], src_choices[0])

        all_sinks = ['CLOCK_REALTIME'] + phc_devices
        self._reg('sink_device', QComboBox(), 'CLOCK_REALTIME',
                  choices=all_sinks,
                  tooltip='Sink clock device (-c).\n'
                          'Default: CLOCK_REALTIME (system clock).')
        self._load_qset_widget('sink_device')
        self._add_row(lo, 'Sink device (-c)', self._widgets['sink_device'][0], 'CLOCK_REALTIME')

        self._reg('pps_device', QLineEdit(), '',
                  tooltip='PPS device (-d). Leave empty unless using PPS.')
        self._load_qset_widget('pps_device')
        self._add_row(lo, 'PPS device (-d)', self._widgets['pps_device'][0], '')

        # Config param: leap_seconds
        self._make_config_row(lo, 'leap_seconds', 'Leap seconds (-O)',
                              QLineEdit(), 0, minv=None,
                              tooltip='UTC-TAI offset in seconds.\n'
                                      'Config file equivalent of -O.\n'
                                      'Currently 37. Set to 0 for auto-learn.')

        lo.addStretch()
        self.tabs.addTab(self._make_scroll(lo), 'Manual')

    # ── Actions ──────────────────────────────────────────────────

    def _on_save(self):
        # Quick tab
        self._save_config_widget('update_interval')

        # Servo tab
        self._save_config_widget('clock_servo')
        self._save_config_widget('pi_proportional_const')
        self._save_config_widget('pi_integral_const')
        self._save_config_widget('step_threshold')
        self._save_config_widget('first_step_threshold')
        self._save_config_widget('sanity_freq_limit')
        self._save_config_widget('num_readings')
        self._save_config_widget('ntpshm_segment')

        # Advanced tab
        self._save_config_widget('uds_address')
        self._save_config_widget('domainNumber')
        self._save_config_widget('logging_level')
        self._save_config_widget('message_tag')
        self._save_config_widget('kernel_leap')
        self._save_config_widget('use_syslog')
        self._save_config_widget('verbose')
        self._save_config_widget('free_running')
        self._save_config_widget('transportSpecific')
        self._save_config_widget('refclock_sock_address')

        # Manual tab
        self._save_config_widget('leap_seconds')

        # Save CLI-only flags to QSettings
        self._save_qset_widget('auto_mode')
        self._save_qset_widget('sync_realtime')
        self._save_qset_widget('wait_ptp4l')
        self._save_qset_widget('summary_updates')
        self._save_qset_widget('source_device')
        self._save_qset_widget('sink_device')
        self._save_qset_widget('pps_device')

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
            for key in self._widgets:
                if key in self._enable_cbs:
                    self._load_config_widget(key)
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

        cli_flags.append('-m')

        # Pass -z (uds_address) from config if explicitly set
        uds = self.config.get('uds_address')
        if uds:
            cli_flags.extend(['-z', str(uds)])

        return ['-f', CONFIG_PATH] + cli_flags
