#!/usr/bin/env python3
"""Tests fuer HW-Timestamp-Filter (hwstamp_ctl) in den PTP Start-Optionen.

Covered:
  1) Checkbox: existiert, default ON, Tooltip gesetzt
  2) Save/Load-Roundtrip der Checkbox via QSettings
  3) Befehlsliste ON: Set (`-t 1 -r 12`) + Read-Back, als letzte Eintraege
  4) Befehlsliste OFF: keine hwstamp-Zeilen
  5) Position: hwstamp bleibt hinter anderen aktivierten Optionen
  6) Fehlendes hwstamp_ctl-Binary: Skip + Terminal-Warnung, keine Zeilen

Run:   python3 tests/test_hwstamp_filter.py
Exit:  0 = alle Checks ok, 1 = mindestens ein Check fehlgeschlagen

Root-frei, offscreen, nur QSettings-Keys (im finally zurueckgesetzt).
Erweiterung: neue check_*()-Funktion + Aufruf in main().
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSettings

FAILS = []

ALL_KEYS = [
    "gro_off", "gso_off", "tso_off", "sg_off", "rx_usecs_0",
    "multicast_on", "phc_reset", "mcast_event", "mcast_pdelay", "wol_d",
    "stop_timesyncd", "stop_chronyd", "stop_ntpd", "stop_sys_time_wait",
    "hwstamp_filter",
]

SET_CMD = "sudo hwstamp_ctl -i enp55s0 -t 1 -r 12"
READ_CMD = "sudo hwstamp_ctl -i enp55s0"


def check(name, cond, detail=""):
    print(f"{'ok' if cond else '  FAIL'} {name}" + (f" -> {detail}" if not cond else ""))
    if not cond:
        FAILS.append(name)


def settings():
    return QSettings("sync67", "ptp_settings")


def _with_clean_settings(fn):
    """QSettings snapshot/restore; Keys vorher entfernt fuer Default-Tests."""
    snap = {k: settings().value(k) for k in ALL_KEYS}
    try:
        for k in ALL_KEYS:
            settings().remove(k)
        fn()
    finally:
        for k in ALL_KEYS:
            settings().remove(k)
        for k, v in snap.items():
            if v is not None:
                settings().setValue(k, v)


def set_opts(**kw):
    """Alle Optionen OFF, dann die uebergebenen ON (z.B. hwstamp_filter=True)."""
    for k in ALL_KEYS:
        settings().setValue(k, False)
    for k, v in kw.items():
        settings().setValue(k, v)


def build_commands():
    from ui.ptp_tab import PTPTab
    tab = PTPTab()
    return tab, tab._build_pre_ptp4l_commands("enp55s0")


# ── 1) Checkbox default ───────────────────────────────────────

def check_dialog_default():
    def run():
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog()
        check("Checkbox hwstamp_check existiert",
              hasattr(dlg, "hwstamp_check"))
        if hasattr(dlg, "hwstamp_check"):
            check("default ON", dlg.hwstamp_check.isChecked())
            check("Tooltip gesetzt",
                  bool(dlg.hwstamp_check.toolTip().strip()))
    _with_clean_settings(run)


# ── 2) Save/Load-Roundtrip ────────────────────────────────────

def check_dialog_roundtrip():
    def run():
        from ui.settings_dialog import SettingsDialog
        dlg = SettingsDialog()
        dlg.hwstamp_check.setChecked(False)
        dlg.save_settings()
        dlg2 = SettingsDialog()
        check("unchecked ueberlebt Save/Load",
              not dlg2.hwstamp_check.isChecked())
        dlg2.hwstamp_check.setChecked(True)
        dlg2.save_settings()
        dlg3 = SettingsDialog()
        check("checked ueberlebt Save/Load",
              dlg3.hwstamp_check.isChecked())
    _with_clean_settings(run)


# ── 3) Befehlsliste ON ────────────────────────────────────────

def check_commands_on():
    def run():
        set_opts(hwstamp_filter=True)
        _, cmds = build_commands()
        check("Set-Befehl enthalten", SET_CMD in cmds, cmds)
        check("Read-Back enthalten", READ_CMD in cmds, cmds)
        check("genau diese zwei Befehle (alle anderen Optionen OFF)",
              cmds == [SET_CMD, READ_CMD], cmds)
    _with_clean_settings(run)


# ── 4) Befehlsliste OFF ───────────────────────────────────────

def check_commands_off():
    def run():
        set_opts(hwstamp_filter=False)
        _, cmds = build_commands()
        check("keine hwstamp-Zeilen", not any("hwstamp_ctl" in c for c in cmds),
              cmds)
        check("leere Liste (keine anderen Optionen ON)", cmds == [], cmds)
    _with_clean_settings(run)


# ── 5) Position am Kettenende ─────────────────────────────────

def check_position():
    def run():
        set_opts(hwstamp_filter=True, mcast_event=True)
        _, cmds = build_commands()
        check("hwstamp-Set vorletzter Befehl", len(cmds) >= 2
              and cmds[-2] == SET_CMD, cmds)
        check("Read-Back letzter Befehl (direkt vor ptp4l)",
              cmds and cmds[-1] == READ_CMD, cmds)
        check("andere Optionen kommen zuerst",
              any("maddr" in c for c in cmds[:-2]), cmds)
    _with_clean_settings(run)


# ── 6) Fehlendes Binary ───────────────────────────────────────

def check_missing_binary():
    def run():
        from ui import ptp_tab
        set_opts(hwstamp_filter=True, mcast_event=True)
        orig_which = ptp_tab.shutil.which
        ptp_tab.shutil.which = lambda name: None
        try:
            tab, cmds = build_commands()
        finally:
            ptp_tab.shutil.which = orig_which
        check("keine hwstamp-Zeilen ohne Binary",
              not any("hwstamp_ctl" in c for c in cmds), cmds)
        check("andere Optionen trotzdem drin",
              any("maddr" in c for c in cmds), cmds)
        check("Terminal-Warnung", "hwstamp_ctl" in tab.terminal_output.toPlainText(),
              tab.terminal_output.toPlainText()[-200:])
    _with_clean_settings(run)


def main():
    app = QApplication.instance() or QApplication([])
    check_dialog_default()
    check_dialog_roundtrip()
    check_commands_on()
    check_commands_off()
    check_position()
    check_missing_binary()
    print()
    if FAILS:
        print(f"FAILS: {FAILS}")
        sys.exit(1)
    print("FAILS: NONE")
    sys.exit(0)


if __name__ == "__main__":
    main()
