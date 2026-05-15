# Implementierungsplan: AES67 Config Editor

## 1. Motivation

PipeWire-AES67 benutzt eine SPA-Config-Datei (`pipewire-aes67.conf`) mit komplexer Struktur:
`context.properties`, `context.objects`, `context.modules` (rtp-sap, rtp-sink, etc.).
Bislang muss der User Parameter händisch im Editor ändern. Ziel ist ein GUI-Editor der alle relevanten
Parameter zugänglich macht, Default-Werte zeigt, Tooltips bietet und das Hinzufügen/Löschen mehrerer
rtp-sink-Instanzen erlaubt.

## 2. Annahmen (Assumptions)

- Python 3.12, PyQt6, PipeWire 1.5.84
- Die App läuft als root (`os.getuid() == 0`), der tatsächliche User ist via `SUDO_UID`/`SUDO_USER` ermittelbar
- Die Default-Config liegt unter `/usr/share/pipewire/pipewire-aes67.conf`
- Die User-Config liegt unter `~/.config/pipewire/pipewire-aes67.conf`
- Das Config-Format ist SPA-eigen: `key = value` mit `{ }` Blöcken, `[ ]` Arrays und `#` Kommentaren
- Es können mehrere rtp-sink Instanzen existieren (Array-Elemente in `context.modules`)
- `context.spa-libs` wird nie verändert und bleibt immer identisch zur Default-Config
- Die Kommunikationssprache zwischen Agent und User ist Deutsch

## 3. Entscheidungen (Design Decisions)

| Entscheidung | Gewählt | Verworfen | Begründung |
|---|---|---|---|
| Config-Parser | Zeilenbasierter Parser mit Format-Erhalt | JSON/YAML-Konvertierung | User-Config muss menschenlesbar bleiben. Formatierung und Kommentare erhalten |
| Datenmodell | Dict + Liste, gemappt auf Sektionen/Module/Args | DOM-Baum | Einfacher, ausreichend für die Tiefe der Config |
| Parameter-Metadaten | Zentrale `CONFIG_META` Dict | Annotation-basiert | Übersichtlicher, alle Defaults/Tooltips an einem Ort |
| GUI-Aufbau | TabWidget pro Sektion | Ein großer Scroll-Bereich | Bessere Struktur, logisch getrennte Bereiche |
| rtp-sink Multi-Instanz | QTabWidget im RTP-Sink-Tab | Liste mit Scrollbereich | Tab-Metapher passt am besten zu "mehrere Instanzen" |
| stream.rules Editor | Zusammenklappbare Regel-Gruppen | Roh-Text oder externer Editor | Volle GUI-Kontrolle, kein manuelles JSON |
| Speichern | Direkt in User-Config (mit Backup) | In temporäre Datei | Intuitiver für User, ein Schritt weniger |
| PHC/System-Clock | Checkbox "System-Clock verwenden" im PTP-Clock-Tab | Separate Override-Logik | Alles im Editor vereint, kein interner Trick mehr |

## 4. Prioritäten (Critical vs. Optional)

### Critical (MVP – muss im ersten Durchlauf funktionieren)

- Config-Parser: Lesen + Schreiben der Config (Format erhalten)
- Alle ~30 Parameter inkl. Defaults und Tooltips definieren
- GUI: 4 Tabs mit allen Widgets (Dropdowns, SpinBoxes, CheckBoxes, TextFields)
- Default-Wert-Anzeige + Abweichungs-Markierung
- Apply/Cancel Logik (mit Änderungs-Prüfung)
- Config-Prüfung in `start_aes67()` (Default kopieren wenn fehlt)
- Button "AES67 Config Editor" im AES67-Tab

### Important – sollte im ersten Durchlauf dabei sein

- `stream.rules` Editor (Regeln hinzufügen/entfernen/bearbeiten)
- `stream.props` als separate Felder im RTP-Sink-Tab
- Reset Config Button mit Sicherheitsabfrage
- Tooltip-Symbol für jeden Parameter

### Optional – kann später folgen

- rtp-sink Multi-Instanz (mehrere Tabs, Add/Remove)
- Unterdrückung der `/dev/shm`-Override-Logik (ersetzt durch "System-Clock verwenden" Checkbox)

## 5. Edge Cases

