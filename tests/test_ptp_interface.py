#!/usr/bin/env python3
"""Tests fuer die PTP-Interface-Wahl (Auswahl == QSettings == ptp4l).

Covered:
  1) gespeichertes Interface existiert -> bleibt (Benutzerwahl gewinnt)
  2) gespeichertes Interface ungültig -> PHC-faehige NIC (Sysfs-Scan)
  3) keine PHC-NIC -> erstes verfuegbares Interface (Option A)
  4) keine Interfaces -> '' (Start wird geblockt)
  5) phc_interfaces() liest /sys/class/ptp-Struktur (Temp)
  6) PTPTab: QSettings == Auswahlfeld, ungültiger Wert wird ersetzt

Run:   python3 tests/test_ptp_interface.py
Exit:  0 = alle Checks ok, 1 = mindestens ein Check fehlgeschlagen

Root-frei, ohne Display (offscreen); QSettings wird im finally
zurueckgesetzt. Erweiterung: neue check_*()-Funktion in main().
"""
import os
import re
import subprocess
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)  # sonst greift "import core..." nicht

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication

from ui.ptp_tab import PTPTab

try:
    from core.net_interface import choose_interface, phc_interfaces
except Exception:
    choose_interface = None
    phc_interfaces = None

FAILS = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}"
          + (f" -> {detail}" if not cond else ""))
    if not cond:
        FAILS.append(f"{name} ({detail})")


def need(fn, name):
    if callable(fn):
        return True
    check(name, False, "core/net_interface fehlt/laedt nicht")
    return False


def live_interfaces():
    """Wie ui/ptp_tab.py: ip link show, ohne lo."""
    result = subprocess.run(["ip", "link", "show"],
                            capture_output=True, text=True, timeout=5)
    if result.returncode != 0:
        return []
    return [i for i in re.findall(r"^\d+: (\w+):", result.stdout, re.MULTILINE)
            if i != "lo"]


def check_valid_saved():
    print("1) gespeichertes Interface existiert -> bleibt")
    if not need(choose_interface, "choose_interface importiert"):
        return
    got = choose_interface("eth9", ["eth9", "eth10"], phc=["eth10"])
    check("Benutzerwahl bleibt (auch ohne PHC)", got == "eth9", repr(got))


def check_invalid_uses_phc():
    print("2) gespeichert ungultig -> PHC-NIC")
    if not need(choose_interface, "choose_interface importiert"):
        return
    got = choose_interface("gibt-es-nicht", ["enp34s0", "enp37s0"],
                           phc=["enp37s0"])
    check("PHC-NIC gewaehlt", got == "enp37s0", repr(got))
    got = choose_interface("", ["enp34s0", "enp37s0"], phc=["enp37s0"])
    check("leere Auswahl -> PHC-NIC", got == "enp37s0", repr(got))


def check_no_phc():
    print("3) keine PHC-NIC -> erstes Interface (Option A)")
    if not need(choose_interface, "choose_interface importiert"):
        return
    got = choose_interface("alt", ["eth0", "eth1"], phc=[])
    check("erstes Interface der Liste", got == "eth0", repr(got))


def check_empty():
    print("4) keine Interfaces -> leer")
    if not need(choose_interface, "choose_interface importiert"):
        return
    got = choose_interface("alt", [], phc=[])
    check("leerer String", got == "", repr(got))


def check_phc_scan():
    print("5) phc_interfaces() liest die Sysfs-Struktur")
    if not need(phc_interfaces, "phc_interfaces importiert"):
        return
    root = tempfile.mkdtemp()
    os.makedirs(os.path.join(root, "ptp0", "device", "net", "enp99s0"))
    os.makedirs(os.path.join(root, "ptp1", "device", "net", "enp42s0"))
    os.makedirs(os.path.join(root, "ptp2", "device"))  # ohne net -> ignorieren
    got = phc_interfaces(root)
    check("beide NICs gefunden", got == ["enp99s0", "enp42s0"], str(got))
    check("leerer Pfad -> []", phc_interfaces("/gibt-es-nicht") == [])


def check_tab_sync():
    print("6) PTPTab: QSettings == Auswahlfeld, ungultiger Wert ersetzt")
    qs = QSettings("sync67", "ptp_settings")
    had = qs.contains("selected_interface")
    old = qs.value("selected_interface", "", type=str)
    try:
        qs.setValue("selected_interface", "gibt-es-nicht")
        tab = PTPTab()
        combo = tab.interface_combo.currentText()
        saved = qs.value("selected_interface", "", type=str)
        check("QSettings == Auswahlfeld", saved == combo,
              f"{saved!r} vs {combo!r}")
        check("ungueltiger Wert ersetzt", saved != "gibt-es-nicht", repr(saved))
        live = live_interfaces()
        check("Auswahl existiert (ip link)", combo in live,
              f"{combo!r} not in {live}")
        if need(phc_interfaces, "phc_interfaces importiert"):
            phc = phc_interfaces()
            if phc:
                check("PHC-NIC gewaehlt", saved in phc,
                      f"{saved!r} not in {phc}")
        tab.deleteLater()
    finally:
        if had:
            qs.setValue("selected_interface", old)
        else:
            qs.remove("selected_interface")


def main():
    app = QApplication.instance() or QApplication([])

    check_valid_saved()
    check_invalid_uses_phc()
    check_no_phc()
    check_empty()
    check_phc_scan()
    check_tab_sync()

    print("FAILS: NONE" if not FAILS else f"FAILS: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
