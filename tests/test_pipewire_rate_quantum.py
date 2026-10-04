#!/usr/bin/env python3
"""Tests fuer Rate/Quantum-Dropdowns im PipeWire-Tab.

Covered:
  1) Nutzer-Auswahl Rate ueberlebt die 2-s-Timer-Ticks (Refresh-Problem)
  2) Nutzer-Auswahl Quantum (Dropdown) ueberlebt die Timer-Ticks
  3) Nutzer-Eingabe Quantum per Tippen (editierbar) ueberlebt den Tick
  4) Status-Labels bleiben live (zeigen weiter den Systemwert)
  5) Apply fuehrt den Write aus und hebt die Sperre auf
  6) Refresh-Buttons (a/b) heben die Sperre auf

Run:   python3 tests/test_pipewire_rate_quantum.py
Exit:  0 = alle Checks ok, 1 = mindestens ein Check fehlgeschlagen

Root-frei, ohne Display (offscreen), kein PipeWire noetig: _run ist
durch fixen Test-Output ersetzt, der den Normalzustand abbildet
(force-* = 0, clock.rate = 48000, ein laeufiges Node mit quantum 1024).
Erweiterung: neue check_*()-Funktion in main().
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)  # sonst greift "import ui..." nicht

from PyQt6.QtWidgets import QApplication

from ui.pipewire_tab import PipeWireTab

FAILS = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}"
          + (f" -> {detail}" if not cond else ""))
    if not cond:
        FAILS.append(f"{name} ({detail})")


def meta(key, value):
    return (f'Found "settings" metadata 33\n'
            f"update: id:0 key:'{key}' value:'{value}' type:''\n")


def build():
    """PipeWire-Tab mit gestopptem Timer und fixem Daten-Ersatz."""
    tab = PipeWireTab()
    tab._timer.stop()
    tab.writes = []

    def fake_run(cmd, timeout=5):
        cmd = list(cmd)
        if len(cmd) == 6:  # Setzen: ... 0 <key> <value>
            tab.writes.append(cmd)
            return ""
        key = cmd[-1]
        return {
            "clock.force-rate": meta(key, 0),
            "clock.rate": meta(key, 48000),
            "clock.force-quantum": meta(key, 0),
            "clock.quantum": meta(key, 1024),
        }.get(key, "")

    tab._run = fake_run
    tab._last_nodes = [{
        "state": "Running", "rate": "48000", "quantum": "1024",
        "xruns": "0", "name": "test-node", "id": "12",
        "wait": "0", "busy": "0", "fmt": "s32", "ch": "2",
    }]
    return tab


def user_select_rate(tab, index):
    """Simuliert Nutzer-Klick im Rate-Dropdown (activated = nur Nutzer)."""
    tab.rate_combo.setCurrentIndex(index)
    tab.rate_combo.activated.emit(index)


def user_select_quantum(tab, text):
    """Simuliert Wahl im Quantum-Dropdown."""
    tab.q_combo.setCurrentText(text)
    tab.q_combo.activated.emit(tab.q_combo.currentIndex())


def user_type_quantum(tab, text):
    """Simuliert Tippen ins editierbare Quantum-Feld."""
    tab.q_combo.lineEdit().setText(text)
    tab.q_combo.lineEdit().textEdited.emit(text)


def check_rate_kept():
    print("1) Rate-Auswahl 96000 ueberlebt die Timer-Ticks")
    tab = build()
    user_select_rate(tab, 1)  # 96000
    tab._update_all()
    tab._update_all()
    check("Combo bleibt bei 96000",
          tab.rate_combo.currentText() == "96000",
          repr(tab.rate_combo.currentText()))


def check_quantum_kept():
    print("2) Quantum-Auswahl 512 ueberlebt die Timer-Ticks")
    tab = build()
    user_select_quantum(tab, "512")
    tab._update_all()
    tab._update_all()
    check("Combo bleibt bei 512",
          tab.q_combo.currentText() == "512",
          repr(tab.q_combo.currentText()))


def check_quantum_typed():
    print("3) getipptes Quantum 256 ueberlebt den Tick")
    tab = build()
    user_type_quantum(tab, "256")
    tab._update_all()
    check("Combo bleibt bei 256",
          tab.q_combo.currentText() == "256",
          repr(tab.q_combo.currentText()))


def check_labels_live():
    print("4) Status-Labels bleiben live (Systemwert)")
    tab = build()
    user_select_rate(tab, 1)
    user_select_quantum(tab, "512")
    tab._update_all()
    check("Rate-Label zeigt Systemwert 48000",
          "48000" in tab.rate_status.text(), repr(tab.rate_status.text()))
    check("Quantum-Label zeigt Systemwert 1024",
          "1024" in tab.q_status.text(), repr(tab.q_status.text()))


def check_apply_clears():
    print("5) Apply schreibt den Wert und hebt die Sperre auf")
    tab = build()
    user_select_quantum(tab, "512")
    tab._set_metadata("clock.force-quantum", "512")
    check("Write-Kommando ausgefuehrt",
          any(cmd[-1] == "512" for cmd in tab.writes), str(tab.writes))
    tab._update_all()
    check("Combo zeigt wieder den Systemwert",
          tab.q_combo.currentText() == "1024",
          repr(tab.q_combo.currentText()))


def check_refresh_buttons():
    print("6) Refresh-Buttons heben die Sperre auf")
    tab = build()
    user_select_rate(tab, 1)
    user_select_quantum(tab, "512")
    handler_r = getattr(tab, "_on_rate_refresh", None)
    handler_q = getattr(tab, "_on_q_refresh", None)
    check("Rate-Refresh-Handler existiert", callable(handler_r))
    check("Quantum-Refresh-Handler existiert", callable(handler_q))
    if not (callable(handler_r) and callable(handler_q)):
        return
    tab._on_rate_refresh()
    tab._on_q_refresh()
    check("Rate-Combo wieder Systemwert",
          tab.rate_combo.currentText() == "48000",
          repr(tab.rate_combo.currentText()))
    check("Quantum-Combo wieder Systemwert",
          tab.q_combo.currentText() == "1024",
          repr(tab.q_combo.currentText()))


def main():
    app = QApplication.instance() or QApplication([])

    check_rate_kept()
    check_quantum_kept()
    check_quantum_typed()
    check_labels_live()
    check_apply_clears()
    check_refresh_buttons()

    print("FAILS: NONE" if not FAILS else f"FAILS: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