| Edge Case | Behandlung |
|---|---|
| User-Config existiert nicht beim Start | Default wird automatisch kopiert beim ersten Klick auf START |
| User-Config ist leer oder korrupt | Parser wirft Exception → GUI zeigt Fehlerdialog → User kann auf Reset klicken |
| Default-Config existiert nicht (`/usr/share/...`) | Fehlermeldung + Vorschlag die Config manuell zu besorgen |
| rtp-sink Instanz wurde gelöscht, ist aber die letzte | Löschen nicht erlaubt, letzte Instanz bleibt erhalten |
| Parameter-Wert ungültig (z.B. IP ausserhalb Range) | Validierung beim Apply, rote Markierung am Widget |
| Config während der Bearbeitung extern geändert | Apply prüft Änderungsdatum, warnt wenn extern modifiziert |
| stream.rules enthält unbekannte Felder | Werden als "Raw" Text erhalten, nicht überschrieben |
| Module werden anhand ihres Namens identifiziert | Parser erkennt Module an `{ name = libpipewire-... }`, nicht an Position |
| Sonderzeichen in Strings (Anführungszeichen, Backslashes) | Korrekt escapen beim Serialisieren |

## 6. Schnittstellen (Interfaces & Datenstrukturen)

### `core/aes67_config.py`

```python
class AES67Config:
    """Repräsentiert die gesamte pipewire-aes67.conf."""

    def __init__(self):
        self.sections: dict = {}       # Geparste Struktur
        self.raw_order: list = []      # Reihenfolge der Sektionen (für Format-Erhalt)
        self.comment_map: dict = {}    # Zeilen-Kommentare zuordnen
        self.default_path: str = "/usr/share/pipewire/pipewire-aes67.conf"
        self.user_path: str = "~/.config/pipewire/pipewire-aes67.conf"

    def load(self, path: str) -> None:
        """Liest Config, parst in sections-Struktur.
        Raises FileNotFoundError, ParseError."""

    def save(self, path: str) -> None:
        """Schreibt sections-Struktur zurück ins SPA-Format.
        Erhält Kommentare, Leerzeilen, Formatierung soweit möglich.
        Raises IOError."""

    def get(self, *keys: str) -> Any:
        """Holt Wert aus der verschachtelten Struktur.
        Keys sind Pfad-Schritte, z.B. get('modules','rtp-sap','args','local.ifname')
        Returns None wenn nicht gefunden."""

    def set(self, value: Any, *keys: str) -> bool:
        """Setzt Wert in der Struktur. Erzeugt fehlende Dict-Ebenen.
        Returns True bei Änderung, False wenn Wert identisch."""

    def get_default(self, *keys: str) -> Any:
        """Gibt Default-Wert aus der Default-Config zurück."""

    def reset_to_default(self) -> None:
        """Überschreibt User-Config mit Default-Config (shutil.copy)."""

    def get_module_index(self, name: str) -> int:
        """Gibt Index eines Moduls in der modules-Liste zurück.
        Name z.B. 'libpipewire-module-rtp-sap'.
        Returns -1 wenn nicht gefunden."""

    def add_rtp_sink(self, template_index: int = -1) -> int:
        """Fügt neuen rtp-sink Block hinzu (kopiert von Vorlage).
        Returns Index des neuen Blocks."""

    def remove_rtp_sink(self, index: int) -> bool:
        """Entfernt rtp-sink Block.
        Gibt False zurück wenn es der letzte ist (Löschen nicht erlaubt)."""
```

### `core/aes67_config_meta.py`

```python
from typing import Literal

ParamType = Literal['string', 'int', 'float', 'bool', 'interface', 'ip', 'port', 'choice', 'multiline']

ParamMeta = {
    'type': ParamType,
    'default': Any,
    'label': str,
    'tooltip': str,
    'section': str,
    'advanced': bool,
    'module': str,           # Name des Moduls
    'path_in_args': str,     # Pfad innerhalb der args, z.B. "audio.rate"
    'choices': list = None,  # Für 'choice' Typ
    'min': Any = None,       # Für Zahl-Typen
    'max': Any = None,
    'step': float = None,
}

CONFIG_PARAMS: list[ParamMeta] = [...]

PARAM_MAP: dict[str, ParamMeta] = {f"{p['module']}.{p['path_in_args']}": p for p in CONFIG_PARAMS}
```

### `ui/aes67_settings_dialog.py`

