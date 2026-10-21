"""PTP-faehige Netzwerk-Interfaces erkennen – ohne Hardcode.

Auf jedem Rechner kann die NIC anders heissen; die PTP-Hardware-Uhr
(-> benoetigt fuer ptp4l -H) steht unter /sys/class/ptp/ptp*/device/net.
"""


import os
import re
import subprocess
from pathlib import Path

PTP_SYSFS = '/sys/class/ptp'


def phc_index(iface, path=PTP_SYSFS):
    """PHC-Index des Interfaces wie in `ethtool -T`, -1 wenn unbekannt.

    ptp4l braucht den Wert pro Interface-Section, sonst schlaegt der Start
    mit 'PHC device mismatch' fehl, wenn mehrere NICs im System sind.
    """
    if not iface:
        return -1
    try:
        out = subprocess.run(['ethtool', '-T', iface],
                             capture_output=True, text=True, timeout=5)
        m = re.search(r'PTP Hardware Clock:\s*(\d+)', out.stdout)
        if m:
            return int(m.group(1))
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        for ptp in sorted(Path(path).glob('ptp*')):
            net = ptp / 'device' / 'net'
            if net.is_dir() and iface in os.listdir(net):
                return int(ptp.name.replace('ptp', ''))
    except (OSError, ValueError):
        pass
    return -1


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
