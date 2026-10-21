#!/usr/bin/env python3
"""Tests fuer section-aware ptp4l.conf ([global] + [interface]-Sections).

Covered:
  1) Section-Parsing: get() isoliert pro Section
  2) set() pro Section: Update + Einfuege-Position vor naechster Section
  3) Neue Section via ensure_section / auto beim set()
  4) Save-Roundtrip: Struktur (Header + Keys) bleibt erhalten
  5) Unbekannte Interface-Keys ueberleben save() (fault_badpeernet_interval)
  6) reset_to_default: Combo-Interface bevorzugt, sonst erstes ptp-faehiges,
     Interface-Defaults wie in aktueller conf, phc_index mit aufgeloestem Wert
  7) Meta-Scope: genau die conf-Belegten Keys sind 'interface'
  8) Dialog: Pro-Tab-Split (Global | Interface [name]), Apply schreibt in
     die richtige Section

Run:   python3 tests/test_ptp4l_sections.py
Exit:  0 = alle Checks ok, 1 = mindestens ein Check fehlgeschlagen

Root-frei, offscreen, nur Temp-Verzeichnisse.
Erweiterung: neue check_*()-Funktion + Aufruf in main().
"""
import os
import sys
import tempfile
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from PyQt6.QtWidgets import QApplication, QMessageBox

from core.ptp4l_config import PTP4LConfig
from core.ptp4l_config_meta import (CONFIG_PARAMS, PARAM_MAP,
                                    INTERFACE_META_KEYS)

FAILS = []

FIXTURE = """[global]
priority1\t128
logging_level\t6
network_transport\tUDPv4

[enp37s0]
delay_mechanism\tE2E
network_transport\tUDPv4
logSyncInterval\t0
fault_badpeernet_interval\t16
# time_stamping\thardware

[enp34s0]
delay_mechanism\tP2P
"""

# Interface-Defaults wie in der aktuellen /etc/linuxptp/ptp4l.conf unter
# [enp37s0] (time_stamping bewusst kommentiert -> global greift)
CONF_INTERFACE_DEFAULTS = {
    'delay_mechanism': 'E2E',
    'network_transport': 'UDPv4',
    'delayAsymmetry': '0',
    'logMinPdelayReqInterval': '0',
    'logSyncInterval': '0',
    'logAnnounceInterval': '0',
    'announceReceiptTimeout': '3',
    'logMinDelayReqInterval': '0',
    'fault_reset_interval': '4',
    'fault_badpeernet_interval': '16',
}


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}"
          + (f" -> {detail}" if not cond else ""))
    if not cond:
        FAILS.append(f"{name} ({detail})")


def tmpdir():
    return tempfile.mkdtemp(prefix="ptp4lsec_")


def write_cfg(d, text=FIXTURE):
    path = os.path.join(d, "ptp4l.conf")
    with open(path, "w") as f:
        f.write(text)
    return path


def load_cfg(path):
    c = PTP4LConfig()
    c.load(path)
    return c


def section_text(path, name):
    """Liefert den Text einer Section (von [name] bis zum naechsten Header)."""
    with open(path) as f:
        lines = f.read().split("\n")
    out, active = [], False
    for line in lines:
        if line.startswith("["):
            if active:
                break
            active = line.strip() == f"[{name}]"
            continue
        if active:
            out.append(line)
    return "\n".join(out)


# ── 1) Parsing ────────────────────────────────────────────────

def check_parse_sections():
    print("1) Section-Parsing: get() isoliert pro Section")
    d = tmpdir()
    try:
        cfg = load_cfg(write_cfg(d))
        check("global priority1 = 128", cfg.get("priority1", "global") == 128,
              repr(cfg.get("priority1", "global")))
        check("enp37s0 delay_mechanism = E2E",
              cfg.get("delay_mechanism", "enp37s0") == "E2E",
              repr(cfg.get("delay_mechanism", "enp37s0")))
        check("delay_mechanism NICHT in global",
              cfg.get("delay_mechanism", "global") is None,
              repr(cfg.get("delay_mechanism", "global")))
        check("zweite Section enp34s0 = P2P",
              cfg.get("delay_mechanism", "enp34s0") == "P2P",
              repr(cfg.get("delay_mechanism", "enp34s0")))
        check("Sections-Reihenfolge",
              cfg.get_sections() == ["global", "enp37s0", "enp34s0"],
              repr(cfg.get_sections()))
        check("kommentierter Key gelesen (Space nach #)",
              cfg.get("time_stamping", "enp37s0") == "hardware",
              repr(cfg.get("time_stamping", "enp37s0")))
        check("kommentierter State",
              cfg.get_comment_state("time_stamping", "enp37s0") is True)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ── 2) set() pro Section ──────────────────────────────────────