```python
class AES67SettingsDialog(QDialog):
    def __init__(self, config: AES67Config, parent=None):
        """Öffnet den Editor mit der geladenen Config."""

    def get_modified_params(self) -> list[tuple[str, Any]]:
        """Gibt Liste der geänderten Parameter (key, neue_value).
        Für Apply-Logik."""
```

### `ui/aes67_tab.py` – Integration

```python
class AES67Tab(QWidget):
    ...
    def open_config_editor(self):
        dialog = AES67SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.Accepted:
            self.config.save(self.config.user_path)
            self.terminal_output.append("Config gespeichert.")
```

## 7. Schritt-für-Schritt Implementierung

### Schritt 1: `core/aes67_config.py`

1.1. Lege Datei `core/__init__.py` an (falls nicht existiert)
1.2. Implementiere Klasse `AES67Config`:
   - `load()`: Lese Datei zeilenweise, rufe internen Parser `_parse()`
   - `_parse()`: Erkenne Sektionen (`context.properties`, `context.modules`, etc.)
   - Für `context.modules`: Erkenne `{ name = libpipewire-... }` Blöcke, parse `args = { }`
   - Für `context.objects`: Erkenne `{ factory = ... }` Blöcke
   - Erhalte Kommentare und Leerzeilen in `raw_order` und `comment_map`
   - `save()`: Schreibe aus raw_order + sections zurück, mit Format-Erhalt
   - `get()`: Navigiere in der sections Dict mit Punkt-Notation
   - `set()`: Setze Wert, markiere in `_modified`
   - `add_rtp_sink()`: Finde letztes rtp-sink Modul, kopiere args Block
   - `remove_rtp_sink()`: Lösche Eintrag aus modules-Liste
1.3. Exception-Klassen: `ConfigNotFoundError`, `ConfigParseError`, `ConfigWriteError`
1.4. Test: `python3 -c "from core.aes67_config import AES67Config; c = AES67Config(); c.load('/usr/share/pipewire/pipewire-aes67.conf'); print(c.get('modules','rtp-sap','args','local.ifname'))"`

**SPA-Format-Besonderheiten die der Parser beherrschen muss:**
- `key = wert` (einfach)
- `key = "wert mit leerzeichen"` (quoted)
- `key = [ "a", "b" ]` (Array)
- `key = { sub = value }` (Inline-Objekt)
- `# Kommentar` und `## Kommentar` (beide erhalten)
- `... (truncated)` in Beispielen ignorieren (kommt nur in Doku vor)
- Leerzeichen am Zeilenanfang signifikant für Einrückung
- `flags = [ ifexists nofail ]` (Array ohne Anführungszeichen)

### Schritt 2: `core/aes67_config_meta.py`

2.1. Definiere `CONFIG_PARAMS` Liste mit allen ~30 Parametern.
2.2. Definiere `PARAM_MAP` Dict für schnellen Zugriff.
2.3. Jeder Parameter bekommt: `type`, `default`, `label`, `tooltip`, `section`, `advanced`, `module`, `path_in_args`.
2.4. Interface-Parameter bekommen zusätzlich Referenz auf das zugehörige ifname-Feld.
2.5. Die Tooltips müssen auf Deutsch sein, verständlich für Audio-Anwender ohne tiefes PipeWire-Wissen.

**Parameter-Liste:**

