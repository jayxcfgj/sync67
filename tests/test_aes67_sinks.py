#!/usr/bin/env python3
"""Regression-Tests: Mehrfach-Sinks anlegen/bearbeiten/entfernen
   + AES67-Kanal-Limit (max. 8 Channels pro Stream).

Run:   python3 tests/test_aes67_sinks.py
Exit:  0 = alle Checks ok, 1 = mindestens ein Check fehlgeschlagen

Root-frei, offscreen, schreibt NUR in Temp-Verzeichnisse.
"""
import os
import shutil
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from PyQt6.QtWidgets import QApplication, QMessageBox

from core.aes67_config import AES67Config
from core.aes67_config_meta import PARAM_MAP
from ui.aes67_settings_dialog import AES67SettingsDialog

STOCK = "/usr/share/pipewire/pipewire-aes67.conf"
FAILS = []
WARNINGS = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}"
          + (f" -> {detail}" if not cond else ""))
    if not cond:
        FAILS.append(f"{name} ({detail})")


def build():
    """Stock-Config im Temp-Verzeichnis (unveraendert)."""
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "pipewire-aes67.conf")
    shutil.copy(STOCK, path)
    cfg = AES67Config()
    cfg.load(path)
    return cfg, path


def reload_cfg(path):
    cfg = AES67Config()
    cfg.load(path)
    return cfg


def sink_indices(cfg):
    mods = cfg._data.get("context.modules", [])
    return [i for i, m in enumerate(mods)
            if isinstance(m, dict) and m.get("name") == "libpipewire-module-rtp-sink"]


def sink_args(cfg, i):
    return cfg._data["context.modules"][i].get("args", {})


def _u(value):
    """Formatierungs-Quotes ignorieren (format_value() quotet Punkte)."""
    return str(value).strip('"') if value is not None else ""


def check_add_roundtrip():
    print("1) Add Sink -> Save -> Reload")
    cfg, path = build()
    n0 = len(sink_indices(cfg))
    idx = cfg.add_rtp_sink()
    cfg.save(backup=False)
    c2 = reload_cfg(path)
    n1 = len(sink_indices(c2))
    check("Sink-Zaehler +1", n1 == n0 + 1, f"{n0} -> {n1}")
    check("zurueckgemeldeter Index ist ein rtp-sink",
          idx in sink_indices(c2), f"idx={idx}, sinks={sink_indices(c2)}")

    raw = open(path).read().splitlines()
    open_idx = next(i for i, l in enumerate(raw)
                    if l.startswith("context.modules"))
    entries = [i for i, l in enumerate(raw)
               if l.lstrip().startswith("{ name = libpipewire-module-rtp-sink")]
    close_idx = next(i for i, l in enumerate(raw[open_idx + 1:], open_idx + 1)
                     if l == "]")
    check("neuer Block liegt VOR dem schliessenden \"]\"",
          len(entries) == 2 and close_idx > max(entries),
          f"entries={entries}, close={close_idx}")


def check_unique_stream_identity():
    print("2) Eindeutige Werte des neuen Sinks")
    cfg, path = build()
    cfg.add_rtp_sink()
    cfg.save(backup=False)
    c2 = reload_cfg(path)
    idxs = sink_indices(c2)
    check("zwei Sinks vorhanden", len(idxs) == 2, f"sinks={idxs}")
    names = [_u(sink_args(c2, i).get("stream.props", {}).get("node.name"))
             for i in idxs]
    sess = [_u(sink_args(c2, i).get("sess.name")) for i in idxs]
    ips = [_u(sink_args(c2, i).get("destination.ip")) for i in idxs]
    ports = [_u(sink_args(c2, i).get("destination.port")) for i in idxs]
    check("node.name eindeutig", len(set(names)) == len(names), str(names))
    check("sess.name eindeutig", len(set(sess)) == len(sess), str(sess))
    check("destination.ip eindeutig", len(set(ips)) == len(ips), str(ips))
    check("destination.ip in 239.69.x.x (AES67/Dante)",
          all(ip.startswith("239.69.") for ip in ips), str(ips))
    check("destination.port bleibt 5004 (AES67-Default)",
          all(p == "5004" for p in ports), str(ports))


