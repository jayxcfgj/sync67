# sync67 – Einsteiger-Dokument

Willkommen bei sync67! Diese Anleitung hilft dir, das Tool schnell und ohne tiefes technisches Vorwissen einzurichten. Hier erfährst du, was du brauchst, wie du die wichtigsten Fallstricke umgehst und deine AES67-Streaming-Übertragung startest.

## 1. Was ist sync67?

**sync67** ist ein Linux-Tool für die Verwaltung, Überwachung und Konfiguration von **AES67-Audio-Streaming** über PipeWire. Es arbeitet zusammen mit:

- **ptp4l** (Teil von LinuxPTP) – regelt die PTP-Zeit (Grandmaster → Slave)
- **phc2sys** – kopiert PHC-Zeit auf CLOCK_REALTIME
- **pipewire-aes67** – überträgt Audio über RTP im Netzwerk

sync67 ersetzt **nicht** Tools wie qpwgraph, helvum oder coppwr – diese werden *neben* sync67 für die Audio-Routing-Schaltung verwendet.

## 2. Installation

### Benötigte Pakete

```bash
# Unter Debian/Ubuntu/Mint:
sudo apt update
sudo apt install python3-pyqt6 linuxptp

# Dann sync67 klonen und starten:
git clone https://github.com/jayxcfgj/sync67.git
cd sync67
sudo python3 main.py
```

### Wichtige Hinweise zur Installation

- **PTP-fähige Netzwerkkarte**: Entweder ASIX AX88279/A (USB) oder Intel i210/i225/i226 (PCIe)
- **Zweites Netzwerk-Interface** (optional): Für Trennung von PTP-Datenverkehr und normalem Internetverkehr
- **AES67-Empfänger**: z.B. Behringer X32 mit X-Dante Card, andere Dante-fähige Geräte




## 3. Erste Schritte mit sync67

### Der Session-Tab (empfohlener Weg)

Der Session-Tab ist der einfachste Einstieg:

1. Öffne sync67 und gehe zum **Session-Tab**
2. Wähle dein PTP-Interface (meist `ptp0` oder `ptp1`)
3. **Optional**: Aktiviere die phc2sys-Checkbox (siehe Erklärung unten)
4. Klicke auf **Start**

sync67 startet automatisch die Kette: `ptp4l → (phc2sys) → AES67`. Jeder Schritt wird geprüft, und du siehst Ampel-Symbole (grün = OK, gelb = Warnung, rot = Fehler).

### Ohne phc2sys (Alternative)

Du kannst phc2sys auch weglassen, wenn du folgende Einstellung wählst:
- In der pipewire-aes67.conf: `clock.id = "realtime"` (und `clock.interface` auskommentiert lassen)
- Dann liest PipeWire direkt die CLOCK_REALTIME

> **Wichtig**: Ohne phc2sys driftet die CLOCK_REALTIME irgendwann vom PTP-Zeitwert ab, wenn du keinen NTP-Server (wie chronyd) laufen hast.

## 4. Wichtige Konfiguration

### pipewire-aes67.conf – die wichtigsten Parameter

Öffne die Config-Datei (meist unter `~/.config/pipewire/pipewire-aes67.conf`) und stelle sicher Folgendes:

```ini
clock.id = "realtime"
#clock.interface = "enx..."   <-- ACHTUNG: AUSKOMMENTIEREN!
resync.ms = 48
max_resync = 4
sess.min-ptime = 1
sess.max-ptime = 4
sess.latency.msec = 12
rt.prio = 83
```

**Warum diese Werte?**