def check_set_per_section():
    print("2) set() pro Section inkl. Einfuege-Position")
    d = tmpdir()
    try:
        path = write_cfg(d)
        cfg = load_cfg(path)
        cfg.set("logging_level", 7, "global")
        cfg.set("logSyncInterval", -1, "enp37s0")
        cfg.set("announceReceiptTimeout", 3, "enp37s0")  # neu in Section
        cfg.set("verbose", 1, "global")                   # neu in global
        cfg.save()

        c2 = load_cfg(path)
        check("global update", c2.get("logging_level", "global") == 7)
        check("interface update", c2.get("logSyncInterval", "enp37s0") == -1)
        check("anderes Interface unveraendert",
              c2.get("logSyncInterval", "enp34s0") is None)
        check("neuer Key in enp37s0",
              c2.get("announceReceiptTimeout", "enp37s0") == 3)
        check("neuer Key in global", c2.get("verbose", "global") == 1)

        # Einfuege-Position: neue globaler Key vor [enp37s0]-Header?
        with open(path) as f:
            text = f.read()
        check("global-Key VOR Interface-Header",
              text.index("verbose") < text.index("[enp37s0]"),
              f"verbose@{text.index('verbose')} vs header@{text.index('[enp37s0]')}")
        check("interface-Key VOR naechster Section",
              text.index("announceReceiptTimeout") < text.index("[enp34s0]"))
        check("kein Key an Dateiende gehaengt",
              not text.rstrip().endswith("logSyncInterval\t-1"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ── 3) ensure_section ─────────────────────────────────────────

def check_ensure_section():
    print("3) ensure_section legt neuen Header an")
    d = tmpdir()
    try:
        path = write_cfg(d)
        cfg = load_cfg(path)
        check("vorhandene Section: False",
              cfg.ensure_section("enp37s0") is False)
        check("neue Section: True", cfg.ensure_section("enp99s0") is True)
        check("neue Section hat phc_index (auto/-1 bei unbekanntem iface)",
              cfg.get("phc_index", "enp99s0") is not None,
              repr(cfg.get("phc_index", "enp99s0")))
        cfg.set("delay_mechanism", "P2P", "enp99s0")
        cfg.save()
        c2 = load_cfg(path)
        check("Section nach Reload da", "enp99s0" in c2.get_sections(),
              repr(c2.get_sections()))
        check("Key in neuer Section",
              c2.get("delay_mechanism", "enp99s0") == "P2P")
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ── 4) Save-Roundtrip ─────────────────────────────────────────

def check_set_creates_section():
    print("3b) set() legt Section an: In-Memory konsistent, kein Duplikat")
    d = tmpdir()
    try:
        path = write_cfg(d)
        cfg = load_cfg(path)
        cfg.set("logSyncInterval", 0, "enp88s88")
        check("In-Memory get() nach set()-Anlage",
              cfg.get("logSyncInterval", "enp88s88") == 0,
              repr(cfg.get("logSyncInterval", "enp88s88")))
        cfg.set("logSyncInterval", -3, "enp88s88")
        cfg.save()
        c2 = load_cfg(path)
        n = section_text(path, "enp88s88").count("logSyncInterval\t")
        check("keine Duplikatzeile nach Update", n == 1, n)
        check("Wert im File aktualisiert",
              c2.get("logSyncInterval", "enp88s88") == -3,
              repr(c2.get("logSyncInterval", "enp88s88")))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def check_save_roundtrip():
    print("4) Save-Roundtrip: Section-Struktur bleibt")
    d = tmpdir()
    try:
        path = write_cfg(d)
        before = open(path).read()
        cfg = load_cfg(path)
        cfg.save()
        after = open(path).read()
        check("Inhalt identisch nach Speichern ohne Aenderung",
              before == after)
        check("alle Header erhalten",
              all(h in after for h in ("[global]", "[enp37s0]", "[enp34s0]")))
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ── 5) Unbekannte Interface-Keys ──────────────────────────────