def check_set_writes_raw():
    print("3) set() fuer den neuen Sink schreibt wirklich in die Datei")
    cfg, path = build()
    idx = cfg.add_rtp_sink()
    ok = cfg.set('"9.9.9.9"', "context.modules", idx, "args", "destination.ip")
    cfg.save(backup=False)
    content = open(path).read()
    check("set() meldet Erfolg", ok)
    check("Wert landet in der Datei", "9.9.9.9" in content)


def check_remove_roundtrip():
    print("4) Remove Sink -> Save -> Reload")
    cfg, path = build()
    idx = cfg.add_rtp_sink()
    cfg.save(backup=False)
    c2 = reload_cfg(path)
    n_before = len(sink_indices(c2))
    ok = c2.remove_rtp_sink(idx)
    c2.save(backup=False)
    c3 = reload_cfg(path)
    entries = [l for l in open(path)
               if l.lstrip().startswith("{ name = libpipewire-module-rtp-sink")]
    check("remove() meldet Erfolg", ok)
    check("Sink-Zaehler -1", len(sink_indices(c3)) == n_before - 1,
          f"{n_before} -> {len(sink_indices(c3))}")
    check("Block auch aus der Datei entfernt", len(entries) == 1,
          f"{len(entries)} Eintraege")
    # Schutz: letzter Sink darf nicht entfernt werden
    check("letzter Sink bleibt gesperrt",
          not c3.remove_rtp_sink(sink_indices(c3)[0]))


def check_channel_limit_meta():
    print("5) Kanal-Limit in der Meta")
    pdef = PARAM_MAP.get("audio.channels")
    check("audio.channels max_val == 8", pdef is not None
          and pdef.max_val == 8,
          "max_val=" + str(getattr(pdef, "max_val", None)))


def _patch_warnings():
    WARNINGS.clear()

    def _warn(*a, **k):
        WARNINGS.append(" | ".join(str(x) for x in a[1:]))
        return QMessageBox.StandardButton.Ok

    QMessageBox.warning = staticmethod(_warn)


def check_gui_channel_limit():
    print("6) GUI: Warnung + Apply-Block bei mehr als 8 Kanaelen")
    cfg, path = build()
    # manuelle Aenderung in der conf: 16 Channels + 9 Channel-Namen
    cfg.set(16, "context.modules", 6, "args", "audio.channels")
    cfg.set([f'"CH{i}"' for i in range(1, 10)],
            "context.modules", 6, "args", "node.channel-names")
    cfg.save(backup=False)

    _patch_warnings()
    c2 = reload_cfg(path)
    dlg = AES67SettingsDialog(c2, None)
    check("Dialog meldet >8 bei Oeffnen (conf manuell geaendert)",
          len(WARNINGS) >= 1, f"warnings={WARNINGS}")

    # GUI-Eingabe: 9 Namen im Widget -> Apply muss blocken
    WARNINGS.clear()
    tab = dlg.rtp_sink_tabs[0]
    tab.widgets["node.channel-names"].set_value([f"CH{i}" for i in range(1, 10)])
    before = open(path).read()
    dlg._on_apply()
    after = open(path).read()
    check("Apply wird geblockt (Datei unveraendert)", before == after)
    check("Apply zeigt Warnung", len(WARNINGS) >= 1, f"warnings={WARNINGS}")


def check_dialog_add_roundtrip():
    print("7) Dialog: '+ Add Sink' -> Apply -> Editor neu oeffnen")
    cfg, path = build()
    dlg = AES67SettingsDialog(cfg, None)
    before = len(dlg.rtp_sink_tabs)
    dlg._on_add_sink()
    check("neuer Sink erscheint sofort im Dialog",
          len(dlg.rtp_sink_tabs) == before + 1,
          f"{before} -> {len(dlg.rtp_sink_tabs)}")
    dlg._on_apply()
    c2 = reload_cfg(path)
    dlg2 = AES67SettingsDialog(c2, None)
    check("Sink nach Neuladen wieder da",
          len(dlg2.rtp_sink_tabs) == before + 1,
          f"{before} -> {len(dlg2.rtp_sink_tabs)}")


def main():
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    QMessageBox.critical = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.Yes)

    check_add_roundtrip()
    check_unique_stream_identity()
    check_set_writes_raw()
    check_remove_roundtrip()
    check_channel_limit_meta()
    check_gui_channel_limit()
    check_dialog_add_roundtrip()

    print("FAILS: NONE" if not FAILS else f"FAILS: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
