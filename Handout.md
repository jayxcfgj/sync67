# sync67

## Projektbeschreibung

sync67 ist ein Linux Desktop Tool zur Verwaltung, Überwachung und Konfiguration von AES67 Audio-Streaming mit PipeWire.

Der Fokus liegt NICHT auf Audio-Patching oder Routing.
Routing soll weiterhin über bestehende Tools wie qpwgraph oder coppwr erfolgen.

sync67 soll stattdessen folgende Bereiche zentral verwalten:

* PTP Clock Synchronisation (ptp4l)
* AES67 Runtime Management
* PipeWire AES67 Konfiguration
* Monitoring von Clock, Streams und PipeWire Status
* Session- und System-Orchestrierung

---

# Zielsetzung

Das Ziel ist eine zentrale grafische Oberfläche für Linux-basierte AES67-Setups im Live- und Studioeinsatz.

Die Software soll insbesondere folgende Workflows vereinfachen:

* PipeWire AES67 starten und überwachen
* ptp4l starten und Sync-Status anzeigen
* AES67 Stream-Konfiguration verwalten
* PipeWire Quantum/XRun Monitoring
* Integration bestehender Patchbay-Tools

Das Projekt richtet sich an professionelle und semiprofessionelle Linux-Audio-Anwendungen.

---

# Technologiestack

## GUI Framework

Qt6

## Python Binding

PyQt6

## Programmiersprache

Python 3

---

# Architekturprinzipien

## WICHTIG:

UI und Logik strikt trennen.

Die GUI darf keine direkte Systemlogik enthalten.

Beispiel:

NICHT:

* Button startet direkt einen Shell-Befehl

SONDERN:

* UI → Service Layer → Systemprozess

---

# Geplante Architektur

## ui/

Qt Fenster, Tabs und Widgets

## services/

Systemdienste und Prozessverwaltung

Beispiele:

* ptp_service.py
* pipewire_service.py
* aes67_service.py

## core/

Gemeinsame Hilfsfunktionen und Infrastruktur

## widgets/

Wiederverwendbare GUI-Komponenten

---

# Entwicklungsphilosophie

Das Projekt wird iterativ entwickelt.

Es sollen zuerst kleine vollständig funktionierende Features entstehen.

NICHT:

* komplette GUI zuerst bauen

SONDERN:

* kleine vertikale Features entwickeln

Beispiel:

* PTP Tab vollständig funktional
* danach nächstes Modul

---

# Wichtige technische Ziele

* Distribution-unabhängig
* Desktop-unabhängig
* Keine GNOME-Abhängigkeit
* Funktioniert unter KDE, XFCE, Cinnamon etc.
* PipeWire-native Architektur
* Gute Integration in Linux Audio Workflows

---

# Aktueller Implementierungsstand

- PTP Tab vollständig funktional mit:
  * Netzwerkinterface auswählen (via `ip link show`)
  * ptp4l starten/stoppen
  * Live-Log anzeigen
  * Sync-Status anzeigen (visuelle Ampel-Anzeige)
  * Settings-Dialog für ethtool/ip link Konfiguration (gro, gso, tso, sg, rx-usecs, multicast)
  * Trennung von UI und Systemlogik (UI → Service Layer → Systemprozess)
- AES67 Tab vollständig funktional mit:
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

---

# MVP-Status

## ✅ PTP Tab (MVP 0.1 – abgeschlossen)

* Netzwerkinterface auswählen
* ptp4l starten/stoppen
* Live-Log anzeigen
* Sync-Status anzeigen (Ampel)

## ✅ AES67 Tab (MVP 0.2 – abgeschlossen)

* PipeWire AES67 starten/stoppen
* Live-Log anzeigen
* Config-Datei öffnen

## System Tab (MVP 0.3 – offen)

* pw-top Informationen anzeigen
* Quantum anzeigen
* XRuns anzeigen

---

# Externe Tools

sync67 ersetzt KEINE Patchbay.

Für Routing/Patching sollen externe Tools genutzt werden:

* qpwgraph
* coppwr
* helvum

sync67 kann später Buttons oder Integrationen für diese Tools bereitstellen.

---

# Namenskonzept

Der Name "sync67" steht für:

* AES67
* Synchronisation
* PTP Clocking
* Realtime Audio Networking
