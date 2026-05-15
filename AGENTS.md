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
- PTP-Tab (MVP 0.1) vollständig implementiert mit:
  * Netzwerkinterface-Dropdown (befüllt via `ip link show`)
  * Settings-Dialog für ethtool/ip link Konfiguration (gro, gso, tso, sg, rx-usecs, multicast)
  * START PTP Button → führt Konfigurationsbefehle aus, startet dann `ptp4l -i $IFACE -m -l 6 -H`
  * STOP PTP Button → beendet ptp4l-Prozess
  * Terminal-Ausgabebereich (schwarz/grün) für Befehlsausgaben und ptp4l-Logs
  * Visuelle Ampel-Anzeige für PTP-Synchronisationsstabilität (grün/gelb/rot)
  * Separate QProcess-Objekte für Konfigurationsbefehle und ptp4l
  * sudo-Credential-Check via `sudo -n true` (User muss vorher `sudo -v` im Terminal ausführen)
- AES67-Tab (MVP 0.2) implementiert mit:
  * Start/Stop Buttons für `pipewire-aes67`
  * Terminal-Ausgabebereich für Logs und Fehlermeldungen
  * Config-Button zum Öffnen von `~/.config/pipewire/pipewire-aes67.conf`
  * Kein sudo erforderlich
  * Wichtig: App läuft scheinbar als root (os.getuid() == 0). Daher müssen
    `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS` und `HOME` explizit auf
    den User-Wert gesetzt werden (via `SUDO_UID` aus der Umgebung).
    Sonst findet pipewire-aes67 weder Config noch PipeWire-Socket.
  * Da die App als root läuft, wird die PTP-Hardware-Clock (PHC) nicht
    korrekt erkannt. Daher wird in einer temporären Config-Datei
    (`/dev/shm/pipewire-aes67-override.conf`) `clock.interface` auskommentiert,
    sodass die System-Clock statt des PHC verwendet wird.
- Keine Build/Test/Lint-Konfiguration vorhanden

## Beim Hinzufügen von Features
1. Modular Struktur (ui/services/core/widgets) einhalten
2. UI von Systemlogik trennen (services/ für Systembefehle)
3. Kleine, testbare Schritte
4. `docs/mvp.md` für geplante Feature-Reihenfolge beachten
5. Für Systembefehle QProcess mit Fehlerbehandlung verwenden
6. Benutzereinstellungen mit QSettings speichern
