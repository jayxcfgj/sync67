#!/usr/bin/env python3
"""Regression-Tests fuer den AES67-Config-Editor.

Covered:
  1) System-Clock-Roundtrip (normal -> system clock -> zurueck) ohne
     doppelte/verlorene Config-Key-Zeilen
  2) Apply auf eine unangetastete Stock-Config (keine Duplikate,
     kommentierte Keys bleiben kommentiert)
  3) Reset Config = Stock-Copy + sync67-Defaults + .bak + keine
     Deviation-Highlights im frisch geladenen Dialog

Run:   python3 tests/test_aes67_reset.py
Exit:  0 = alle Checks ok, 1 = mindestens ein Check fehlgeschlagen

Root-frei, ohne Display (offscreen), schreibt NUR in Temp-Verzeichnisse –
dein echtes ~/.config/pipewire/pipewire-aes67.conf bleibt unangetastet.
Erweiterung: neue check_*()-Funktion in main() hinzufuegen.
"""
import collections
import os
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)  # sonst greift "import core..." nicht

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QMessageBox

from core.aes67_config import AES67Config, _KV_RE
from ui.aes67_settings_dialog import AES67SettingsDialog

STOCK = "/usr/share/pipewire/pipewire-aes67.conf"
IFACE = "enp3s0"
FAILS = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}"
          + (f" -> {detail}" if not cond else ""))
    if not cond:
        FAILS.append(f"{name} ({detail})")


def build(iface=IFACE):
    """Stock-Config (ggf. mit sync67-Defaults) in einem Temp-File
    plus frisch gebautem Dialog – wie die App es sehen wuerde."""
    tmp = tempfile.mkdtemp()
    dst = os.path.join(tmp, "pipewire-aes67.conf")
    shutil.copy(STOCK, dst)
    cfg = AES67Config()
    cfg.load(dst)
    if iface:
        cfg.apply_sync67_defaults(iface)
        cfg.save(backup=False)
        cfg.load(dst)
    return cfg, AES67SettingsDialog(cfg, None)


def counts(path):
    """Vorkommen je Key (kommentiert oder aktiv) in der Config."""
    out = collections.Counter()
    for line in open(path):
        m = _KV_RE.match(line.strip().lstrip("#"))
        if m:
            out[m.group("key")] += 1
    return out


def deviating(dlg):
    """Widgets mit goldenem Default-Abweichungs-Rand."""
    widgets = dict(dlg.widgets)
    for tab in dlg.rtp_sink_tabs:
        widgets.update(tab.widgets)
    return [k for k, pw in widgets.items() if "f0c040" in pw.widget.styleSheet()]


def check_roundtrip():
    print("1) normal -> system clock -> zurueck")
    cfg, dlg = build()
    base = counts(cfg.get_loaded_path())
    dlg._on_apply()
    dlg.system_clock_cb.setChecked(True)
    dlg._on_apply()
    cfg2 = AES67Config()
    cfg2.load(cfg.get_loaded_path())
    dlg2 = AES67SettingsDialog(cfg2, None)
    check("System-Clock-Checkbox beim Neuladen wiederhergestellt",
          dlg2.system_clock_cb.isChecked())
    dlg2.system_clock_cb.setChecked(False)
    dlg2._on_apply()
    after = counts(cfg2.get_loaded_path())
    delta = {k: after[k] - base.get(k, 0)
             for k in after if after[k] != base.get(k, 0)}
    check("keine Key-Zeile doppelt/verloren", not delta, str(delta))


def check_stock_apply():
    print("2) Stock-Config, unangetastet angewandt")
    cfg, dlg = build(iface=None)
    before = counts(cfg.get_loaded_path())
    dlg._on_apply()
    path = dlg.config.get_loaded_path()
    after = counts(path)
    extra = {k: after[k] - before.get(k, 0)
             for k in after if after[k] > before.get(k, 0)}
    check("kein Key doppelt", all(v <= 1 for v in extra.values()),
          str(extra))
    rt = [l.strip() for l in open(path) if "rt.prio" in l]
    check("kommentiertes rt.prio bleibt unangetastet",
          bool(rt) and all(l.startswith("#") for l in rt), str(rt))


def check_reset():
    print("3) Reset Config")
    cfg, dlg = build(iface=None)
    dlg._on_reset()
    path = dlg.config.get_loaded_path()
    cfg2 = AES67Config()
    cfg2.load(path)
    check("max_resync = 4",
          cfg2.get("context.objects", 0, "args", "max_resync") == 4)
    check("resync.ms = 48",
          cfg2.get("context.objects", 0, "args", "resync.ms") == 48)
    check("sink max-ptime = 4",
          cfg2.get("context.modules", "libpipewire-module-rtp-sink",
                   "args", "sess.max-ptime") == 4)
    check("sink latency = 12",
          cfg2.get("context.modules", "libpipewire-module-rtp-sink",
                   "args", "sess.latency.msec") == 12)
    check(".bak angelegt", os.path.exists(path + ".bak"))
    dlg2 = AES67SettingsDialog(cfg2, None)
    check("keine Deviations nach Reset", not deviating(dlg2),
          str(deviating(dlg2)))


def main():
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    QMessageBox.warning = staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.Yes)

    # ptp_interface() liest QSettings – einmalig auf testbare Werte setzen
    qs = QSettings("sync67", "ptp_settings")
    old_iface = qs.value("selected_interface", "", type=str)
    if not old_iface:
        qs.setValue("selected_interface", IFACE)
    try:
        check_roundtrip()
        check_stock_apply()
        check_reset()
    finally:
        if not old_iface:
            qs.setValue("selected_interface", "")

    print("FAILS: NONE" if not FAILS else f"FAILS: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