| Modul | Parameter | Typ | Default |
|---|---|---|---|
| PTP0-Driver | `clock.interface` | interface | `eth0` |
| PTP0-Driver | `clock.name` | string | `"clock.system.ptp0"` |
| PTP0-Driver | `clock.device` | string | `"/dev/ptp0"` |
| PTP0-Driver | `clock.id` | choice | `""` (leer) |
| PTP0-Driver | `resync.ms` | float | `1.5` |
| PTP0-Driver | `priority.driver` | int | `100000` |
| PTP0-Driver | `object.export` | bool | `true` |
| mod-rt | `nice.level` | int | `-11` |
| mod-rt | `rlimits.enabled` | bool | (fehlt im Default) |
| mod-rt | `rtkit.enabled` | bool | (fehlt im Default) |
| mod-rt | `rt.prio` | int | `83` |
| rtp-sap | `local.ifname` | interface | `eth0` |
| rtp-sap | `sap.ip` | ip | `239.255.255.255` |
| rtp-sap | `sap.port` | port | `9875` |
| rtp-sap | `net.ttl` | int | `32` |
| rtp-sap | `net.loop` | bool | `false` |
| rtp-sap | `ptp.management-socket` | string | `"/var/run/ptp4lro"` |
| rtp-sap | `sess.latency.msec` | int | `3` |
| rtp-sink | `local.ifname` | interface | `eth0` |
| rtp-sink | `destination.ip` | ip | `239.69.150.243` |
| rtp-sink | `destination.port` | port | `5004` |
| rtp-sink | `net.mtu` | int | `1280` |
| rtp-sink | `net.ttl` | int | `32` |
| rtp-sink | `net.loop` | bool | `false` |
| rtp-sink | `sess.min-ptime` | int | `1` |
| rtp-sink | `sess.max-ptime` | int | `1` |
| rtp-sink | `sess.name` | string | `"PipeWire RTP stream"` |
| rtp-sink | `sess.media` | string | `"audio"` |
| rtp-sink | `sess.ts-refclk` | string | `"ptp=traceable"` |
| rtp-sink | `sess.ts-offset` | int | `0` |
| rtp-sink | `sess.ts-direct` | bool | `false` |
| rtp-sink | `sess.latency.msec` | int | `3` |
| rtp-sink | `audio.format` | choice | `"S24BE"` |
| rtp-sink | `audio.rate` | choice | `48000` |
| rtp-sink | `audio.channels` | int | `2` |
| rtp-sink | `node.channel-names` | multiline | `["CH1", "CH2"]` |
| rtp-sink (props) | `node.name` | string | `"rtp-sink"` |
| rtp-sink (props) | `node.always-process` | bool | `true` |
| rtp-sink (props) | `rtp.ntp` | int | `0` |
| rtp-sink (props) | `rtp.fetch-ts-refclk` | bool | `true` |

### Schritt 3: `ui/aes67_settings_dialog.py`

3.1. Lege Datei an.
3.2. Basis: `class AES67SettingsDialog(QDialog)` mit QVBoxLayout.
3.3. Erzeuge QTabWidget mit 4 Tabs.
3.4. Pro Tab: **Dynamisch die Widgets aus CONFIG_PARAMS erzeugen**:
   - Lese `CONFIG_PARAMS` für die Sektion
   - Für jeden Parameter: erzeuge Label + Widget + Default-Anzeige + Tooltip
   - Abhängig von `type`:
     - `interface`: QComboBox, befüllt via `ip link show` (Loopback herausfiltern)
     - `string`: QLineEdit
     - `int`: QSpinBox
     - `float`: QDoubleSpinBox
     - `bool`: QCheckBox
     - `ip`: QLineEdit mit QRegularExpressionValidator
     - `port`: QSpinBox 1-65535
     - `choice`: QComboBox mit vordefinierten choices
     - `multiline`: QTextEdit (max 3 Zeilen Höhe)
3.5. "System-Clock verwenden" Checkbox: Zusätzlicher Eintrag im PTP-Clock-Tab.
   Wenn aktiviert: setze `#clock.interface` (auskommentiert) in der gespeicherten Config.
   Wenn deaktiviert: setze `clock.interface` mit dem ausgewählten Interface-Wert.
3.6. **Default-Anzeige**: Graues Label unter dem Widget: `Default: eth0`
3.7. **Abweichungs-Markierung**: Hintergrundfarbe des Widgets auf `#E3F2FD` (hellblau) setzen wenn aktueller Wert != Default.
3.8. **Tooltip**: `widget.setToolTip(param['tooltip'])` + Label setToolTip.
3.9. **stream.rules Editor** (rtp-sap Tab):
   - Lade `get('modules','rtp-sap','args','stream.rules')` als Array
   - Für jede Regel: GroupBox mit `matches` und `actions` Feldern
   - "Add Rule" Button: fügt neue leere Regel hinzu
   - "Remove Rule" Button mit Bestätigung
3.10. **stream.props Editor** (rtp-sink Tab):
   - Lade `get('modules','rtp-sink','args','stream.props')` als Dict
   - Zeige jedes Key-Value-Paar als separates Widget
3.11. **RTP Sink Multi-Instanz**:
   - QTabWidget im RTP-Sink-Tab
   - Standard: ein Tab "Sink 1"
   - "+ Add Sink": kopiert aktuelles rtp-sink args, erzeugt neuen Tab
   - "✕ Remove": löscht Tab (und später den Modul-Eintrag). Letzte Instanz kann nicht gelöscht werden.
   - Beim Apply: alle Tabs in modules-Liste serialisieren