def check_unknown_iface_key_survives():
    print("5) fault_badpeernet_interval ueberlebt save()")
    d = tmpdir()
    try:
        path = write_cfg(d)
        cfg = load_cfg(path)
        cfg.save()
        c2 = load_cfg(path)
        check("Key nach Save noch da",
              c2.get("fault_badpeernet_interval", "enp37s0") == 16,
              repr(c2.get("fault_badpeernet_interval", "enp37s0")))
        check("Zeile in Section-Text",
              "fault_badpeernet_interval" in section_text(path, "enp37s0"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ── 6) reset_to_default ───────────────────────────────────────

def check_reset_creates_interface_section():
    print("6) reset_to_default: Combo-Interface bevorzugt, sonst Scan")
    d = tmpdir()
    try:
        path = write_cfg(d)
        cfg = load_cfg(path)

        # Combo-Interface NICHT ptp-faehig -> erstes gefundenes
        iface = cfg.reset_to_default("enp34s0", ["enp37s0"])
        check("Scan greift wenn Combo nicht ptp-faehig", iface == "enp37s0",
              repr(iface))
        c2 = load_cfg(path)
        check("Section [enp37s0] angelegt", "enp37s0" in c2.get_sections(),
              repr(c2.get_sections()))
        check("alte Sectionen weg (Reset = Default)",
              c2.get_sections() == ["global", "enp37s0"],
              repr(c2.get_sections()))
        check("Global-Default aus Default-File",
              c2.get("priority1", "global") == 128,
              repr(c2.get("priority1", "global")))
        stext = section_text(path, "enp37s0")
        for key, val in CONF_INTERFACE_DEFAULTS.items():
            check(f"Interface-Default {key} = {val}",
                  c2.get(key, "enp37s0") is not None
                  and str(c2.get(key, "enp37s0")) == val,
                  f"got {c2.get(key, 'enp37s0')!r}, in file: {key in stext}")
        check("time_stamping kommentiert wie in aktueller conf",
              "# time_stamping" in stext, stext[:200])
        from core.net_interface import phc_index
        check("phc_index in Interface-Section (mismatch-Vermeidung)",
              "phc_index" in stext, stext[:300])
        check("phc_index = aufgeloester PHC-Index des gewaehlten Iface",
              c2.get("phc_index", iface) is not None
              and str(c2.get("phc_index", iface)) == str(phc_index(iface)),
              f"conf={c2.get('phc_index', iface)!r}, "
              f"ethtool={phc_index(iface)}")

        # Combo ptp-faehig -> Combo gewinnt
        iface2 = cfg.reset_to_default("enp37s0", ["enp37s0", "enp99s0"])
        check("Combo-Interface bevorzugt", iface2 == "enp37s0", repr(iface2))

        # Scan leer -> Combo als Fallback
        iface3 = cfg.reset_to_default("eth0", [])
        check("Scan leer -> Combo", iface3 == "eth0", repr(iface3))
        check("Section [eth0] da", "eth0" in load_cfg(path).get_sections(),
              repr(load_cfg(path).get_sections()))
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ── 7) Meta-Scope ─────────────────────────────────────────────


def check_meta_scope():
    print("7) Meta-Scope: nur conf-belegte Keys sind 'interface'")
    for key in INTERFACE_META_KEYS:
        pdef = PARAM_MAP.get(key)
        check(f"{key} existiert in Meta", pdef is not None)
        if pdef is not None:
            check(f"{key} scope=interface", pdef.scope == "interface",
                  repr(pdef.scope))
    for pdef in CONFIG_PARAMS:
        if pdef.key in INTERFACE_META_KEYS:
            continue
        check(f"{pdef.key} scope=global", pdef.scope == "global",
              repr(pdef.scope))
    check("fault_badpeernet_interval scope=interface",
          "fault_badpeernet_interval" in PARAM_MAP
          and PARAM_MAP["fault_badpeernet_interval"].scope == "interface",
          repr(PARAM_MAP.get("fault_badpeernet_interval")
               and PARAM_MAP["fault_badpeernet_interval"].scope))
    check("phc_index in INTERFACE_META_KEYS (interface-scope)",
          "phc_index" in INTERFACE_META_KEYS)
    check("phc_index ParamDef scope=interface",
          "phc_index" in PARAM_MAP
          and PARAM_MAP["phc_index"].scope == "interface",
          repr(PARAM_MAP.get("phc_index") and PARAM_MAP["phc_index"].scope))
    keys = [p.key for p in CONFIG_PARAMS]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    check("keine doppelten ParamDefs", not dupes, dupes)


# ── 8) Dialog ─────────────────────────────────────────────────

