"""Parameter definitions for /etc/linuxptp/phc2sys.conf."""


class ParamDef:
    __slots__ = ('key', 'type', 'default', 'label', 'tooltip',
                 'section', 'choices', 'min_val', 'max_val', 'step')

    def __init__(self, key, ptype, default, label='', tooltip='',
                 section='Quick', choices=None,
                 min_val=None, max_val=None, step=None):
        self.key = key
        self.type = ptype
        self.default = default
        self.label = label or key
        self.tooltip = tooltip
        self.section = section
        self.choices = choices or []
        self.min_val = min_val
        self.max_val = max_val
        self.step = step


# Built-in defaults as documented in phc2sys(8) man page
BUILTIN_DEFAULTS = {
    'clock_servo': 'pi',
    'pi_proportional_const': 0.7,
    'pi_integral_const': 0.3,
    'step_threshold': 0.0,
    'first_step_threshold': 0.00002,
    'sanity_freq_limit': 200000000,
    'num_readings': 5,
    'update_interval': 1.0,
    'leap_seconds': 0,
    'kernel_leap': 1,
    'use_syslog': 1,
    'verbose': 0,
    'uds_address': '/var/run/ptp4l',
    'domainNumber': 0,
    'logging_level': 6,
    'ntpshm_segment': 0,
    'message_tag': '',
    'free_running': 0,
    'transportSpecific': 0,
    'refclock_sock_address': '/var/run/refclock.ptp.sock',
}

SECTION_ORDER = ['Quick', 'Servo', 'Advanced', 'Manual']

