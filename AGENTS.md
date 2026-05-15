# sync67 Agent Guidance

## Projektstruktur
- `ui/` – Qt Fenster, Tabs, Widgets
- `services/` – Systemdienste und Prozessverwaltung (ptp_service.py, pipewire_service.py, aes67_service.py)
- `core/` – Gemeinsame Hilfsfunktionen und Infrastruktur
- `widgets/` – Wiederverwendbare GUI-Komponenten

## Wichtige Entwicklungsprinzipien
- **Kleine Schritte**: Keine riesigen Komplettlösungen. Kleine, testbare Features.
- **Keine Überarchitektur**: Verständlich, wartbar, pragmatisch. Keine Enterprise-Patterns.
- **Modularität**: UI, Services, Systemlogik, Widgets logisch trennen. Keine riesigen Dateien.
- **Verständlichkeit vor Cleverness**: Einfache Wartbarkeit, Debugbarkeit, Erweiterbarkeit.
- **UI und Funktionalität gemeinsam entwickeln**: GUI wächst organisch mit Features. Keine vollständig designte GUI ohne Funktionalität.
- **Erst funktionierend, dann schön**: Stabilität und Funktion priorisieren, nicht perfektes UI-Design.
- **Bestehende Linux-Audio-Tools respektieren**: sync67 ersetzt nicht qpwgraph, coppwr, helvum. Fokus auf Synchronisation, Monitoring, Runtime Control, AES67 Management.
- **Strikte Trennung von UI und Logik**: UI → Service Layer → Systemprozess. GUI enthält keine direkte Systemlogik.

## Technologie-Stack
- Python 3
- Qt6 / PyQt6 (PySide6 nicht in dieser Umgebung verfügbar)
- PipeWire
- Linux PTP (ptp4l)
- Keine GNOME-spezifischen Technologien; desktop-unabhängige Architektur
- Distribution-unabhängig (Linux Mint, Debian, Ubuntu, Arch)

## Aktueller Stand
- Frühe Entwicklung / Proof-of-Concept-Phase
- `main.py` ist der Anwendungseinstiegspunkt
- PTP-Tab (MVP 0.1) vollständig implementiert
- AES67-Tab (MVP 0.2) vollständig implementiert mit:
  * Start/Stop für `pipewire-aes67`
  * Terminal-Ausgabe (schwarz/grün)
  * Config-Button (xdg-open)
  * AES67 Config Editor Button → GUI-Editor mit 4 Tabs, ~40 Parametern

### Config Editor (`core/aes67_config.py`, `core/aes67_config_meta.py`, `ui/aes67_settings_dialog.py`)
- Format-erhaltender SPA-Parser (Zeilenbasiert, Kommentare/Formatierung bleiben erhalten)
- 40 Parameter in 4 Tabs (PTP Clock, RTP SAP Input, RTP Sink Output, Expert)
- RTP-Sink-Multi-Instanz (Add/Remove Sinks mit QTabWidget)
- System-Clock-Checkbox (kommentiert `clock.interface` aus → löst PHC-Timestamp-0-Problem als root)
- Deviation-Highlighting (goldener linker Rand bei Abweichung vom Default)
- Dunkles Theme (App-Level QPalette + gezielte Stylesheets, native SpinBox/ComboBox-Pfeile bleiben sichtbar)
- Stream.rules Raw-Editor (SPA-Rohtext im Expert-Tab, Round-Trip-sicher)
- Formatierung/Ausrichtung/Leerzeichen/Kommentare bleiben beim Speichern erhalten

### Wichtige Implementation-Details
- App läuft als root → `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`, `HOME` via `SUDO_UID` setzen
- Config-Parser (`AES67Config`): `_raw_lines[]` + `_data{}` + `_line_map[]` für format-erhaltendes set() mit Fallback-Zeilenscan
- Pfade als Tupel (`('args', 'local.ifname')`) wegen Punkt-Tasten wie `clock.interface`
- Regex `_SECTION_RE`: `context\.[\w\-]+` (Hyphen in `spa-libs`)
- Regex `_KV_RE`: Negative-Lookahead `(?!\s*[\{\[])` unterscheidet `key = value` von `key = {`
- `get_raw_block`/`set_raw_block` für Rohtext-Blöcke (stream.rules)

### PipeWire Tab (MVP 0.3)
- `ui/pipewire_tab.py`: Rate/Quantum-Steuerung via `pw-metadata`, pw-top Node-Tabelle
- Sample-Rate-Dropdown: 48000, 96000, 192000 (kein 44100 – nicht AES67-konform)
- Quantum-Dropdown: 16-8192 (Zweierpotenzen), editierbar
- Status-Anzeige: Latenz (berechnet), Xruns (klickbar), DSP Load (ProgressBar)
- Node-Tabelle mit Tree-Struktur: pw-top Output wird geparst (Fixed-Width), Parent-Child via `+` Prefix
- Tabellen-Spalten: ID, Status (Running/Idle/Closed), Name, Quantum, Format, CH, DSP (Mini-Bar), Waiting, Busy, Xruns
- Update-Intervall: 2s via QTimer
- pw-top muss installiert sein, sonst leere Tabelle

### Bekannte Einschränkungen
- `context.spa-libs` wird geparst aber nicht im Editor angezeigt (wird nie verändert)
- `node.channel-names` als MultilineWidget (Array-String-Konvertierung korrigiert aber nicht mit Sonderzeichen getestet)
- `stream.rules` nur als Raw-Editor, kein strukturierter Rule-Editor
- pw-top: Spalten-Parsing per Fixed-Width (abhängig vom pw-top Output-Format)
- Xruns: lokaler Zähler, kein System-Reset möglich
- Keine Build/Test/Lint-Konfiguration vorhanden

## Beim Hinzufügen von Features
1. Modular Struktur (ui/services/core/widgets) einhalten
2. UI von Systemlogik trennen (services/ für Systembefehle)
3. Kleine, testbare Schritte
4. `docs/mvp.md` für geplante Feature-Reihenfolge beachten
5. Für Systembefehle QProcess mit Fehlerbehandlung verwenden
6. Benutzereinstellungen mit QSettings speichern
