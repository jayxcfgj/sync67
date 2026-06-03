"""phc2sys Config Dialog – 4 tabs for all command-line options."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox,
    QCheckBox, QComboBox, QPushButton,
    QWidget, QScrollArea, QFormLayout
)
from PyQt6.QtCore import Qt, QSettings

import os


_IFACE_CACHE = None


def _load_phc_devices():
    global _IFACE_CACHE
    if _IFACE_CACHE is not None:
        return _IFACE_CACHE
    devices = []
    try:
        for entry in os.listdir('/sys/class/ptp/'):
            if entry.startswith('ptp'):
                devices.append(f'/dev/{entry}')
    except Exception:
        pass
    _IFACE_CACHE = sorted(devices)
    return _IFACE_CACHE


_DEFAULT_TOOLTIP = 'Default: {}'
_DEFAULT = object()


def _lbl(text, default=_DEFAULT, tooltip=''):
    parts = [text]
    if default is not _DEFAULT:
        parts.append(f'  ({_DEFAULT_TOOLTIP.format(default)})')
    full = '\n'.join(parts)
    if tooltip:
        full += f'\n{tooltip}'
    return full


class Phc2sysConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('phc2sys Configuration')
        self.setMinimumSize(400, 300)
        self.resize(550, 500)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)
        self._settings = QSettings('sync67', 'phc2sys_settings')
        self._widgets = {}
        self._init_ui()

    def _add_row(self, layout, label, widget, default_label_text=''):
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        row.addWidget(widget)
        if default_label_text:
            dl = QLabel(default_label_text)
            dl.setStyleSheet('color: gray; font-size: 10px;')
            row.addWidget(dl)
        row.addStretch()
        layout.addRow(row)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self._create_quick_tab()
        self._create_servo_tab()
        self._create_advanced_tab()
        self._create_manual_tab()
        layout.addWidget(self.tabs)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        save_btn = QPushButton('Save')
        save_btn.clicked.connect(self._on_save)
        cancel_btn = QPushButton('Cancel')
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self._load_settings()

    def _make_scroll(self, form):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content.setMinimumSize(0, 0)
        content.setLayout(form)
        scroll.setWidget(content)
        return scroll

    # ── Quick Tab ────────────────────────────────────────────────

    def _create_quick_tab(self):
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._w('auto_mode', QCheckBox(), True,
                label='Auto mode (-a)',
                tooltip='Automatically read clocks from running ptp4l\n'
                        'and follow port state changes. Recommended.\n'
                        'When OFF, manual source/sink must be configured\n'
                        'in the Manual tab.')
        self._add_row(form, 'Auto mode (-a):', self._widgets['auto_mode'][0])

        self._w('sync_realtime', QComboBox(), 1,
                label='Sync system clock (-r)',
                choices=['off', 'single (-r)', 'double (-rr)'],
                tooltip='-r: synchronize system (realtime) clock to PHC.\n'
                        '-rr: also consider system clock as time source\n'
                        '      (for grandmaster setups).')
        self._add_row(form, 'Sync system clock:', self._widgets['sync_realtime'][0])

        self._w('wait_ptp4l', QCheckBox(), True,
                label='Wait for ptp4l (-w)',
                tooltip='Wait until ptp4l is synchronized before starting.\n'
                        'Auto-learns UTC offset from ptp4l.')
        self._add_row(form, 'Wait for ptp4l (-w):', self._widgets['wait_ptp4l'][0])

        self._w('update_rate', QDoubleSpinBox(), 5.0,
                label='Update rate (-R Hz)',
                minv=0.1, maxv=100.0, step=0.5,
                tooltip='How many times per second the clock is updated.\n'
                        'Higher = smoother sync, more CPU.\n'
                        'Default: 5.0 Hz (AES67 recommendation).')
        self._add_row(form, 'Update rate (-R):', self._widgets['update_rate'][0])

        self.tabs.addTab(self._make_scroll(form), 'Quick')

    # ── Servo Tab ────────────────────────────────────────────────

    def _create_servo_tab(self):
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._w('servo_type', QComboBox(), 0,
                label='Clock servo (-E)',
                choices=['pi', 'linreg'],
                tooltip='pi = Proportional-Integral controller (stable).\n'
                        'linreg = linear regression (better for large drift).')
        self._add_row(form, 'Servo type (-E):', self._widgets['servo_type'][0])

        self._w('pi_proportional', QDoubleSpinBox(), 0.7,
                label='PI proportional (-P)',
                minv=0.01, maxv=10.0, step=0.1,
                tooltip='Proportional gain. Higher = faster reaction.\n'
                        'Lower (0.5) for stable PCIe NICs.')
        self._add_row(form, 'PI proportional (-P):', self._widgets['pi_proportional'][0])

        self._w('pi_integral', QDoubleSpinBox(), 0.3,
                label='PI integral (-I)',
                minv=0.01, maxv=10.0, step=0.1,
                tooltip='Integral gain. Higher = faster steady-state correction.\n'
                        'Lower (0.1) for noisy PHCs.')
        self._add_row(form, 'PI integral (-I):', self._widgets['pi_integral'][0])

        self._w('step_threshold', QSpinBox(), 0,
                label='Step threshold (-S µs)',
                minv=0, maxv=1000000, step=100,
                tooltip='Maximum offset correctable by frequency adjustment.\n'
                        'Offsets above this cause a time step.\n'
                        '0 = no stepping after startup. Default: 0 (disabled).')
        self._add_row(form, 'Step threshold (-S):', self._widgets['step_threshold'][0])

        self._w('first_step', QSpinBox(), 20,
                label='First step threshold (-F µs)',
                minv=0, maxv=1000000, step=10,
                tooltip='Max offset corrected by frequency on first update.\n'
                        'Allows quick lock at startup. Raise (1000 µs)\n'
                        'for cold-start USB PHCs. Default: 20 µs.')
        self._add_row(form, 'First step (-F):', self._widgets['first_step'][0])

        self._w('sanity_limit', QSpinBox(), 200000000,
                label='Sanity freq limit (-L ppb)',
                minv=0, maxv=999999999, step=1000000,
                tooltip='Maximum allowed frequency offset in ppb.\n'
                        'Triggers servo reset if exceeded.\n'
                        '0 = disabled. Default: 200000000 (20%).')
        self._add_row(form, 'Sanity limit (-L):', self._widgets['sanity_limit'][0])

        self._w('readings_per_update', QSpinBox(), 5,
                label='Readings per update (-N)',
                minv=1, maxv=100, step=1,
                tooltip='Number of PHC readings per update.\n'
                        'Only the fastest is used. Increase (10-15)\n'
                        'for noisy USB NICs. Default: 5.')
        self._add_row(form, 'Readings (-N):', self._widgets['readings_per_update'][0])

        self._w('summary_updates', QSpinBox(), 0,
                label='Summary updates (-u)',
                minv=0, maxv=1000, step=1,
                tooltip='Number of clock updates in summary stats.\n'
                        '0 = disabled (prints individual samples).')
        self._add_row(form, 'Summary updates (-u):', self._widgets['summary_updates'][0])

        self._w('shm_segment', QSpinBox(), 0,
                label='SHM segment (-M)',
                minv=0, maxv=255, step=1,
                tooltip='NTP SHM segment number.\n'
                        'Only relevant for ntpshm servo type.')
        self._add_row(form, 'SHM segment (-M):', self._widgets['shm_segment'][0])

        self.tabs.addTab(self._make_scroll(form), 'Servo')

    # ── Advanced Tab ─────────────────────────────────────────────

    def _create_advanced_tab(self):
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._w('uds_address', QLineEdit(), '/var/run/ptp4l',
                label='UDS address (-z)',
                tooltip='UNIX domain socket for ptp4l communication.\n'
                        'Must match ptp4l uds_address/ptp4l.conf.')
        self._add_row(form, 'UDS address (-z):', self._widgets['uds_address'][0])

        self._w('domain_number', QSpinBox(), 0,
                label='Domain number (-n)',
                minv=0, maxv=255, step=1,
                tooltip='PTP domain number. Must match ptp4l.')
        self._add_row(form, 'Domain (-n):', self._widgets['domain_number'][0])

        self._w('logging_level', QSpinBox(), 6,
                label='Logging level (-l)',
                minv=0, maxv=7, step=1,
                tooltip='0=emerg, 1=alert, 2=crit, 3=err,\n'
                        '4=warning, 5=notice, 6=info, 7=debug.')
        self._add_row(form, 'Log level (-l):', self._widgets['logging_level'][0])

        self._w('message_tag', QLineEdit(), '',
                label='Message tag (-t)',
                tooltip='String prepended to all log messages.\n'
                        'Helps identify phc2sys output alongside ptp4l.')
        self._add_row(form, 'Tag (-t):', self._widgets['message_tag'][0])

        self._w('leap_servo', QCheckBox(), False,
                label='Leap servo (-x)',
                tooltip='Apply leap seconds by servo instead of kernel.\n'
                        'Avoids a sudden 1s time step during leap events.')
        self._add_row(form, 'Leap servo (-x):', self._widgets['leap_servo'][0])

        self._w('quiet_syslog', QCheckBox(), False,
                label='Quiet syslog (-q)',
                tooltip='Do not print messages to syslog.\n'
                        'Only stdout (with -m).')
        self._add_row(form, 'Quiet syslog (-q):', self._widgets['quiet_syslog'][0])

        self._w('print_stdout', QCheckBox(), True,
                label='Print stdout (-m)',
                tooltip='Print messages to stdout.\n'
                        'Required for terminal display in the UI.')
        self._add_row(form, 'Print stdout (-m):', self._widgets['print_stdout'][0])

        self._w('config_file', QLineEdit(), '',
                label='Config file (-f)',
                tooltip='Path to external config file. If set, all\n'
                        'other CLI parameters are ignored.\n'
                        'Must match phc2sys.conf format.')
        self._add_row(form, 'Config file (-f):', self._widgets['config_file'][0])

        self.tabs.addTab(self._make_scroll(form), 'Advanced')

    # ── Manual Tab ───────────────────────────────────────────────

    def _create_manual_tab(self):
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        phc_devices = _load_phc_devices()
        all_clock_sources = ['CLOCK_REALTIME'] + phc_devices

        self._w('source_device', QComboBox(), 0,
                label='Source device (-s)',
                choices=phc_devices or ['/dev/ptp0'],
                tooltip='Source clock device. Used when auto mode (-a) is OFF.\n'
                        'The clock that provides the reference time.')
        self._add_row(form, 'Source device (-s):', self._widgets['source_device'][0])

        self._w('sink_device', QComboBox(), 0,
                label='Sink device (-c)',
                choices=all_clock_sources,
                tooltip='Sink clock device. Used when auto mode (-a) is OFF.\n'
                        'The clock that receives the reference time.\n'
                        'Default: CLOCK_REALTIME (system clock).')
        self._add_row(form, 'Sink device (-c):', self._widgets['sink_device'][0])

        self._w('pps_device', QLineEdit(), '',
                label='PPS device (-d)',
                tooltip='Pulse-per-second device (e.g. /dev/pps0).\n'
                        'Alternative to direct time reads.\n'
                        'Leave empty unless using PPS.')
        self._add_row(form, 'PPS device (-d):', self._widgets['pps_device'][0])

        self._w('time_offset', QSpinBox(), 0,
                label='Time offset (-O µs)',
                minv=-1000000, maxv=1000000, step=1,
                tooltip='Sink-source time offset in µs.\n'
                        'Auto-learned from ptp4l when -w is used.\n'
                        'Manual: e.g. 37000000 (37s UTC-TAI).')
        self._add_row(form, 'Time offset (-O):', self._widgets['time_offset'][0])

        self.tabs.addTab(self._make_scroll(form), 'Manual')

    # ── Widget helpers ───────────────────────────────────────────

    def _w(self, key, widget, default, label='', tooltip='',
           choices=None, minv=None, maxv=None, step=None):
        widget.setToolTip(tooltip)
        if isinstance(widget, QDoubleSpinBox):
            if minv is not None:
                widget.setMinimum(minv)
            if maxv is not None:
                widget.setMaximum(maxv)
            if step is not None:
                widget.setSingleStep(step)
            widget.setDecimals(1)
        elif isinstance(widget, QSpinBox):
            if minv is not None:
                widget.setMinimum(minv)
            if maxv is not None:
                widget.setMaximum(maxv)
            if step is not None:
                widget.setSingleStep(step)
        elif isinstance(widget, QComboBox) and choices:
            widget.clear()
            widget.addItems(choices)
        self._widgets[key] = (widget, default)

    def _load_settings(self):
        for key, (widget, default) in self._widgets.items():
            val = self._settings.value(key, default)
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(val) if not isinstance(val, bool) else val)
            elif isinstance(widget, QSpinBox):
                widget.setValue(int(val))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(val))
            elif isinstance(widget, QComboBox):
                idx = widget.findText(str(val))
                if idx >= 0:
                    widget.setCurrentIndex(idx)
                elif isinstance(val, int) and val < widget.count():
                    widget.setCurrentIndex(val)
            elif isinstance(widget, QLineEdit):
                widget.setText(str(val) if val else '')

    def _save_settings(self):
        for key, (widget, _) in self._widgets.items():
            if isinstance(widget, QCheckBox):
                self._settings.setValue(key, widget.isChecked())
            elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                self._settings.setValue(key, widget.value())
            elif isinstance(widget, QComboBox):
                self._settings.setValue(key, widget.currentText())
            elif isinstance(widget, QLineEdit):
                self._settings.setValue(key, widget.text())

    def _on_save(self):
        self._save_settings()
        self.accept()

    def build_command(self):
        """Build phc2sys command from current settings.

        Returns list of argument strings or empty if config file is set.
        """
        cfg = self._settings.value('config_file', '', type=str)
        if cfg:
            return []

        args = []
        auto = self._settings.value('auto_mode', True, type=bool)
        if auto:
            args.append('-a')
            sync_r = self._settings.value('sync_realtime', 'single (-r)', type=str)
            if sync_r == 'single (-r)':
                args.append('-r')
            elif sync_r == 'double (-rr)':
                args.append('-rr')
        else:
            if self._settings.value('wait_ptp4l', True, type=bool):
                args.append('-w')
            source = self._settings.value('source_device', '/dev/ptp0', type=str)
            if source:
                args.extend(['-s', source])
            sink = self._settings.value('sink_device', 'CLOCK_REALTIME', type=str)
            if sink:
                args.extend(['-c', sink])
            pps = self._settings.value('pps_device', '', type=str)
            if pps:
                args.extend(['-d', pps])
            offset = self._settings.value('time_offset', 0, type=int)
            if offset != 0:
                args.extend(['-O', str(offset / 1_000_000)])

        rate = self._settings.value('update_rate', 5.0, type=float)
        args.extend(['-R', str(rate)])

        servo = self._settings.value('servo_type', 'pi', type=str)
        args.extend(['-E', servo])

        pp = self._settings.value('pi_proportional', 0.7, type=float)
        args.extend(['-P', str(pp)])

        pi = self._settings.value('pi_integral', 0.3, type=float)
        args.extend(['-I', str(pi)])

        step = self._settings.value('step_threshold', 0, type=int)
        if step > 0:
            args.extend(['-S', str(step / 1_000_000)])

        first = self._settings.value('first_step', 20, type=int)
        if first > 0:
            args.extend(['-F', str(first / 1_000_000)])

        limit = self._settings.value('sanity_limit', 200000000, type=int)
        if limit != 200000000:
            args.extend(['-L', str(limit)])

        n_readings = self._settings.value('readings_per_update', 5, type=int)
        if n_readings != 5:
            args.extend(['-N', str(n_readings)])

        summary = self._settings.value('summary_updates', 0, type=int)
        if summary > 0:
            args.extend(['-u', str(summary)])

        shm = self._settings.value('shm_segment', 0, type=int)
        if shm != 0:
            args.extend(['-M', str(shm)])

        domain = self._settings.value('domain_number', 0, type=int)
        if domain != 0:
            args.extend(['-n', str(domain)])

        uds = self._settings.value('uds_address', '/var/run/ptp4l', type=str)
        if uds != '/var/run/ptp4l':
            args.extend(['-z', uds])

        tag = self._settings.value('message_tag', '', type=str)
        if tag:
            args.extend(['-t', tag])

        log_level = self._settings.value('logging_level', 6, type=int)
        if log_level != 6:
            args.extend(['-l', str(log_level)])

        if self._settings.value('leap_servo', False, type=bool):
            args.append('-x')

        if self._settings.value('quiet_syslog', False, type=bool):
            args.append('-q')

        if self._settings.value('print_stdout', True, type=bool):
            args.append('-m')

        return args