CONFIG_PARAMS = [

    # ── Quick (Servo & Rate) ────────────────────────────────
    ParamDef('clock_servo', 'choice', 'pi',
             label='Clock Servo',
             choices=['pi', 'linreg', 'ntpshm', 'nullf', 'refclock_sock'],
             tooltip='Servo algorithm.\n'
                     'pi = PI controller (default, stable).\n'
                     'linreg = linear regression (better for large drift).',
             section='Quick'),

    ParamDef('pi_proportional_const', 'float', 0.7,
             label='PI Proportional Constant',
             min_val=0.01, max_val=10.0, step=0.1,
             tooltip='Proportional gain of the PI controller.\n'
                     'Higher = faster reaction.\n'
                     'Lower (0.5) for stable PCIe NICs.',
             section='Quick'),

    ParamDef('pi_integral_const', 'float', 0.3,
             label='PI Integral Constant',
             min_val=0.01, max_val=10.0, step=0.1,
             tooltip='Integral gain of the PI controller.\n'
                     'Higher = faster steady-state correction.\n'
                     'Lower (0.1) for noisy PHCs.',
             section='Quick'),

    ParamDef('update_interval', 'float', 1.0,
             label='Update Interval (seconds)',
             min_val=0.01, max_val=10.0, step=0.1,
             tooltip='Time between sink updates in seconds.\n'
                     '1.0 = 1 Hz (default, ~1 log line/sec).\n'
                     '0.2 = 5 Hz (faster updates, more log lines).\n'
                     'Shown as update rate in the dialog.',
             section='Quick'),

    # ── Servo ───────────────────────────────────────────────
    ParamDef('step_threshold', 'float', 0.0,
             label='Step Threshold (seconds)',
             min_val=0.0, max_val=1.0, step=0.01,
             tooltip='Max offset corrected by frequency change instead of stepping.\n'
                     'Offsets above this cause a clock step.\n'
                     '0.0 = no stepping after startup (default).',
             section='Servo'),

    ParamDef('first_step_threshold', 'float', 0.00002,
             label='First Step Threshold (seconds)',
             min_val=0.0, max_val=1.0, step=0.00001,
             tooltip='Max offset corrected on first update.\n'
                     '0.00002 = 20 µs (default).\n'
                     'Raise to 0.001 (1 ms) for cold-start USB PHCs.',
             section='Servo'),

    ParamDef('sanity_freq_limit', 'int', 200000000,
             label='Sanity Frequency Limit (ppb)',
             min_val=0, max_val=999999999, step=1000000,
             tooltip='Max allowed frequency offset in ppb.\n'
                     'Triggers servo reset if exceeded.\n'
                     '0 = disabled. Default: 200000000 (20%).',
             section='Servo'),

    ParamDef('num_readings', 'int', 5,
             label='Number of Readings',
             min_val=1, max_val=100, step=1,
             tooltip='Number of PHC readings per update.\n'
                     'Only the fastest is used.\n'
                     'Increase (10-15) for noisy USB NICs.',
             section='Servo'),

    # ── Advanced ────────────────────────────────────────────
    ParamDef('uds_address', 'string', '/var/run/ptp4l',
             label='UDS Address',
             tooltip='UNIX domain socket for ptp4l communication.\n'
                     'Must match ptp4l uds_address in ptp4l.conf.',
             section='Advanced'),

    ParamDef('domainNumber', 'int', 0,
             label='Domain Number',
             min_val=0, max_val=255, step=1,
             tooltip='PTP domain number. Must match ptp4l.',
             section='Advanced'),

    ParamDef('logging_level', 'int', 6,
             label='Logging Level',
             min_val=0, max_val=7, step=1,
             tooltip='0=emerg, 1=alert, 2=crit, 3=err,\n'
                     '4=warning, 5=notice, 6=info, 7=debug.',
             section='Advanced'),

    ParamDef('message_tag', 'string', '',
             label='Message Tag',
             tooltip='String prepended to all log messages.\n'
                     'Helps identify phc2sys output alongside ptp4l.',
             section='Advanced'),

    ParamDef('ntpshm_segment', 'int', 0,
             label='NTP SHM Segment',
             min_val=0, max_val=255, step=1,
             tooltip='SHM segment number for ntpshm servo.\n'
                     'Only relevant when clock_servo = ntpshm.',
             section='Advanced'),

    ParamDef('use_syslog', 'bool', 1,
             label='Use Syslog',
             tooltip='Print messages to system log.\n'
                     'Disable (=0) to suppress syslog output.',
             section='Advanced'),

    ParamDef('verbose', 'bool', 0,
             label='Verbose (stdout)',
             tooltip='Print messages to standard output.\n'
                     'Enable (=1) for terminal display in the UI.',
             section='Advanced'),

    ParamDef('free_running', 'bool', 0,
             label='Free Running',
             tooltip="Don't adjust the sink clock.\n"
                     'Useful for testing / monitoring only.',
             section='Advanced'),

    ParamDef('transportSpecific', 'int', 0,
             label='Transport Specific',
             min_val=0, max_val=255, step=1,
             tooltip='Transport specific field.\n'
                     'Must match ptp4l transportSpecific.',
             section='Advanced'),

    ParamDef('refclock_sock_address', 'string', '/var/run/refclock.ptp.sock',
             label='Refclock Socket Address',
             tooltip='UNIX domain socket for refclock_sock servo.\n'
                     'Only relevant when clock_servo = refclock_sock.',
             section='Advanced'),

    # ── Manual / Offset ─────────────────────────────────────
    ParamDef('leap_seconds', 'int', 0,
             label='Leap Seconds (UTC-TAI offset)',
             min_val=-1000, max_val=1000, step=1,
             tooltip='Offset between TAI and UTC in seconds.\n'
                     'Currently 37 (as of 2025+).\n'
                     'Set to 0 for auto (via -w) or when using -a.\n'
                     'Config file equivalent of -O.',
             section='Manual'),

    ParamDef('kernel_leap', 'bool', 1,
             label='Kernel Leap Handling',
             tooltip='Let kernel apply leap seconds by stepping the clock.\n'
                     'Enable (=1, default): kernel handles leaps.\n'
                     'Disable (=0): servo corrects leap slowly (= -x flag).',
             section='Manual'),
]


def get_params_for_section(section):
    return [p for p in CONFIG_PARAMS if p.section == section]


def get_default(key):
    for p in CONFIG_PARAMS:
        if p.key == key:
            return p.default
    return BUILTIN_DEFAULTS.get(key)
