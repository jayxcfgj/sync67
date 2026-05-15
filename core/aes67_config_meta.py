"""Metadaten für alle Parameter der pipewire-aes67.conf."""

from typing import Any


class ParamDef:
    __slots__ = ('key', 'module', 'path', 'type', 'default',
                 'label', 'tooltip', 'section', 'advanced',
                 'choices', 'min_val', 'max_val', 'step')

    def __init__(self, key: str, module: str, path: str,
                 ptype: str, default: Any,
                 label: str = '', tooltip: str = '',
                 section: str = 'Expert', advanced: bool = False,
                 choices: list = None,
                 min_val=None, max_val=None, step=None):
        self.key = key
        self.module = module
        self.path = path
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
             'args.clock.interface', 'interface',
             '"eth0"',
             label='Netzwerk-Interface (PHC)',
             tooltip='Netzwerkschnittstelle für die PTP Hardware Clock (PHC).\n'
                     'Wird genutzt um automatisch das passende /dev/ptpX zu finden.\n'
                     'Bei Problemen: "System-Clock verwenden" aktivieren.',
             section='PTP Clock'),
    ParamDef('clock.device', 'context.objects',
             'args.clock.device', 'string',
             '"/dev/ptp0"',
             label='PHC Gerät',
             tooltip='PTP Hardware Clock-Gerät.\n'
                     'Wird nur verwendet wenn kein Interface angegeben ist.',
             section='PTP Clock'),
    ParamDef('clock.id', 'context.objects',
             'args.clock.id', 'choice',
             None,
             label='Clock-ID',
             tooltip='Alternative Clock-Quelle.\n'
                     '"tai" = CLOCK_TAI (auch von NTP syncbar).\n'
                     'Leer lassen = automatisch via Interface/Device.',
             section='PTP Clock',
             choices=['', 'tai']),
    ParamDef('clock.name', 'context.objects',
             'args.clock.name', 'string',
             '"clock.system.ptp0"',
             label='Clock-Name',
             tooltip='Name der PTP Clock.\n'
                     'Wird von anderen Modulen referenziert.',
             section='PTP Clock'),
    ParamDef('priority.driver', 'context.objects',
             'args.priority.driver', 'int',
             100000,
             label='Driver-Priorität',
             tooltip='Priorität des PTP-Treibers.\n'
                     'Niedrigerer Wert = höhere Priorität.',
             section='PTP Clock',
             min_val=0, max_val=1000000, step=1000),
    ParamDef('resync.ms', 'context.objects',
             'args.resync.ms', 'float',
             1.5,
             label='Resync-Intervall (ms)',
             tooltip='Zeitraum in ms nach dem eine Neu-Synchronisation\n'
                     'der Clock erzwungen wird.\n'
                     'Niedriger = häufigere Resyncs.',
             section='PTP Clock',
             min_val=0.1, max_val=60.0, step=0.1),
    ParamDef('object.export', 'context.objects',
             'args.object.export', 'bool',
             True,
             label='Clock exportieren',
             tooltip='Die PTP Clock als PipeWire-Objekt exportieren.\n'
                     'Muss aktiviert sein damit andere Module sie nutzen können.',
             section='PTP Clock'),

    # ── System-Clock Fallback (PTP Clock) ──────────────────────
    ParamDef('system.clock.enabled', 'context.objects',
             'args.clock.interface', 'bool',
             False,
             label='System-Clock verwenden (PHC deaktivieren)',
             tooltip='Wenn aktiviert: clock.interface wird auskommentiert.\n'
                     'Die System-Clock wird statt der PHC verwendet.\n'
                     'Nötig wenn die App als root läuft und PHC Timestamp 0 liefert.',
             section='PTP Clock'),

    # ── RT-Modul (Expert) ──────────────────────────────────────
    ParamDef('nice.level', 'libpipewire-module-rt',
             'args.nice.level', 'int',
             -11,
             label='Nice-Level',
             tooltip='Nice-Wert für Echtzeit-Threads.\n'
                     'Negativ = höhere Priorität.',
             section='Expert', advanced=True,
             min_val=-20, max_val=19),
    ParamDef('rt.prio', 'libpipewire-module-rt',
             'args.rt.prio', 'int',
             83,
             label='RT-Priorität',
             tooltip='Echtzeit-Thread-Priorität (1-99).\n'
                     'Höher = wichtigere Threads.',
             section='Expert', advanced=True,
             min_val=1, max_val=99),
    ParamDef('rlimits.enabled', 'libpipewire-module-rt',
             'args.rlimits.enabled', 'bool',
             True,
             label='rlimits aktivieren',
             tooltip='Ressourcenlimits für Echtzeit-Threads aktivieren.',
             section='Expert', advanced=True),
    ParamDef('rtkit.enabled', 'libpipewire-module-rt',
             'args.rtkit.enabled', 'bool',
             False,
             label='RTKit aktivieren',
             tooltip='RTKit-DBus-Service für Echtzeit-Priorität verwenden.\n'
                     'Alternativ zu normalen rlimits.',
             section='Expert', advanced=True),

    # ── RTP SAP Input ──────────────────────────────────────────
    ParamDef('sap.local.ifname', 'libpipewire-module-rtp-sap',
             'args.local.ifname', 'interface',
             'eth0',
             label='Netzwerk-Interface (SAP)',
             tooltip='Netzwerkschnittstelle für den SAP-Empfang.\n'
                     'Auf dieser Schnittstelle wird nach AES67-Streams gesucht.',
             section='RTP SAP Input'),
    ParamDef('sap.ip', 'libpipewire-module-rtp-sap',
             'args.sap.ip', 'ip',
             '239.255.255.255',
             label='SAP Multicast-IP',
             tooltip='SAP-Ankündigungs-Multicast-Adresse.\n'
                     'Standard: 239.255.255.255',
             section='RTP SAP Input'),
    ParamDef('sap.port', 'libpipewire-module-rtp-sap',
             'args.sap.port', 'port',
             9875,
             label='SAP Port',
             tooltip='SAP-Ankündigungs-Port.\n'
                     'Standard: 9875',
             section='RTP SAP Input',
             min_val=1, max_val=65535),
    ParamDef('sap.net.ttl', 'libpipewire-module-rtp-sap',
             'args.net.ttl', 'int',
             32,
             label='SAP TTL',
             tooltip='Time-To-Live für SAP-Pakete.\n'
                     '1 = lokales Subnetz, 32 = Site.',
             section='RTP SAP Input',
             min_val=1, max_val=255),
    ParamDef('sap.net.loop', 'libpipewire-module-rtp-sap',
             'args.net.loop', 'bool',
             False,
             label='Loopback (SAP)',
             tooltip='Loopback für SAP-Pakete aktivieren.\n'
                     'Normalerweise deaktiviert.',
             section='RTP SAP Input'),
    ParamDef('ptp.management-socket', 'libpipewire-module-rtp-sap',
             'args.ptp.management-socket', 'string',
             '"/var/run/ptp4lro"',
             label='PTP Management Socket',
             tooltip='UNIX-Socket für PTP-Management-Nachrichten.\n'
                     'Nur nötig bei ptp4l Version 4.',
             section='RTP SAP Input'),
    ParamDef('sess.latency.msec.sap', 'libpipewire-module-rtp-sap',
             'args.sess.latency.msec', 'int',
             3,
             label='SAP Latenz (ms)',
             tooltip='Latenzpuffer für empfangene AES67-Streams in ms.\n'
                     'Nur Integer-Werte. Niedriger = weniger Latenz aber riskanter.',
             section='RTP SAP Input',
             min_val=1, max_val=100),

    # ── RTP Sink Output ────────────────────────────────────────
    ParamDef('sink.local.ifname', 'libpipewire-module-rtp-sink',
             'args.local.ifname', 'interface',
             'eth0',
             label='Netzwerk-Interface (Sink)',
             tooltip='Netzwerkschnittstelle für den AES67-Stream-Ausgang.',
             section='RTP Sink Output'),
    ParamDef('destination.ip', 'libpipewire-module-rtp-sink',
             'args.destination.ip', 'ip',
             '239.69.150.243',
             label='Ziel Multicast-IP',
             tooltip='Ziel-Multicast-IP für den AES67-Stream.\n'
                     '239.69.x.x Bereich für AES67 empfohlen.\n'
                     'Bei mehreren Sinks: andere IP pro Stream.',
             section='RTP Sink Output'),
    ParamDef('destination.port', 'libpipewire-module-rtp-sink',
             'args.destination.port', 'port',
             5004,
             label='Ziel Port',
             tooltip='Ziel-Port für den AES67-Stream.\n'
                     'Standard: 5004',
             section='RTP Sink Output',
             min_val=1, max_val=65535),
    ParamDef('net.mtu', 'libpipewire-module-rtp-sink',
             'args.net.mtu', 'int',
             1280,
             label='MTU',
             tooltip='Maximum Transmission Unit für RTP-Pakete.\n'
                     '1280 = sicher für die meisten Netzwerke.',
             section='RTP Sink Output',
             min_val=576, max_val=9000, step=100),
    ParamDef('sink.net.ttl', 'libpipewire-module-rtp-sink',
             'args.net.ttl', 'int',
             32,
             label='TTL (Sink)',
             tooltip='Time-To-Live für RTP-Stream.\n'
                     '1 = nur lokales Subnetz.',
             section='RTP Sink Output',
             min_val=1, max_val=255),
    ParamDef('sink.net.loop', 'libpipewire-module-rtp-sink',
             'args.net.loop', 'bool',
             False,
             label='Loopback (Sink)',
             tooltip='Loopback für RTP-Stream aktivieren.',
             section='RTP Sink Output'),
    ParamDef('sess.min-ptime', 'libpipewire-module-rtp-sink',
             'args.sess.min-ptime', 'int',
             1,
             label='Min Packet-Time (ms)',
             tooltip='Minimale Paketdauer in ms.\n'
                     'Sollte gleich max-ptime sein.',
             section='RTP Sink Output',
             min_val=1, max_val=100),
    ParamDef('sess.max-ptime', 'libpipewire-module-rtp-sink',
             'args.sess.max-ptime', 'int',
             1,
             label='Max Packet-Time (ms)',
             tooltip='Maximale Paketdauer in ms.\n'
                     '1 ms funktioniert mit den meisten Geräten.',
             section='RTP Sink Output',
             min_val=1, max_val=100),
    ParamDef('sess.name', 'libpipewire-module-rtp-sink',
             'args.sess.name', 'string',
             '"PipeWire RTP stream"',
             label='Session-Name',
             tooltip='Name des AES67-Streams.\n'
                     'Bei mehreren Sinks: eindeutigen Namen vergeben.',
             section='RTP Sink Output'),
    ParamDef('sess.media', 'libpipewire-module-rtp-sink',
             'args.sess.media', 'string',
             '"audio"',
             label='Medien-Typ',
             tooltip='Medientyp des Streams (meist "audio").',
             section='RTP Sink Output'),
    ParamDef('sess.ts-refclk', 'libpipewire-module-rtp-sink',
             'args.sess.ts-refclk', 'string',
             '"ptp=traceable"',
             label='Timestamp-Referenz-Clock',
             tooltip='Referenz-Clock für RTP-Timestamps.\n'
                     '"ptp=traceable" = PTP-synchronisiert.',
             section='RTP Sink Output'),
    ParamDef('sess.ts-offset', 'libpipewire-module-rtp-sink',
             'args.sess.ts-offset', 'int',
             0,
             label='Timestamp-Offset',
             tooltip='Offset für RTP-Timestamps in ms.',
             section='RTP Sink Output',
             min_val=-1000, max_val=1000),
    ParamDef('sess.ts-direct', 'libpipewire-module-rtp-sink',
             'args.sess.ts-direct', 'bool',
             False,
             label='Direkte Timestamps',
             tooltip='RTP-Timestamps direkt gegen PTP-synchronisierten Driver.\n'
                     'Kann Latenz reduzieren wenn Referenz-Clocks identisch sind.',
             section='RTP Sink Output'),
    ParamDef('sink.latency', 'libpipewire-module-rtp-sink',
             'args.sess.latency.msec', 'int',
             3,
             label='Sink Latenz (ms)',
             tooltip='Latenzpuffer für den ausgehenden AES67-Stream in ms.\n'
                     'Nur Integer-Werte.',
             section='RTP Sink Output',
             min_val=1, max_val=100),
    ParamDef('audio.format', 'libpipewire-module-rtp-sink',
             'args.audio.format', 'choice',
             '"S24BE"',
             label='Audio-Format',
             tooltip='AES67-Audio-Format.\n'
                     'S24BE = 24 Bit Big-Endian (AES67-Standard).',
             section='RTP Sink Output',
             choices=['"S16BE"', '"S24BE"', '"S32BE"', '"F32BE"']),
    ParamDef('audio.rate', 'libpipewire-module-rtp-sink',
             'args.audio.rate', 'choice',
             48000,
             label='Sample-Rate',
             tooltip='Abfastrate in Hz.\n'
                     'AES67-unterstützt: 48000 (Standard).\n'
                     '44100 = nicht AES67-kompatibel.',
             section='RTP Sink Output',
             choices=[44100, 48000, 96000]),
    ParamDef('audio.channels', 'libpipewire-module-rtp-sink',
             'args.audio.channels', 'int',
             2,
             label='Kanäle',
             tooltip='Anzahl Audiokanäle im Stream.\n'
                     '2 = Stereo.',
             section='RTP Sink Output',
             min_val=1, max_val=64),
    ParamDef('node.channel-names', 'libpipewire-module-rtp-sink',
             'args.node.channel-names', 'multiline',
             '["CH1", "CH2"]',
             label='Kanalnamen',
             tooltip='Namen der Audiokanäle.\n'
                     'Für AES67-Empfänger sichtbar.\n'
                     'Format: ["CH1", "CH2", ...]',
             section='RTP Sink Output'),

    # ── stream.props (RTP Sink) ────────────────────────────────
    ParamDef('sp.node.name', 'libpipewire-module-rtp-sink',
             'args.stream.props.node.name', 'string',
             '"rtp-sink"',
             label='Node-Name (Props)',
             tooltip='PipeWire-Node-Name des AES67-Streams.\n'
                     'Bei mehreren Sinks: eindeutigen Namen vergeben.',
             section='RTP Sink Output'),
    ParamDef('sp.node.always-process', 'libpipewire-module-rtp-sink',
             'args.stream.props.node.always-process', 'bool',
             True,
             label='Immer verarbeiten',
             tooltip='Node immer aktiv halten, auch ohne Verbindung.',
             section='RTP Sink Output'),
    ParamDef('sp.rtp.ntp', 'libpipewire-module-rtp-sink',
             'args.stream.props.rtp.ntp', 'int',
             0,
             label='RTP NTP-Modus',
             tooltip='NTP-Modus für RTP-Timestamps.\n'
                     '0 = automatisch.',
             section='RTP Sink Output',
             min_val=0, max_val=3),
    ParamDef('sp.rtp.fetch-ts-refclk', 'libpipewire-module-rtp-sink',
             'args.stream.props.rtp.fetch-ts-refclk', 'bool',
             True,
             label='Referenz-Clock abrufen',
             tooltip='PTP-Referenz-Clock für Timestamps automatisch abrufen.',
             section='RTP Sink Output'),
]

# ── Lookup-Map ─────────────────────────────────────────────────
PARAM_MAP: dict[str, ParamDef] = {p.key: p for p in CONFIG_PARAMS}

# ── Section-Order für Tabs ─────────────────────────────────────
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