3.12. **Buttons unten**: Apply, Cancel, Reset Config.
3.13. **Cancel mit Änderungs-Prüfung**: Flag `_has_changes` setzen bei jeder Widget-Änderung.
   Bei Cancel wenn `_has_changes`: QMessageBox "Änderungen verwerfen?"
3.14. **Apply Logik:**
   - Sammle alle Werte aus den Widgets
   - Rufe `config.set(wert, *keys)` für jeden geänderten Parameter
   - Rufe `config.save(self.config.user_path)`
   - Bei Erfolg: QMessageBox "Config gespeichert" und accept()
   - Bei Fehler: QMessageBox mit Fehlertext, Dialog bleibt offen
3.15. **Reset Config Logik:**
   - QMessageBox.warning("Config zurücksetzen", "Bist du sicher?")
   - Bei Yes: `config.reset_to_default()` + `config.load(config.user_path)` + Widgets neu laden
   - Meldung: "Config zurückgesetzt auf Default"

**Multi-Instanz:** Ein eigenes `RtpSinkTabWidget(QWidget)` wird erstellt, das einen Satz Widgets für eine rtp-sink Instanz kapselt.

### Schritt 4: Integration in `ui/aes67_tab.py`

4.1. **Config-Prüfung** in `start_aes67()` – ganz am Anfang, vor allem anderen:
```python
config_path = os.path.join(user_home, ".config/pipewire/pipewire-aes67.conf")
if not os.path.exists(config_path):
    self.terminal_output.append("Keine User-Config gefunden. Kopiere Default...")
    shutil.copy(default_config_path, config_path)
    self.terminal_output.append(f"Default Config nach {config_path} kopiert.")
```
4.2. **Config laden** in `__init__` oder beim ersten Öffnen des Editors:
```python
self.config = AES67Config()
self.config.load(self.config.user_path)
```
4.3. **Neuer Button** in `config_group`:
```python
self.config_editor_btn = QPushButton("AES67 Config Editor")
self.config_editor_btn.clicked.connect(self.open_config_editor)
```
4.4. **open_config_editor()** Methode:
```python
def open_config_editor(self):
    from ui.aes67_settings_dialog import AES67SettingsDialog
    dialog = AES67SettingsDialog(self.config, self)
    if dialog.exec() == QDialog.Accepted:
        self.terminal_output.append("Config gespeichert.")
        self.config.load(self.config.user_path)
```
4.5. **temp-override Logik anpassen:**
   Die `/dev/shm/pipewire-aes67-override.conf` wird NUR NOCH erzeugt wenn im Editor NICHT
   "System-Clock verwenden" aktiviert ist. Langfristig kann die gesamte Override-Logik entfallen.

### Schritt 5: Nachbereitung

5.1. `AGENTS.md` aktualisieren: Neuen Config-Editor erwähnen.
5.2. `Handout.md` aktualisieren: Config-Editor im MVP-Status ergänzen.
5.3. Syntax-Check: `python3 -m py_compile core/aes67_config.py core/aes67_config_meta.py ui/aes67_settings_dialog.py ui/aes67_tab.py`
5.4. Testen: App starten, Config-Editor öffnen, Parameter ändern, Apply, Config-Datei prüfen.

## 8. Fragen die ein Implementierungs-Agent stellen könnte (beantwortet)

**F: Wie tief muss der Parser gehen?**  
A: Nur 2-3 Ebenen tief. `context.modules` → Module → `args` → Parameter. Für `stream.rules` und `stream.props` reicht ein Sub-Parser der Inline-Objekte erkennt.

**F: Was passiert mit `... (truncated)` in den Original-Configs?**  
A: Ignorieren. Das ist ein Artefakt der Doku. In den tatsächlichen Config-Dateien kommt das nicht vor.

**F: Wie werden Array-Werte gespeichert?**  
A: Als Python-Liste. Beim Serialisieren: `[ "CH1", "CH2" ]`.

**F: Was wenn ein User einen Wert auf den Default zurücksetzen will?**  
A: Der "Reset Config" Button setzt die gesamte Config zurück. Für einzelne Parameter: Der User kann den Wert manuell auf den Default ändern (die Default-Anzeige zeigt den Zielwert).

