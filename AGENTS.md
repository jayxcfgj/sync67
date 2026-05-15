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
- **MVP 0.1** PTP-Tab: ptp4l starten/stoppen, Sync-Status (Ampel), ethtool-Settings
- **MVP 0.2** AES67-Tab: pipewire-aes67 starten/stoppen, Config-Editor (4 Tabs, ~40 Parameter, RTP-Sink-Multi-Instanz, Dark Theme, stream.rules Raw-Editor)
- **MVP 0.3** PipeWire-Tab: Rate/Quantum-Steuerung, pw-top Node-Tabelle, DSP/Xruns/Latenz-Status
- **MVP 0.4** Session-Tab: Quick-Start (ptp4l + aes67), System-Status, Sync-Ampel, Xruns, DSP, Versionen, Routing-Tools

### Config Editor (`core/aes67_config.py`, `core/aes67_config_meta.py`, `ui/aes67_settings_dialog.py`)
- Format-erhaltender SPA-Parser (Zeilenbasiert, Kommentare/Formatierung bleiben erhalten)
- 40 Parameter in 4 Tabs (PTP Clock, RTP SAP Input, RTP Sink Output, Expert)
- RTP-Sink-Multi-Instanz (Add/Remove Sinks mit QTabWidget)
- System-Clock-Checkbox (kommentiert `clock.interface` aus → PHC-Timestamp-0-Problem als root)
- Deviation-Highlighting (goldener linker Rand bei Abweichung vom Default)
- Dunkles Theme (App-Level QPalette + gezielte Stylesheets)
- Stream.rules Raw-Editor (Expert-Tab, Round-Trip-sicher)

### PipeWire Tab (`ui/pipewire_tab.py`)
- Sample-Rate-Dropdown: 48000, 96000, 192000 (kein 44100 – nicht AES67-konform)
- Quantum-Dropdown: 16-8192 (Zweierpotenzen), editierbar
- Apply/Reset/Refresh Buttons für Rate und Quantum
- Setzen via `clock.force-rate` / `clock.force-quantum` (sofortige Wirkung auf Nodes)
- Lesen via `pw-metadata` + Fallback auf effektive Werte aus `pw-top`
- Timer-Updates (2s) respektieren gesetzte Metadata-Werte
- Latenz-Anzeige (berechnet aus Quantum × Rate, Tooltip mit Formel)
- Xruns-Counter (klickbar zum Zurücksetzen)
- DSP Load mit farbigem ProgressBar (grün/gelb/rot)
- Node-Tabelle mit Tree-Struktur: pw-top wird via `\s{2,}`-Split geparst, Parent-Child via `+` Prefix, 2. Iteration (effektive Running-States)
- Tabellen-Spalten: ID, Status (Running/Idle/Closed), Name, Quantum, Format, CH, DSP (Label+Mini-Bar), Waiting, Busy, Xruns, Rate
- Read-Only (kein Selection), Spaltenbreiten via QSettings gemerkt

### Session Tab (MVP 0.4)
- `ui/session_tab.py`: Quick-Start (ptp4l + aes67), System-Status, Sync-Ampel, Versionen
- Start-Reihenfolge: ptp4l → 2s warten → pipewire-aes67; Stop: aes67 → ptp4l
- Status: PTP (RUNNING/stopped + Offset in ns), AES67, PipeWire (Rate/Quantum)
- Sync-Ampel (grün ≤200ns, gelb ≤1000ns, rot) + Xruns-Counter + DSP-Bar
- Versionen-Block: PipeWire, LinuxPTP, Python, PyQt6 (rot/grün je nach installiert)
- Routing-Tools: qpwgraph, helvum, coppwr als Buttons (`shutil.which`-Prüfung)
- About-Button (`ℹ`) im Versionen-Block + als CornerWidget in Tab-Leiste
- `core/version.py`: Version, Name, Beschreibung, Lizenz, Author
- `ui/about_dialog.py`: About QDialog mit allen Versionen

### Wichtige Implementation-Details
- App läuft als root → `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS`, `HOME` via `SUDO_UID` setzen
- `_user_env()` für subprocess.run-Aufrufe von `pw-metadata` und `pw-top`
- Config-Parser (`AES67Config`): `_raw_lines[]` + `_data{}` + `_line_map[]` für format-erhaltendes set()
- Pfade als Tupel (`('args', 'local.ifname')`) wegen Punkt-Tasten
- `get_raw_block`/`set_raw_block` für Rohtext-Blöcke (stream.rules)
- User-Einstellungen via QSettings: PTP-Interface, Tabellen-Spaltenbreiten

### Bekannte Einschränkungen
- `context.spa-libs` wird geparst aber nicht im Editor angezeigt
- `node.channel-names` als MultilineWidget (nicht mit Sonderzeichen getestet)
- `stream.rules` nur als Raw-Editor, kein strukturierter Rule-Editor
- Xruns: lokaler Zähler, kein System-Reset möglich
- Keine Build/Test/Lint-Konfiguration vorhanden

## Beim Hinzufügen von Features
1. Modular Struktur (ui/services/core/widgets) einhalten
2. UI von Systemlogik trennen (services/ für Systembefehle)
3. Kleine, testbare Schritte
4. `docs/mvp.md` für geplante Feature-Reihenfolge beachten
5. Für Systembefehle QProcess mit Fehlerbehandlung verwenden
6. Benutzereinstellungen mit QSettings speichern