def check_dialog_two_columns():
    print("8) Dialog: Pro-Tab-Split + Apply in richtige Section")
    d = tmpdir()
    try:
        path = write_cfg(d)
        cfg = load_cfg(path)
        from ui.ptp4l_config_dialog import PTP4LConfigDialog
        dlg = PTP4LConfigDialog(cfg, "enp37s0", None)

        check("network_transport in Interface-Section",
              dlg._key_section.get("network_transport") == "enp37s0",
              repr(dlg._key_section.get("network_transport")))
        check("priority1 in global",
              dlg._key_section.get("priority1") == "global",
              repr(dlg._key_section.get("priority1")))
        check("logSyncInterval in Interface-Section",
              dlg._key_section.get("logSyncInterval") == "enp37s0")
        check("neighborPropDelayThresh global (nicht conf-belegt)",
              dlg._key_section.get("neighborPropDelayThresh") == "global",
              repr(dlg._key_section.get("neighborPropDelayThresh")))
        check("Interface-Label traegt Namen",
              any("enp37s0" in lbl.text() for lbl in dlg._iface_pane_labels),
              [lbl.text() for lbl in dlg._iface_pane_labels])
        check("phc_index in Interface-Pane",
              dlg._key_section.get("phc_index") == "enp37s0",
              repr(dlg._key_section.get("phc_index")))
        from core.net_interface import phc_index
        check("phc_index zeigt aufgeloesten Wert (nicht Global-Fallback -1)",
              dlg.widgets["phc_index"].get_value() == phc_index("enp37s0"),
              f"widget={dlg.widgets['phc_index'].get_value()!r}, "
              f"ethtool={phc_index('enp37s0')}")

        # Werte aus der richtigen Section gelesen?
        check("Interface-Wert gelesen",
              dlg.widgets["network_transport"].get_value() == "UDPv4",
              repr(dlg.widgets["network_transport"].get_value()))

        # Aendern + Apply
        dlg.widgets["network_transport"].set_value("L2")
        dlg.widgets["priority1"].set_value(200)
        dlg._on_apply()

        c2 = load_cfg(path)
        check("Interface-Section gesetzt",
              c2.get("network_transport", "enp37s0") == "L2",
              repr(c2.get("network_transport", "enp37s0")))
        check("Apply haelt fehlendes phc_index in bestehender Section nach",
              c2.get("phc_index", "enp37s0") is not None
              and str(c2.get("phc_index", "enp37s0")) == str(phc_index("enp37s0")),
              f"conf={c2.get('phc_index', 'enp37s0')!r}, "
              f"ethtool={phc_index('enp37s0')}")
        check("Apply healt AUCH andere Interface-Sections (Mismatch-Schutz)",
              c2.get("phc_index", "enp34s0") is not None
              and str(c2.get("phc_index", "enp34s0")) == str(phc_index("enp34s0")),
              f"conf={c2.get('phc_index', 'enp34s0')!r}, "
              f"ethtool={phc_index('enp34s0')}")
        check("Global-Section NICHT angetastet",
              c2.get("network_transport", "global") == "UDPv4",
              repr(c2.get("network_transport", "global")))
        check("Global priority1 gesetzt",
              c2.get("priority1", "global") == 200,
              repr(c2.get("priority1", "global")))
        check("zweite Section unveraendert",
              c2.get("delay_mechanism", "enp34s0") == "P2P")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def check_dialog_missing_section_created():
    print("8b) Dialog: fehlende Interface-Section wird beim Apply angelegt")
    d = tmpdir()
    try:
        path = write_cfg(d, "[global]\npriority1\t128\n")
        cfg = load_cfg(path)
        from ui.ptp4l_config_dialog import PTP4LConfigDialog
        dlg = PTP4LConfigDialog(cfg, "enp55s0", None)
        dlg.widgets["delay_mechanism"].set_value("P2P")
        dlg._on_apply()
        c2 = load_cfg(path)
        check("Section automatisch angelegt",
              "enp55s0" in c2.get_sections(), repr(c2.get_sections()))
        check("Wert in neuer Section",
              c2.get("delay_mechanism", "enp55s0") == "P2P")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def check_time_stamping_global_only():
    print("8d) time_stamping: nur global, nie in der Interface-Section")
    d = tmpdir()
    try:
        path = write_cfg(d)
        cfg = load_cfg(path)
        from ui.ptp4l_config_dialog import PTP4LConfigDialog

        # Neues Interface ohne Section: Apply legt Section an – aber ohne
        # time_stamping (ptp4l wuerden den aktiven Key dort ablehnen)
        dlg = PTP4LConfigDialog(cfg, "enp55s0", None)
        check("time_stamping im Global-Pane",
              dlg._key_section.get("time_stamping") == "global",
              repr(dlg._key_section.get("time_stamping")))
        dlg._on_apply()
        check("kein time_stamping in neuer Interface-Section",
              "time_stamping" not in section_text(path, "enp55s0"),
              section_text(path, "enp55s0"))
        c_new = load_cfg(path)
        check("logAnnounceInterval = Meta-Default, nicht erste Choice (-3)",
              c_new.get("logAnnounceInterval", "enp55s0") == 1,
              repr(c_new.get("logAnnounceInterval", "enp55s0")))

        # Bestehende kommentierte Zeile (Referenz-Conf) bleibt kommentiert
        cfg2 = load_cfg(path)
        dlg2 = PTP4LConfigDialog(cfg2, "enp37s0", None)
        dlg2._on_apply()
        c3 = load_cfg(path)
        check("kommentierte time_stamping-Zeile bleibt kommentiert",
              c3.get_comment_state("time_stamping", "enp37s0") is True)
        check("time_stamping-Global-Zeile aktiv",
              c3.get_comment_state("time_stamping", "global") is False
              and c3.get("time_stamping", "global") is not None,
              repr((c3.get("time_stamping", "global"),
                    c3.get_comment_state("time_stamping", "global"))))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def check_splitter_centered():
    """Beim Oeffnen soll der Spalten-Split mittig liegen (Default)."""
    print("8e) Splitter zentriert beim Oeffnen")
    d = tmpdir()
    try:
        path = write_cfg(d)
        cfg = load_cfg(path)
        from ui.ptp4l_config_dialog import PTP4LConfigDialog
        dlg = PTP4LConfigDialog(cfg, "enp37s0", None)
        dlg.resize(1200, 800)
        dlg.show()
        app = QApplication.instance()
        for _ in range(5):
            app.processEvents()  # showEvent + singleShot(0) abarbeiten
        splitters = getattr(dlg, "_splitters", [])
        # 7 Section-Tabs haben einen Splitter, der Other-Tab nicht
        check("7 Splitter (alle ausser Other)", len(splitters) == 7,
              len(splitters))
        for i, sp in enumerate(splitters):
            sizes = sp.sizes()
            if not sizes or len(sizes) < 2 or 0 in sizes:
                check(f"Splitter {i} hat zwei sichtbare Spalten", False,
                      repr(sizes))
                continue
            check(f"Splitter {i} mittig ({sizes[0]} vs {sizes[1]})",
                  abs(sizes[0] - sizes[1]) <= 4, repr(sizes))
        dlg.close()
    finally:
        shutil.rmtree(d, ignore_errors=True)