- `clock.id = "realtime"`: PipeWire nutzt die Systemuhr
- `clock.interface` auskommentiert: Damit `clock.id` wirkt (sonst wird die Interface-Einstellung bevorzugt)
- `resync.ms = 48`: Alle 48ms wird der PTP-Abgleich geprüft (1.5ms war zu aggressiv)
- `max_resync = 4`: Der Resync-Freeze dauert maximal 4ms (nicht 48, das verursacht Artefakte)
- `sess.max-ptime = 4`: 4ms-Pakete statt 1ms (vermeidet Scheduling-Probleme bei 1ms-Paketen)
- `sess.latency.msec = 12`: Puffer von 12ms (muss Vielfaches von max-ptime=4 sein: 12/4=3)
- `rt.prio = 83`: Echtzeit-Priorität für PipeWire (helft gegen Störungen durch andere Prozesse)

### Netzwerk-Einrichtung

**Empfohlen: Zwei separate Netze**

```
[Laptop] ─── USB-ASIX (PTP + AES67) ─── Switch ─── [X32/Dante]
           └── WiFi/eth0 (Internet/Rest)
```

- **Einschalten**: Ein Netzwerk nur für PTP + AES67 (dedizierter Switch, kein Internet)
- **Zweites Netzwerk**: Für Internet, Updates, andere Dienste

> **Falls nur ein Netzwerk möglich**: nutze in ptp4l.conf:
> ```
> ptp_dst_mac = 01:1B:19:00:00:00
> p2p_dst_mac = 01:80:C2:00:00:0E
> ```
> Dann filtert ptp4l nur noch PTP-Pakete.

## 5. Häufige Probleme und Lösungen

### Problem 1: "missing timeout 2-4" in der Konsole

**Ursache**: RTP-Paket kam zu spät (USB-Jitter oder Scheduling-Problem).

**Lösung**: 
- `sess.max-ptime = 4` setzen (4ms-Pakete)
- `sess.latency.msec = 12` setzen (größerer Puffer)
- `resync.ms = 48` (nicht 1.5)

### Problem 2: "expected X != actual Y" (256 Samples Lücke)

**Ursache**: Ein RTP-Paket ging verloren oder wurde verzögert (5,33ms Entsprechung bei 48kHz).

**Lösung**: Bei 4ms ptime tritt das seltener auf (ca. alle 1-2 Minuten). Die Audio-Qualität bleibt meistens erhalten.

### Problem 3: "clock jumped forward" in dmesg

**Ursache**: Früher: timesyncd lief parallel. Heute: sollte nicht mehr auftreten.

**Lösung**: Stelle sicher, dass `systemd-timesyncd` deaktiviert ist (siehe Kapitel 2).

### Problem 4: Kein /dev/ptpX Device

**Ursache**: Falscher Treiber installiert.

**Lösung**: 
- Nutze den ASIX Vendor-Treiber v4.1.0 (nicht den Kernel-Treiber `ax88179_178a`)
- Nach Kernel-Update: `make clean && make -j$(nproc) && sudo make install`
- Blacklist: `echo "blacklist ax88179_178a" | sudo tee /etc/modprobe.d/blacklist-ax88179.conf`

## 5. Häufige Fragen (FAQ)

### Q: Brauche ich einen Grandmaster (GM)?

**A**: Ja, für AES67 brauchst du eine PTP-GM (Grandmaster).
Der PC kann auch als GM fungieren, ist jedoch nicht empfohlen.
Grundsätzlich sollte immer das Dante-Gerät die Role des  Grandmasters übernehmen.


### Q: Wie oft muss ich den Treiber des ASIX-USB-NIC neu bauen?

**A**: Bei jedem Kernel-Update muss der ASIX-Treiber neu kompiliert werden:
```bash
make clean && make -j$(nproc) && sudo make install
```

## 6. Abschließende Tipps

- Starte immer erst `systemd-timesyncd` deaktivieren, bevor du sync67 startest
- Nutze den Session-Tab für den schnellsten Start
- Behalte die Ampel-Anzeigen im Blick (grün = alles OK)
- Bei Problemen zuerst die Logs in sync67 ansehen


---
*Stand: Juni 2026. Basierend auf Erfahrungen mit ASIX AX88279A, Linux Kernel 6.17 und PipeWire 1.7.0.*
