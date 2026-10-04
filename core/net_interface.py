"""PTP-faehige Netzwerk-Interfaces erkennen – ohne Hardcode.

Auf jedem Rechner kann die NIC anders heissen; die PTP-Hardware-Uhr
(-> benoetigt fuer ptp4l -H) steht unter /sys/class/ptp/ptp*/device/net.
"""


import os
from pathlib import Path

PTP_SYSFS = '/sys/class/ptp'


def phc_interfaces(path=PTP_SYSFS):
    """Interfaces mit PTP-Hardware-Uhr (Reihenfolge wie die Sysfs)."""
    found = []
    try:
        ptp_dirs = sorted(Path(path).glob('ptp*'))
    except OSError:
        return []
    for ptp in ptp_dirs:
        net = ptp / 'device' / 'net'
        try:
            names = sorted(os.listdir(net))
        except OSError:
            continue
        for name in names:
            if name not in found:
                found.append(name)
    return found


def choose_interface(saved, available, phc=None):
    """PTP-Interface waehlen: Benutzerwahl, sonst PHC-NIC, sonst erstes.

    saved     – zuletzt gespeichertes Interface (darf ungueltig sein)
    available – verfuegbare Interfaces (z.B. aus 'ip link show')
    phc       – PHC-faehige Interfaces; None = selbst aus der Sysfs lesen
    """
    if saved and saved in available:
        return saved
    if phc is None:
        phc = phc_interfaces()
    for iface in available:
        if iface in phc:
            return iface
    return available[0] if available else ''