def check_real_conf_apply_unchanged():
    """Kopie der echten /etc/linuxptp/ptp4l.conf: Apply ohne Aenderungen
    darf nichts umschreiben (kein Wert, keine Kommentarzeile verloren)."""
    real = "/etc/linuxptp/ptp4l.conf"
    if not os.path.exists(real):
        print("8c) Real-Conf-Apply: uebersprungen (Datei fehlt)")
        return
    print("8c) Real-Conf-Kopie: Apply ohne Aenderungen = identisch")
    d = tmpdir()
    try:
        path = os.path.join(d, "ptp4l.conf")
        shutil.copy(real, path)
        before = open(path, "rb").read()
        cfg = load_cfg(path)
        iface = next((s for s in cfg.get_sections() if s != "global"),
                     cfg.get_sections()[0] if cfg.get_sections() else "global")
        from ui.ptp4l_config_dialog import PTP4LConfigDialog
        dlg = PTP4LConfigDialog(cfg, iface, None)
        dlg._on_apply()
        after = open(path, "rb").read()
        check("Byte-identisch nach Apply", before == after,
              f"diff {len(before)} -> {len(after)} bytes")
        check("Sectionen erhalten",
              load_cfg(path).get_sections() == cfg.get_sections(),
              repr(load_cfg(path).get_sections()))
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    app = QApplication.instance() or QApplication([])
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    QMessageBox.critical = staticmethod(lambda *a, **k: None)
    QMessageBox.question = staticmethod(
        lambda *a, **k: QMessageBox.StandardButton.Yes)

    check_parse_sections()
    check_set_per_section()
    check_ensure_section()
    check_set_creates_section()
    check_save_roundtrip()
    check_unknown_iface_key_survives()
    check_reset_creates_interface_section()
    check_meta_scope()
    check_dialog_two_columns()
    check_dialog_missing_section_created()
    check_time_stamping_global_only()
    check_splitter_centered()
    check_real_conf_apply_unchanged()

    print("FAILS: NONE" if not FAILS else f"FAILS: {FAILS}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
