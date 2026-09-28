# sync67 – Fehler-Liste und Lösungen

Diese Dokumentation listet alle häufigen Fehler und Warnungen auf, die bei der Nutzung von `pipewire-aes67` auftreten können. Jeder Eintrag enthält die Ursache und die empfohlene Lösung.

---

## 1. "missing timeout 2-10" in den Logs

**Bedeutung**: Der RTP-Streaming-Buffer ist fast leer, das System kann das nächste Paket nicht rechtzeitig liefern.

**Ursachen**:
- USB-Jitter des NIC (2-10ms Verzögerung bei Paketübertragung)
- Zu kleines `sess.latency.msec` (sollte mindestens 10 betragen)
- Zu hohes `sess.max-ptime` (mehr als 4ms verursacht Scheduling-Probleme)
- `systemd-timesyncd` läuft parallel (wird standardmäßig vor jedem ptp4l-start deaktiviert, siehe "Start Optionen")

**Lösung**:
```bash
# In der pipewire-aes67.conf:
sess.latency.msec = 12     # Muss Vielfaches von max-ptime sein (12/4=3)
sess.max-ptime = 4         # 4ms-Pakete statt 1ms
resync.ms = 48             # nicht 1.5!

```

---

## 2. "expected X != actual Y" (Timestamp-Sprünge)

**Bedeutung**: Die tatsächliche_timestamp weicht von der erwarteten ab. Der Unterschied beträgt meist 256 Samples (entspricht 5,33ms bei 48kHz, also genau ein RTP-Paket bei 1ms ptime).

**Ursache**:
- Bei 1ms ptime: Der PipeWire-Scheduler kann den 1ms-Takt nicht halten → Paketverlust
- Bei 4ms ptime: Tritt seltener auf (ca. alle 1-2 Minuten), meist unerhehrlich

**Lösung**:
- `sess.max-ptime = 4` setzen (empfohlen) → das Problem tritt selten auf
- `sess.latency.msec = 12` sicherstellen
- `rt.prio = 83` in der Config aktivieren (helft gegen Prozess-Störungen)

---

## 3. "clock jumped forward" in dmesg

**Bedeutung**: Phc2sys hat einen Sprung von ca. 1 Sekunde erkannt.

**Ursache**:
- **Früher**: `systemd-timesyncd` lief parallel und verursachte Sprünge
- **Heute**: Sollte nicht mehr auftreten, wenn timesyncd deaktiviert ist
(wird standardmäßig vor jedem ptp4l-start deaktiviert, siehe "Start Optionen")

**Lösung**:
```bash
Alternative zur automaischten abschaltung manuell deaktivieren mit:
sudo systemctl stop systemd-timesyncd
sudo timedatectl set-ntp false
```
Wenn das Problem weiterhin auftritt, prüfen Sie:
```bash
systemctl is-active systemd-timesyncd  # Soll "inactive" anzeigen
```

---

## 3. " clock.check" Warnungen in dmesg

**Bedeutung**: Phc2sys interner Schutzmechanismus.

**Ursache**: Phc2sys erkennt, dass zwei Dienste gleichzeitig auf CLOCK_REALTIME zugreifen (phc2sys + timesyncd). Das ist ein Schutzmechanismus, kein Hardware-Fehler.

**Lösung**:
- `systemd-timesyncd` deaktivieren (siehe Kapitel 2 der Einsteiger-Anleitung)
- In `/etc/linuxptp/phc2sys.conf`:
  ```
  sanity_freq_limit 0
  ```
  Dies deaktiviert die clockcheck-Warnungen.

---

## 4. "No such file or directory" für /dev/ptpX

**Bedeutung**: Das PTP-Device existiert nicht.

**Ursache**:
- Falscher Treiber installiert
- Nach Kernel-Update nicht neu gebaut

**Lösung**:
- ASIX Vendor-Treiber v4.1.0 installieren (nicht den Kernel-Treiber `ax88179_178a`)
- Nach Kernel-Update neu bauen:
  ```bash
  make clean && make -j$(nproc) && sudo make install
  sudo modprobe -r ax_usb_nic && sudo modprobe ax_usb_nic
  ```
- Blacklist hinzufügen: `echo "blacklist ax88179_178a" | sudo tee /etc/modprobe.d/blacklist-ax88179.conf`

---

## 5. "No such file or directory" für Konfigurationsdatei

**Bedeutung**: Die Datei `pipewire-aes67.conf` wurde nicht gefunden.

**Ursache**:
- Datei an falscher Stelle
- PipeWire liest standardmäßig aus `/etc/pipewire/`

**Lösung**:
- Kopiere/verschiebe die Config nach `/etc/pipewire/`
- Oder erstelle sie unter `~/.config/pipewire/pipewire-aes67.conf`
- Nach Neustart von PipeWire pruefen

---

## 6. "SDP: Das Argument ist ungültig"

**Bedeutung**: Die SDP-Sitzung konnte nicht erstellt werden.

**Ursache**:
- Inkompatible Parameter zwischen Sender und Empfänger
- Falsche `sess.min-ptime` / `sess.max-ptime` Werte
- Falsche Netzwerk-Parameter (Port, IP, TTL)

**Lösung**:
- Stelle sicher, dass beide Seiten gleiche `sess.min-ptime` und `sess.max-ptime` haben
- Prüfe `sess.ts-refclk = "ptp=traceable"` 
- Prüfe Netzwerk-Parameter (TTL, Port, Multicast-IP)
- Sicherstellen, dass `sess.min-ptime = 1` und `sess.max-ptime = 1` für Dante-kompatible Geräte gesetzt ist (oder `4` für stabileren Betrieb)

---

## 7. Zusammenfassung: Die "Checkliste" für einen fehlerfreien Start

Bevor du sync67 startest, prüfe bitte:

- [ ] `systemd-timesyncd` ist deaktiviert (`systemctl is-active systemd-timesyncd` = `inactive`)
- [ ] `clock.id = "realtime"` in pipewire-aes67.conf steht
- [ ] `clock.interface` ist auskommentiert (kommentiert gelassen)
- [ ] `sess.latency.msec = 12` (und Vielfaches von `sess.max-ptime`)
- [ ] `sess.max-ptime = 4` (empfohlen für Stabilität)
- [ ] `resync.ms = 48` und `max_resync = 4`
- [ ] Treiber ist der ASIX v4.1.0 (nicht der Kernel-Treiber `ax88179_178a`)
- [ ] Nach Kernel-Update: `make clean && make -j$(nproc) && sudo make install`

---

*Stand: Juni 2026. Basierend auf tausenden von Testminuten mit ASIX AX88279A, Kernel 6.17 und PipeWire 1.7.0.*
