# AES67 Config-Editor Regressionstest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wiederholbarer Regressions-Test für die AES67-Config-Editor-Änderungen (Reset-Defaults, Duplikatzeilen, System-Clock-Roundtrip), ausführbar mit `python3 tests/test_aes67_reset.py`.

**Architecture:** Ein einzelnes dependency-freies Skript baut denselben `AES67SettingsDialog` offscreen auf wie die App, klickt die Pfade durch (normal → System-Clock → zurück, Stock-Apply, Reset) und zählt die entstandenen Config-Key-Zeilen. Alles gegen Temp-Kopien von `/usr/share/pipewire/pipewire-aes67.conf` – das echte `~/.config/pipewire/pipewire-aes67.conf` wird nie beschrieben.

**Tech Stack:** Python 3, PyQt6 (bereits Projekt-Dependency), `QT_QPA_PLATFORM=offscreen`. **Kein pytest** (nicht installiert, kein Setup im Projekt) → reines Skript, Exit-Code 0 = ok / 1 = Fehler.

**Spec:** Die zu testenden Verhaltensregeln stammen aus `AGENTS.md` (Abschnitt „Config Editor“) und dem Commit `b56703b`.

## Global Constraints
- Keine neuen Abhängigkeiten (kein pytest, kein tox, kein Makefile-Zwang)
- Test läuft root-frei und ohne Display (`QT_QPA_PLATFORM=offscreen`)
- Test darf QSettings `sync67/ptp_settings selected_interface` nur temporär setzen und im `finally` zurücksetzen
- Erweiterbarkeit: neuer Check = neue `check_*()`-Funktion, kein neues File
- `AGENTS.md` ist gitignored → dortige Änderungen nicht committen

---

### Task 1: `tests/test_aes67_reset.py`

**Files:**
- Create: `tests/test_aes67_reset.py`

**Interfaces:**
- Consumes: `core.aes67_config.AES67Config`, `core.aes67_config._KV_RE`, `ui.aes67_settings_dialog.AES67SettingsDialog`
- Produces: `main()` (Exit-Code 0/1), Hilfsfunktionen `build()`, `counts()`, `deviating()`, `check()`

- [ ] **Step 1: Test-File schreiben** (vollständiger Inhalt liegt in der Ausführungssession; Kern: `sys.path.insert(0, REPO)` sonst greift `import core…` nicht, QSettings-Rücksetzung im `finally`, drei `check_*`-Funktionen mit 9 Checks)

- [ ] **Step 2: Grün – Test ausführen**
  Run: `python3 tests/test_aes67_reset.py`
  Expected: `FAILS: NONE`, Exit-Code 0

- [ ] **Step 3: Rot – Regression künstlich erzeugen (Beweis, dass der Test etwas sieht)**
  In `core/aes67_config.py` `uncomment_key()`: die Zeile `self._parse()` auskommentieren.
  Run: `python3 tests/test_aes67_reset.py`
  Expected: `FAIL` mit `keine Key-Zeile doppelt/verloren -> {'clock.interface': …}`, Exit-Code 1

- [ ] **Step 4: Grün – Änderung zurücknehmen**
  `self._parse()` in `uncomment_key()` wieder aktivieren.
  Run: `python3 tests/test_aes67_reset.py`
  Expected: `FAILS: NONE`, Exit-Code 0

- [ ] **Step 5: Commit**
  `git add tests/test_aes67_reset.py && git commit -m "tests: add AES67 config editor regression test"`

### Task 2: AGENTS.md – Test-Abschnitt

**Files:**
- Modify: `AGENTS.md` („Bekannte Einschränkungen“: „Keine Build/Test/Lint-Konfiguration vorhanden“ → durch Test-Hinweis ersetzen; neuer Abschnitt „### Tests“ mit Ausführungs-Befehl und Erweiterungsanleitung)

- [ ] **Step 1:** AGENTS.md editieren, kein Commit (gitignored)

## Selbst-Review
- Spec-Abdeckung: Reset-Defaults (max_resync/resync.ms/ptime/latency/.bak), Duplikate (Roundtrip-Delta, Stock-Apply), System-Clock-Checkbox-Roundtrip, unangetastete kommentierte Keys, keine Deviations nach Reset → alle in Task 1 abgebildet.
- Keine Platzhalter, keine Abhängigkeit auf nicht definierte Symbole.
