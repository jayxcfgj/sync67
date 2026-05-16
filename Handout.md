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
  * Netzwerkinterface auswählen (via `ip link show`) + Auswahl wird via QSettings gemerkt
  * ptp4l starten/stoppen
  * Live-Log anzeigen
  * Sync-Status anzeigen (visuelle Ampel-Anzeige)
  * Start Options-Dialog für ethtool/ip link Konfiguration (gro, gso, tso, sg, rx-usecs, multicast)
  * **PTP4L Config Editor**: GUI-Editor für `/etc/linuxptp/ptp4l.conf`
    * 119 Parameter in 7 Tabs (Quick, Main, Port, Runtime, Servo, Transport, Interface)
    * Quick-Tab mit 10 wichtigsten Parametern
    * Format-erhaltender Parser, Reset Config Button
    * Tooltips + Default-Anzeige + Deviation-Highlighting
  * Trennung von UI und Systemlogik (UI → Service Layer → Systemprozess)
- AES67 Tab vollständig funktional mit:
  * Start/Stop Buttons für `pipewire-aes67`
  * Terminal-Ausgabebereich
  * Config-Button zum Öffnen der Config-Datei im Editor
  * **AES67 Config Editor**: GUI-Editor für alle ~40 Parameter der `pipewire-aes67.conf`
    * 4 Tabs: PTP Clock, RTP SAP Input, RTP Sink Output, Expert
    * Format-erhaltender SPA-Parser (Kommentare/Formatierung bleiben erhalten)
    * RTP-Sink-Multi-Instanz (Add/Remove)
    * System-Clock-Checkbox (PHC-Problem-Umgehung als root)
    * Deviation-Highlighting bei Abweichung vom Default
    * Dunkles Theme (Dark Mode)
    * stream.rules Raw-Editor im Expert-Tab
  * Wichtig: App läuft scheinbar als root (os.getuid() == 0). Daher müssen
    `XDG_RUNTIME_DIR`, `DBUS_SESSION_BUS_ADDRESS` und `HOME` explizit auf
    den User-Wert gesetzt werden (via `SUDO_UID` aus der Umgebung).
    Sonst findet pipewire-aes67 weder Config noch PipeWire-Socket.
  * PHC-Problem (Timestamp 0 als root): gelöst via "System-Clock verwenden"
    Checkbox im Config-Editor. Kein `/dev/shm`-Override mehr nötig.
- PipeWire Tab (MVP 0.3) vollständig funktional mit:
  * Sample Rate und Quantum steuern/lesen via `pw-metadata`
  * Apply setzt via `clock.force-rate` / `clock.force-quantum` → sofortige Wirkung auf Nodes
  * Refresh zeigt Metadata-Wert, Reset zeigt effektiven Wert aus pw-top
  * Timer-Updates (2s) respektieren gesetzte Metadata-Werte, sonst effektive Werte aus pw-top
  * Latenz-Anzeige (berechnet aus Quantum/Rate, Tooltip mit Formel)
  * Xruns-Counter (klickbar zum Zurücksetzen)
  * DSP Load mit farbigem ProgressBar (grün <50%, gelb <80%, rot >=80%)
  * Node-Tabelle mit Tree-Struktur (Parent-Child via └─), aktualisiert via `pw-top` alle 2s
  * Spalten: ID, Status, Name, Quantum, Format, CH, DSP (Label + Mini-Bar), Waiting, Busy, Xruns, Rate
  * Read-Only (kein Selection-Modus), Spaltenbreiten via QSettings gemerkt
  * PTP-Interface-Auswahl via QSettings gemerkt

---

# MVP-Status

## ✅ PTP Tab (MVP 0.1 – abgeschlossen)

* Netzwerkinterface auswählen (Auswahl gespeichert)
* ptp4l starten/stoppen
* Live-Log anzeigen
* Sync-Status anzeigen (Ampel)
* Start Options für ethtool-Optimierung
* **PTP4L Config Editor** (119 Parameter, 7 Tabs, Quick-Tab)

## ✅ AES67 Tab (MVP 0.2 – abgeschlossen)

* PipeWire AES67 starten/stoppen
* Live-Log anzeigen
* Config-Datei öffnen
* AES67 Config Editor (40 Parameter, 4 Tabs, Stream-Rules-Editor)

## ✅ Session Tab (MVP 0.4 – abgeschlossen)

* Quick-Start: ptp4l + pipewire-aes67 in Reihe starten/stoppen
* System-Status: PTP (mit Sync-Ampel), AES67, PipeWire auf einen Blick
* PTP Sync-Ampel: grün ≤200ns, gelb ≤1000ns, rot
* Xruns-Counter + DSP Load (Übernahme aus PipeWire-Tab)
* Versionen: PipeWire, LinuxPTP, Python, PyQt6 (installiert/fehlt Markierung)
* Routing-Tools Buttons: qpwgraph, helvum, coppwr
* About-Dialog mit Versionsinfo und Lizenz

## ✅ PipeWire Tab (MVP 0.3 – abgeschlossen)

* Sample Rate steuern (Dropdown: 48000, 96000, 192000 – Apply/Reset/Refresh)
* Quantum steuern (Dropdown 16-8192, editierbar – Apply/Reset/Refresh)
* Setzen via `clock.force-rate` / `clock.force-quantum` → sofortige Wirkung
* Latenz-Anzeige (berechnet aus Quantum × Rate, Tooltip mit Formel)
* Xruns-Counter (klickbar zum Zurücksetzen)
* DSP Load mit farbigem ProgressBar (grün/gelb/rot)
* Node-Tabelle mit Tree-Struktur (Parent-Child via └─)
  * Spalten: ID, Running, Name, Quantum, Format, CH, DSP (Label+Bar), Waiting, Busy, Xruns, Rate
  * Read-Only, Spaltenbreiten via QSettings gemerkt
  * Aktualisiert alle 2s via pw-top (2. Iteration für Running-States)

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
