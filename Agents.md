# Zusammenarbeit mit KI-Agenten

Dieses Projekt wird gemeinsam mit KI-Agenten iterativ entwickelt.

Der menschliche Projektleiter ist kein professioneller Softwareentwickler, besitzt aber tiefes technisches Verständnis im Bereich:

* Linux Audio
* PipeWire
* AES67
* Dante
* Netzwerk-Audio
* Echtzeit-Audio-Workflows

Die KI soll daher:

* technische Architekturentscheidungen aktiv unterstützen
* sinnvolle Projektstrukturen vorschlagen
* Best Practices erklären
* Code verständlich halten
* kleine iterative Schritte bevorzugen

---

# Wichtige Entwicklungsprinzipien

## Kleine Schritte

Keine riesigen Komplettlösungen erzeugen.

Stattdessen:

* kleine funktionierende Features
* klar testbar
* leicht verständlich

---

## Keine Überarchitektur

Keine unnötig komplexen Enterprise-Patterns.

Das Projekt soll:

* verständlich
* wartbar
* pragmatisch

bleiben.

---

## Modularität

Code logisch trennen:

* UI
* Services
* Systemlogik
* Widgets

Keine riesigen Dateien erzeugen.

---

## Verständlichkeit vor Cleverness

Code soll gut lesbar und nachvollziehbar sein.

Wichtiger als maximale Eleganz ist:

* einfache Wartbarkeit
* gute Debugbarkeit
* leichte Erweiterbarkeit

---

## UI und Funktionalität gemeinsam entwickeln

Die GUI soll organisch mit den echten Features wachsen.

Keine vollständig designte GUI ohne Funktionalität erzeugen.

---

## Bestehende Linux-Audio-Tools respektieren

sync67 ersetzt nicht:

* qpwgraph
* coppwr
* helvum

Das Projekt fokussiert sich auf:

* Synchronisation
* Monitoring
* Runtime Control
* AES67 Management

---

## Erst funktionierend, dann schön

Frühe Entwicklungsphasen priorisieren:

* Stabilität
* Funktion
* Architektur

nicht:

* perfektes UI-Design

---

## Technologien

* Python 3
* PySide6
* Qt6

Keine GNOME-spezifischen Technologien verwenden.

Desktop-unabhängige Architektur bevorzugen.

---

## Erwartete Zielplattformen

* Linux Mint
* Debian
* Ubuntu
* Arch Linux
* PipeWire-basierte Systeme

---

## Wichtiger Fokus

Das Projekt soll später auch in produktiven Live-Audio-Umgebungen nutzbar sein.

Deshalb sind wichtig:

* Stabilität
* Transparenz
* gutes Logging
* klare Statusanzeigen
* robuste Prozessverwaltung