**F: Wie wird `stream.rules` im GUI dargestellt?**  
A: Jede Regel ist eine zusammenklappbare GroupBox mit den Feldern aus der Config.

**F: Wie wird der `clock.interface`-Override im Editor abgebildet?**  
A: Der PTP-Clock-Tab hat eine QCheckBox "System-Clock verwenden (PHC deaktivieren)".
Wenn aktiviert: `clock.interface` wird in der Config auskommentiert.
Wenn deaktiviert: `clock.interface` wird mit dem ausgewählten Interface aktiv gesetzt.

**F: Soll `context.spa-libs` editierbar sein?**  
A: Nein. Wird beim Serialisieren unverändert aus der Original-Config übernommen.

**F: Wie werden mehrere rtp-sink Instanzen serialisiert?**  
A: Jeder Eintrag unter `context.modules` mit `name = libpipewire-module-rtp-sink` wird als eine Instanz behandelt.

## 9. Häufige Fehler und wie man sie vermeidet

| Fehler | Vermeidung |
|---|---|
| Config-Formatierung geht verloren | Parser muss Zeilenstruktur + Kommentare erhalten. `raw_order` Liste führt Buch über die Original-Reihenfolge. |
| TypeError beim Serialisieren von Arrays | Arrays immer als `[ elem1, elem2 ]` formatieren. Strings mit `"`, Zahlen ohne. |
| rtp-sink Instanzen werden beim Laden übersehen | Parser muss Module ANHAND IHRES NAMENS erkennen, nicht an Position. |
| Neue rtp-sink Instanz hat keinen eigenen `stream.props` | `add_rtp_sink()` muss die gesamte args-Struktur kopieren. |
| Beim Apply werden unveränderte Parameter überschrieben | Nur Parameter speichern die sich geändert haben (`_modified` Flag). |
| Interface-Dropdown zeigt `lo` (loopback) | Wie in ptp_tab.py: `[iface for iface in interfaces if iface != 'lo']` |
| Tooltip-Text wird abgeschnitten | Tooltip via `setToolTip()` (Qt zeigt mehrzeilige Tooltips). Zeilenumbrüche mit `\n`. |
| Dialog schliesst trotz Fehler beim Speichern | `save()` in try/except. Bei Exception: Fehlerdialog, Dialog bleibt offen. |

## 10. Definition of Done (Testbare Akzeptanzkriterien)

- [ ] **Parser**: Config laden → `get('modules','rtp-sap','args','local.ifname')` liefert korrekten Wert
- [ ] **Parser (User-Config)**: User-Config laden → abweichende Werte werden erkannt
- [ ] **Serializer**: Config lesen, unverändert speichern, diff zeigt keine Unterschiede
- [ ] **Serializer (geändert)**: Wert ändern, speichern, neu laden → geänderter Wert, Rest unverändert
- [ ] **GUI öffnet sich**: Button "AES67 Config Editor" → QDialog mit 4 Tabs
- [ ] **Parameter sichtbar**: Alle ~30 Parameter typ-gerechte Widgets
- [ ] **Default-Anzeige**: Grauer Text `Default: <wert>` unter jedem Widget
- [ ] **Abweichungs-Markierung**: Parameter ≠ Default haben blauen Hintergrund
- [ ] **Tooltip**: Hover über Label zeigt Erklärung
- [ ] **Apply**: Wert ändern, Apply → Config-Datei enthält neuen Wert
- [ ] **Cancel**: Wert ändern, Cancel → Config-Datei unverändert
- [ ] **Reset Config**: Button → Bestätigung → Config = Default → Widgets aktualisiert
- [ ] **System-Clock Checkbox**: Aktivieren → `clock.interface` in Config auskommentiert
- [ ] **Config-Prüfung**: User-Config löschen → START klicken → Default wird kopiert
- [ ] **stream.rules Editor**: Regeln sichtbar, editierbar, speicherbar
- [ ] **rtp-sink Multi-Instanz**: "+ Add Sink" → neuer Tab → Apply → Config hat zwei rtp-sink Blöcke
- [ ] **Syntax-Clean**: `python3 -m py_compile core/...` → keine Fehler
- [ ] **App startet**: `python3 main.py` → GUI erscheint, AES67-Tab funktioniert
