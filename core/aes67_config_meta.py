"""Metadata for all parameters of pipewire-aes67.conf."""

from typing import Any


class ParamDef:
    __slots__ = ('key', 'module', 'path', 'type', 'default',
                 'label', 'tooltip', 'section', 'advanced',
                 'choices', 'min_val', 'max_val', 'step')

    def __init__(self, key: str, module: str, path: tuple,
                 ptype: str, default: Any,
                 label: str = '', tooltip: str = '',
                 section: str = 'Expert', advanced: bool = False,
                 choices: list = None,
                 min_val=None, max_val=None, step=None):
        self.key = key
        self.module = module
        self.path = path  # e.g. ('args', 'local.ifname') or ('args', 'stream.props', 'node.name')
        self.type = ptype
        self.default = default
        self.label = label or key
        self.tooltip = tooltip
        self.section = section
        self.advanced = advanced
        self.choices = choices or []
        self.min_val = min_val
        self.max_val = max_val
        self.step = step


CONFIG_PARAMS: list[ParamDef] = [

    # ── PTP Clock (context.objects → PTP0-Driver) ──────────────
    ParamDef('clock.interface', 'context.objects',
             ('args', 'clock.interface'), 'interface',
             '"eth0"',
             label='Network Interface (PHC)',
             tooltip='Network interface for the PTP Hardware Clock (PHC).\n'
                     'Select the same interface as configured in the PTP tab.',
             section='PTP Clock'),
    ParamDef('clock.device', 'context.objects',
             ('args', 'clock.device'), 'phc_device',
             '"/dev/ptp0"',
             label='PHC Device',
             tooltip='PTP Hardware Clock device.\n'
                     'Select (empty – dedicated for phc2sys) when phc2sys\n'
                     'manages the clock independently of pipewire-aes67.',
             section='PTP Clock'),
    ParamDef('clock.id', 'context.objects',
             ('args', 'clock.id'), 'string',
             None,
             label='Clock ID',
             tooltip='Alternative clock source.\n'
                     'Leave empty = automatic via interface/device.\n'
                     '"tai" = CLOCK_TAI (syncable via NTP).\n'
                     '"realtime" = CLOCK_REALTIME (use with phc2sys).\n'
                     'Or enter a custom clock ID (e.g. "42").',
             section='PTP Clock'),
    ParamDef('clock.name', 'context.objects',
             ('args', 'clock.name'), 'string',
             '"clock.system.ptp0"',
             label='Clock Name',
             tooltip='Name of the PTP clock.\n'
                     'Referenced by other modules.',
             section='PTP Clock'),
    ParamDef('priority.driver', 'context.objects',
             ('args', 'priority.driver'), 'int',
             100000,
             label='Driver Priority',
             tooltip='Priority of the PTP driver.\n'
                     'Lower value = higher priority.',
             section='PTP Clock',
             min_val=0, max_val=1000000, step=1000),
    ParamDef('resync.ms', 'context.objects',
             ('args', 'resync.ms'), 'float',
             1.5,
             label='Resync Interval (ms)',
             tooltip='Interval in ms after which a re-synchronization\n'
                     'of the clock is forced.\n'
                     'Lower = more frequent resyncs.',
             section='PTP Clock',
             min_val=0.1, max_val=60.0, step=0.1),
    ParamDef('max_resync', 'context.objects',
             ('args', 'max_resync'), 'int',
             48,
             label='Max Resync Error (µs)',
             tooltip='Maximum allowed PHC error before a clock reset is triggered.\n'
                     'If the error after resync exceeds this value, the driver resets.\n'
                     'Increase for imprecise PHCs (e.g. USB adapters).\n'
                     'Default: 48µs (PipeWire internal).',
             section='PTP Clock',
             min_val=1, max_val=10000, step=10),
    ParamDef('object.export', 'context.objects',
             ('args', 'object.export'), 'bool',
             True,
             label='Export Clock',
             tooltip='Export the PTP clock as a PipeWire object.\n'
                     'Must be enabled for other modules to use it.',
             section='PTP Clock'),

    # ── RT-Modul (Expert) ──────────────────────────────────────
    ParamDef('nice.level', 'libpipewire-module-rt',
             ('args', 'nice.level'), 'int',
             -11,
             label='Nice Level',
             tooltip='Nice value for real-time threads.\n'
                     'Negative = higher priority.',
             section='Expert', advanced=True,
             min_val=-20, max_val=19),
    ParamDef('rt.prio', 'libpipewire-module-rt',
             ('args', 'rt.prio'), 'int',
             83,
             label='RT Priority',
             tooltip='Real-time thread priority (1-99).\n'
                     'Higher = more important threads.',
             section='Expert', advanced=True,
             min_val=1, max_val=99),
    ParamDef('rlimits.enabled', 'libpipewire-module-rt',
             ('args', 'rlimits.enabled'), 'bool',
             True,
             label='Enable rlimits',
             tooltip='Enable resource limits for real-time threads.',
             section='Expert', advanced=True),
    ParamDef('rtkit.enabled', 'libpipewire-module-rt',
             ('args', 'rtkit.enabled'), 'bool',
             False,
             label='Enable RTKit',
             tooltip='Use RTKit D-Bus service for real-time priority.\n'
                     'Alternative to regular rlimits.',
             section='Expert', advanced=True),

    # ── RTP SAP Input ──────────────────────────────────────────
    ParamDef('sap.local.ifname', 'libpipewire-module-rtp-sap',
             ('args', 'local.ifname'), 'interface',
             'eth0',
             label='Network Interface (SAP)',
             tooltip='Network interface for SAP reception.\n'
                     'Select the same interface as configured in the PTP tab.',
             section='RTP SAP Input'),
    ParamDef('sap.ip', 'libpipewire-module-rtp-sap',
             ('args', 'sap.ip'), 'ip',
             '239.255.255.255',
             label='SAP Multicast IP',
             tooltip='SAP announcement multicast address.\n'
                     'Default: 239.255.255.255',
             section='RTP SAP Input'),
    ParamDef('sap.port', 'libpipewire-module-rtp-sap',
             ('args', 'sap.port'), 'port',
             9875,
             label='SAP Port',
             tooltip='SAP announcement port.\n'
                     'Default: 9875',
             section='RTP SAP Input',
             min_val=1, max_val=65535),
    ParamDef('sap.net.ttl', 'libpipewire-module-rtp-sap',
             ('args', 'net.ttl'), 'int',
             32,
             label='SAP TTL',
             tooltip='Time-to-live for SAP packets.\n'
                     '1 = lokales Subnetz, 32 = Site.',
             section='RTP SAP Input',
             min_val=1, max_val=255),
    ParamDef('sap.net.loop', 'libpipewire-module-rtp-sap',
             ('args', 'net.loop'), 'bool',
             False,
             label='Loopback (SAP)',
             tooltip='Enable loopback for SAP packets.\n'
                     'Normalerweise disabled.',
             section='RTP SAP Input'),
    ParamDef('ptp.management-socket', 'libpipewire-module-rtp-sap',
             ('args', 'ptp.management-socket'), 'string',
             '/var/run/ptp/ptp4lro',
             label='PTP Management Socket',
             tooltip='Path to ptp4l read-only UNIX domain socket.\n'
                     'Must match uds_ro_address in ptp4l.conf.',
             section='RTP SAP Input'),
    ParamDef('sap.sess.latency.msec', 'libpipewire-module-rtp-sap',
             ('args', 'sess.latency.msec'), 'int',
             3,
             label='SAP Latency (ms)',
             tooltip='Latency buffer for received AES67 streams in ms.\n'
                     'Integer values only. Lower = less latency but more risky.',
             section='RTP SAP Input',
             min_val=1, max_val=100),

    # ── RTP Sink Output ────────────────────────────────────────
    ParamDef('sink.local.ifname', 'libpipewire-module-rtp-sink',
             ('args', 'local.ifname'), 'interface',
             'eth0',
             label='Network Interface (Sink)',
             tooltip='Network interface for AES67 stream output.\n'
                     'Select the same interface as configured in the PTP tab.',
             section='RTP Sink Output'),
    ParamDef('destination.ip', 'libpipewire-module-rtp-sink',
             ('args', 'destination.ip'), 'ip',
             '239.69.150.243',
             label='Destination Multicast IP',
             tooltip='Destination multicast IP for the AES67 stream.\n'
                     '239.69.x.x range recommended for AES67.\n'
                     'For multiple sinks: different IP per stream.',
             section='RTP Sink Output'),
    ParamDef('destination.port', 'libpipewire-module-rtp-sink',
             ('args', 'destination.port'), 'port',
             5004,
             label='Destination Port',
             tooltip='Destination port for the AES67 stream.\n'
                     'Default: 5004',
             section='RTP Sink Output',
             min_val=1, max_val=65535),
    ParamDef('net.mtu', 'libpipewire-module-rtp-sink',
             ('args', 'net.mtu'), 'int',
             1280,
             label='MTU',
             tooltip='Maximum Transmission Unit for RTP packets.\n'
                     '1280 = safe for most networks.',
             section='RTP Sink Output',
             min_val=576, max_val=9000, step=100),
    ParamDef('sink.net.ttl', 'libpipewire-module-rtp-sink',
             ('args', 'net.ttl'), 'int',
             32,
             label='TTL (Sink)',
             tooltip='Time-to-live for RTP stream.\n'
                     '1 = local subnet only.',
             section='RTP Sink Output',
             min_val=1, max_val=255),
    ParamDef('sink.net.loop', 'libpipewire-module-rtp-sink',
             ('args', 'net.loop'), 'bool',
             False,
             label='Loopback (Sink)',
             tooltip='Enable loopback for RTP stream.',
             section='RTP Sink Output'),
    ParamDef('sess.min-ptime', 'libpipewire-module-rtp-sink',
             ('args', 'sess.min-ptime'), 'int',
             1,
             label='Min Packet-Time (ms)',
             tooltip='Minimum packet duration in ms.\n'
                     'Should equal max-ptime.',
             section='RTP Sink Output',
             min_val=1, max_val=100),
    ParamDef('sess.max-ptime', 'libpipewire-module-rtp-sink',
             ('args', 'sess.max-ptime'), 'int',
             1,
             label='Max Packet-Time (ms)',
             tooltip='Maximum packet duration in ms.\n'
                     '1 ms works with most devices.',
             section='RTP Sink Output',
             min_val=1, max_val=100),
    ParamDef('sess.name', 'libpipewire-module-rtp-sink',
             ('args', 'sess.name'), 'string',
             '"PipeWire RTP stream"',
             label='Session-Name',
             tooltip='Name of the AES67 stream.\n'
                     'For multiple sinks: use unique names.',
             section='RTP Sink Output'),
    ParamDef('sess.media', 'libpipewire-module-rtp-sink',
             ('args', 'sess.media'), 'string',
             '"audio"',
             label='Medien-Typ',
             tooltip='Media type of the stream (usually "audio").',
             section='RTP Sink Output'),
    ParamDef('sess.ts-refclk', 'libpipewire-module-rtp-sink',
             ('args', 'sess.ts-refclk'), 'string',
             '"ptp=traceable"',
             label='Timestamp Reference Clock',
             tooltip='Reference clock for RTP timestamps.\n'
                     '"ptp=traceable" = PTP-synchronisiert.',
             section='RTP Sink Output'),
    ParamDef('sess.ts-offset', 'libpipewire-module-rtp-sink',
             ('args', 'sess.ts-offset'), 'int',
             0,
             label='Timestamp Offset',
             tooltip='Offset for RTP timestamps in ms.',
             section='RTP Sink Output',
             min_val=-1000, max_val=1000),
    ParamDef('sess.ts-direct', 'libpipewire-module-rtp-sink',
             ('args', 'sess.ts-direct'), 'bool',
             False,
             label='Direct Timestamps',
             tooltip='Synchronize RTP timestamps directly against the PTP driver.\n'
                     'Can reduce latency when reference clocks match.',
             section='RTP Sink Output'),
    ParamDef('sink.sess.latency.msec', 'libpipewire-module-rtp-sink',
             ('args', 'sess.latency.msec'), 'int',
             3,
             label='Sink Latency (ms)',
             tooltip='Latency buffer for the outgoing AES67 stream in ms.\n'
                     'Integer values only.',
             section='RTP Sink Output',
             min_val=1, max_val=100),
    ParamDef('audio.format', 'libpipewire-module-rtp-sink',
             ('args', 'audio.format'), 'choice',
             '"S24BE"',
             label='Audio-Format',
             tooltip='AES67-Audio-Format.\n'
                     'S24BE = 24-bit Big-Endian (AES67 default).',
             section='RTP Sink Output',
             choices=['"S16BE"', '"S24BE"', '"S32BE"', '"F32BE"']),
    ParamDef('audio.rate', 'libpipewire-module-rtp-sink',
             ('args', 'audio.rate'), 'choice',
             48000,
             label='Sample-Rate',
             tooltip='Sample rate in Hz.\n'
                     'AES67 compatible: 48000 (default).\n'
                     '96000 also possible.',
             section='RTP Sink Output',
             choices=[48000, 96000]),
    ParamDef('audio.channels', 'libpipewire-module-rtp-sink',
             ('args', 'audio.channels'), 'int',
             2,
             label='Channels',
             tooltip='Number of audio channels in the stream.\n'
                     '2 = Stereo.',
             section='RTP Sink Output',
             min_val=1, max_val=64),
    ParamDef('node.channel-names', 'libpipewire-module-rtp-sink',
             ('args', 'node.channel-names'), 'multiline',
             '["CH1", "CH2"]',
             label='Channel Names',
              tooltip='Names of the audio channels.\n'
                      'Visible to AES67 receivers.\n'
                      'Enter comma-separated values, e.g.: CH1, CH2',
             section='RTP Sink Output'),

    # ── stream.props (RTP Sink) ────────────────────────────────
    ParamDef('sp.node.name', 'libpipewire-module-rtp-sink',
             ('args', 'stream.props', 'node.name'), 'string',
             '"rtp-sink"',
             label='Node-Name (Props)',
             tooltip='PipeWire node name of the AES67 stream.\n'
                     'For multiple sinks: use unique names.',
             section='RTP Sink Output'),
    ParamDef('sp.node.always-process', 'libpipewire-module-rtp-sink',
             ('args', 'stream.props', 'node.always-process'), 'bool',
             True,
             label='Always Process',
             tooltip='Keep the node always active, even without a connection.',
             section='RTP Sink Output'),
    ParamDef('sp.rtp.ntp', 'libpipewire-module-rtp-sink',
             ('args', 'stream.props', 'rtp.ntp'), 'int',
             0,
             label='RTP NTP-Modus',
             tooltip='NTP mode for RTP timestamps.\n'
                     '0 = automatic.',
             section='RTP Sink Output',
             min_val=0, max_val=3),
    ParamDef('sp.rtp.fetch-ts-refclk', 'libpipewire-module-rtp-sink',
             ('args', 'stream.props', 'rtp.fetch-ts-refclk'), 'bool',
             True,
             label='Fetch Reference Clock',
             tooltip='Automatically fetch the PTP reference clock for timestamps.',
             section='RTP Sink Output'),
]

# ── Lookup-Map ─────────────────────────────────────────────────
PARAM_MAP: dict[str, ParamDef] = {p.key: p for p in CONFIG_PARAMS}

# ── Section Order ──────────────────────────────────────────────
SECTION_ORDER = [
    'PTP Clock',
    'RTP SAP Input',
    'RTP Sink Output',
    'Expert',
]


def get_params_for_section(section: str) -> list[ParamDef]:
    return [p for p in CONFIG_PARAMS if p.section == section and not p.advanced]


def get_advanced_params_for_section(section: str) -> list[ParamDef]:
    return [p for p in CONFIG_PARAMS if p.section == section and p.advanced]
