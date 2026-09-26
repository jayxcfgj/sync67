# sync67 – Setup-Anleitung

Diese Anleitung hilft dir, sync67 einzurichten und AES67-Streaming mit PipeWire zum Laufen zu bringen, ohne dich in die technischen Details verlieren zu müssen.

---

## 0. Kurz-Glossar (die wichtigsten Begriffe)

| Begriff | Was ist das? | Was macht es? |
|---|---|---|
| **PTP** | Precision Time Protocol | Synchronisiert Uhren im Netzwerk auf <1µs genau |
| **PHC** | PTP Hardware Clock | Hardware-Zähler auf der Netzwerkkarte, der die PTP-Zeit zählt |
| **ptp4l** | PTP-Daemon aus linuxptp | Regelt den PHC über Netzwerk-Nachrichten (GM/Slave) |
| **phc2sys** | Tool aus linuxptp | Kopiert PHC → CLOCK_REALTIME (damit auch Anwendungen die PTP-Zeit sehen) |
| **GM** | Grandmaster | Die Zeitquelle – gibt die Referenz-Zeit vor |
| **Slave** | Folgt dem GM | Gleicht seinen PHC an den GM an |
| **AES67** | Audio-over-IP-Standard | Professionelles Netzwerk-Audio (kompatibel mit Dante, Ravenna) |
| **SDP** | Session Description Protocol | Beschreibt einen AES67-Stream (IP, Port, Format, Latenz) |
| **ptime** | Packet Time | Dauer eines RTP-Pakets in ms (1ms = 48 Samples bei 48kHz) |
| **timesyncd** | systemd NTP-Client | Korrigiert CLOCK_REALTIME per Internet-Zeitserver |
| **CLOCK_REALTIME** | Systemuhr | Die Uhr die Anwendungen (auch PipeWire) sehen |

---

## 1. Voraussetzungen

### Hardware

| Komponente | Hinweis |
|---|---|
| **PTP-fähige Netzwerkkarte** | ASIX AX88279/A (USB), Intel i210/i225/i226 (PCIe) |
| **Zweites Netzwerk-Interface** (optional) | Für PTP + Audio-Daten-Trennung |
| **AES67-Empfänger** | z.B. Behringer X32 mit X-Dante Card, Merging Horus, etc. |

### Software (Installation)

```bash
# Pakete installieren
sudo apt install python3-pyqt6 linuxptp

# PipeWire + pipewire-aes67 muss installiert sein (meist schon)
sudo apt install pipewire pipewire-aes67

# sync67 clone
git clone https://github.com/jayxcfgj/sync67.git
cd sync67
```

---

## 2. ASIX AX88279/A USB-Dongle – Treiber-Installation

> **Nur nötig wenn du einen ASIX USB-Dongle verwendest.** Besitzer einer Intel i210/i225/i226 PCIe-Karte können diesen Schritt überspringen.

### Hintergrund

Die Kernel-Treiber `ax88179_178a` (ab Linux 6.17) erkennen den AX88279A zwar und binden ihn ein, erstellen aber **kein `/dev/ptpX`** – PTP funktioniert damit nicht. Du benötigst den Treiber von der ASIX-Webseite.

Der ASIX-Treiber `ax_usb_nic` braucht **keine Patches oder Modifikationen** – alle "Hardware-Bug"-Patches, die früher empfohlen wurden, beruhten auf einer Fehlannahme (siehe Fehler 8.6).

### Treiber installieren

```bash
# 1. Kernel-Treiber blacklisten (damit nicht der falsche geladen wird)
echo "blacklist ax88179_178a" | sudo tee /etc/modprobe.d/blacklist-ax88179.conf
sudo update-initramfs -u

# 2. Treiber von ASIX-Webseite herunterladen
# → https://www.asix.com.tw/en/product/USBEthernet/Super-Speed_USB_Ethernet/AX88279A
# → Download "ASIX USB Ethernet Driver Source v4.1.0" (oder neuer)
# → Nach ~/ entpacken

# 3. Bauen & Installieren
cd ~/ASIX_USB_NIC_Linux_Driver_Source_v4.1.0/
make clean && make -j$(nproc)
sudo make install

# 4. Dongle neu einstecken oder Treiber laden
sudo modprobe -r ax_usb_nic 2>/dev/null
sudo modprobe ax_usb_nic
```

### Nach der Installation prüfen

```bash
# Dongle erkennen?
ethtool -i enx...
# → driver: ax_usb_nic, version: 4.1.0

# PTP-Device vorhanden?
ls /dev/ptp*
# → /dev/ptp0 oder /dev/ptp1 (abhängig von anderen PTP-Geräten)

# PHC lesbar?
sudo phc_ctl /dev/ptp0 get
# → OK wenn keine Fehlermeldung
```

### Wichtige Hinweise

- **Nach jedem Kernel-Update** muss der Treiber neu gebaut werden: `make clean && make -j$(nproc) && sudo make install`
- **PHC-Index kann wechseln** – wenn du den Dongel aussteckst und wieder einsteckst, kann sich `/dev/ptp0` zu `/dev/ptp1` ändern (vor allem wenn andere PTP-Geräte wie i210 vorhanden sind). sync67 erkennt den richtigen Index automatisch.
- **Keine Patches nötig** – baue den Treiber so wie er von ASIX kommt, ohne Änderungen am Quellcode.
- **Offloading deaktivieren** (optional, aber empfohlen) – siehe nächster Abschnitt.

### Treiber-Konfiguration für AES67

Im Treiber-Verzeichnis gibt es die Datei `ax_config.h`. Für AES67 sollten folgende Werte gesetzt sein:

| Parameter | Wert | Begründung |
|---|---|---|
| `ENABLE_PTP_FUNC` | `1` | PTP-Hardware-Timestamps aktivieren |
| `ENABLE_LSO` | `0` | Large Send Offload aus → verhindert PTP-Paket-Verzögerung durch HW-Segmentierung |
| `ENABLE_COE` | `0` | Checksum Offload aus → NIC soll Pakete nicht modifizieren |
| `ENABLE_INT_AGGRESSIVE` | `0` | Keine aggressiven Interrupts → weniger Jitter |
| `ENABLE_AUTOSUSPEND` | `0` | Auto-Suspend aus → NIC bleibt immer wach |

Alle anderen Parameter auf `0` (Default) lassen:
```
ENABLE_PTP_PPS        0   # PPS-Ausgang nicht benötigt
ENABLE_PTP_125M_CLK   0   # 125MHz-Referenz nicht benötigt
ENABLE_INT_POLLING     0   # Polling nur für Debug
ENABLE_QUEUE_PRIORITY  0   # Priorisierung über Linux tc
ENABLE_TX_TASKLET      0   # Interrupt-getrieben reicht
ENABLE_RX_TASKLET      0   # ...
```

**Nach Änderung neu bauen und installieren:**
```bash
make clean && make -j$(nproc) && sudo make install
sudo modprobe -r ax_usb_nic && sudo modprobe ax_usb_nic
```


---

## 4. systemd-timesyncd deaktivieren (wichtig!)

**`systemd-timesyncd` und `phc2sys` dürfen nicht gleichzeitig laufen.** Beide versuchen `CLOCK_REALTIME` zu regeln → sie kämpfen gegeneinander → 1-Sekunden-Sprünge alle ~32s → AES67 bricht zusammen.

```bash
sudo systemctl stop systemd-timesyncd
sudo timedatectl set-ntp false
# (Erzwingt auch: sudo systemctl disable --now systemd-timesyncd)
```

> **Nach Reboot prüfen:** `systemctl is-active systemd-timesyncd` muss `inactive` zeigen.

---

## 5. Schnellstart: Session-Tab

Der Session-Tab macht das Wichtigste mit einem Klick:

1. PTP-Interface und PHC-Gerät auswählen
2. (optional) phc2sys-Checkbox aktivieren – siehe Kapitel 8
3. Auf **Start** klicken
4. sync67 startet automatisch: ptp4l → (phc2sys) → AES67
5. Ampel zeigt grün wenn alles synchron ist

> **Session-Tab = Empfohlener Weg für den Alltag.**

---

## 6. Manuelle Konfiguration (PTP-Tab + AES67-Tab)

Falls du die Parameter selbst einstellen möchtest:

### 6.1 ptp4l konfigurieren

Im PTP-Tab → Config Editor öffnen.

**Wichtige Parameter:**

| Parameter | Empfehlung | Begründung |
|---|---|---|
| `[global]` | – | – |
| `clockClass` | `248` (Slave) / `6` (GM) | Slave = folgt GM, GM = Master |
| `domainNumber` | `0` | AES67-Default |
| `uds_address` | `/var/run/ptp4l` | RW-Socket für phc2sys (Auto-Modus) |
| `ptp_dst_mac` | `01:1B:19:00:00:00` | Event-Multicast (AES67) |
| `p2p_dst_mac` | `01:80:C2:00:00:0E` | Peer-Delay-Multicast |
| `network_transport` | `L2` | Layer-2 (AES67-konform) |

**Interface-Optimierung:** sync67 kann automatisch GRO/GSO/TSO/SG ausschalten, Multicast-Filter setzen und WoL deaktivieren (Button im PTP-Tab).

### 6.2 pipewire-aes67 konfigurieren

Im AES67-Tab → Config Editor öffnen.

**Empfohlene Einstellungen (stabil getestet):**

```ini
# PTP-Taktquelle
clock.id = "realtime"
# clock.interface AUSKOMMENTIERT lassen (sonst wird clock.id ignoriert)
#clock.interface = "enx..."

# Sync-Intervall
resync.ms  = 48     # alle 48ms (nicht 1.5!)
max_resync = 4      # kurzer Freeze bei Resync (nicht 48!)

# RTP-Paketgröße
# 1ms = 48 Samples/Paket (sehr CPU-intensiv, viele Timeouts)
# 4ms = 192 Samples/Paket (stabil, empfohlen für USB-Ethernet)
sess.min-ptime = 1   # Minimum (geht ins SDP)
sess.max-ptime = 4   # Maximum (optional, Empfänger muss >=4ms unterstützen)
sess.latency.msec = 12  # Puffer (muss Vielfaches von max-ptime sein: 12/4=3)

# Priorität
nice.level = -11
rt.prio     = 83
```

**Warum 4ms statt 1ms?**

Die wichtigste Erkenntnis aus der Praxis: **1ms-Pakete sind für USB-Ethernet nicht stabil.** PipeWires Scheduler kann nicht zuverlässig alle 1ms den RTP-Timer bedienen → ständige `missing timeout`-Warnungen → alle 30-60s ein verlorenes Paket → hörbare Artefakte.

Mit 4ms-Paketen sinkt die Timer-Rate auf 1/4 → keine `missing timeout` mehr, kaum noch Paketverluste.

> **Achtung bei Dante-Geräten:** Manche Dante-Hardware (z.B. X32 X-Dante Card) wählt automatisch die niedrigste vom System gemeldete Latenz. `sess.min-ptime = 1` ist der sichere Default. `sess.max-ptime = 4` erlaubt 4ms-Pakete ohne den SDP zu ändern – der SDP sagt weiterhin `ptime:1`.

---

## 7. Netzwerk-Verkabelung

### Empfehlung: Zwei getrennte Netze

```
[Laptop] ─── USB-ASIX (PTP + AES67) ─── Switch ─── [X32/Dante]
           └── WiFi/eth0 (Internet/Rest)
```

- **Ein Netzwerk für PTP + AES67** (dedizierter Switch, kein Internet)
- **Ein zweites Interface für alles andere** (WiFi, zweiten Ethernet-Port)

Warum? PTP ist empfindlich gegen Netzwerk-Last durch andere Dienste. Ein getrennter PTP-Switch vermeidet Jitter durch Fremdverkehr.

### Falls nur ein Netzwerk möglich:

```ini
# In ptp4l.conf:
ptp_dst_mac = 01:1B:19:00:00:00
p2p_dst_mac = 01:80:C2:00:00:0E
```

ptp4l filtert dann nur noch PTP-Pakete, der Rest wird ignoriert.

---

## 8. Szenarien: Was brauche ich wirklich?

### Szenario A: Laptop = Grandmaster (GM), ASIX USB

```
ptp4l-GM → ASIX-PHC → phc2sys → CLOCK_REALTIME → pipewire → AES67-Stream
```

| Benötigt | phc2sys | clock.id |
|---|---|---|
| **Ja** | phc2sys kopiert PHC → REALTIME | `realtime` |

**Warum phc2sys?** Der ASIX-PHC hält die PTP-Zeit (GM). REALTIME driftet ohne phc2sys frei auf dem Quarz (~20-50ppm) → pipewire-Timestamps weichen ab → Empfänger sieht inkonsistente Timestamps.

### Szenario B: Laptop = Slave (folgt GM), ASIX USB

```
ptp4l-Slave → ASIX-PHC (geregelt auf GM) → phc2sys → CLOCK_REALTIME → pipewire
```

| Benötigt | phc2sys | clock.id |
|---|---|---|
| **Ja** | sonst driftet REALTIME weg | `realtime` |

**Hinweis:** `-O 0` statt `-w` im phc2sys-Befehl verwenden (siehe Kapitel 10.3).

### Szenario C: Main PC = Slave, Intel i210 PCIe

```
ptp4l-Slave → i210-PHC → pipewire (Direkt-Read über clock.interface)
```

| Benötigt | phc2sys | clock.id |
|---|---|---|
| **Nein** | PHC wird direkt gelesen | `clock.interface = "enp..."` |

**Warum kein phc2sys?** i210 ist PCIe → kein USB-Jitter. Direkter PHC-Read liefert saubere Timestamps. REALTIME wird nicht verwendet.

### Entscheidungsmatrix

| Rolle | Interface | clock.id | phc2sys? | Begründung |
|---|---|---|---|---|
| GM (Laptop) | USB-ASIX | `realtime` | **Ja** | REALTIME muss PTP-Zeit folgen |
| GM (PC) | PCIe-i210 | `interface` | **Nein** | Direkt-Read, kein Jitter |
| Slave (Laptop) | USB-ASIX | `realtime` | **Ja** | REALTIME driftet sonst weg |
| Slave (PC) | PCIe-i210 | `interface` | **Nein** | Direkt-Read, kein Jitter |

---

## 9. phc2sys im Detail

### Wann brauche ich phc2sys?

**Grundregel:** Wenn `clock.id = "realtime"` in der AES67-Config steht → **phc2sys muss laufen**, sonst driftet `CLOCK_REALTIME` unkontrolliert.

**Du brauchst KEIN phc2sys, wenn:**
- Du `clock.interface = "enp..."` (i210) verwendest
- Du `clock.id = "monotonic"` (kein PTP) verwendest

### phc2sys starten (Session-Tab)

Die phc2sys-Checkbox im Session-Tab macht alles automatisch:
1. `-s /dev/ptpX` zum richtigen PHC
2. `-c CLOCK_REALTIME` als Ziel
3. `-O 0` statt `-w` (wichtig bei ptp4l-Slave)
4. `-z /var/run/ptp4l` für UDS-Kommunikation (Auto-Modus)

### Wichtige phc2sys-Parameter

| Flag | Bedeutung |
|---|---|
| `-s /dev/ptpX` | PHC-Quelle (z.B. `/dev/ptp0`, `/dev/ptp1`) |
| `-c CLOCK_REALTIME` | Zieluhr |
| `-O 0` | UTC-Offset (0 = UTC). **Nicht `-w` verwenden bei ptp4l-Slave** |
| `-z /var/run/ptp4l` | UDS-Socket-Pfad |
| `-a -r` | Auto-Modus (liest ptp4l-Management) |

---

## 10. Häufige Fehler & Lösungen

### 10.1 "missing timeout 2-6" in pipewire-aes67

**Ursache:** RTP-Paket kam zu spät (USB-Jitter oder Scheduling-Problem bei 1ms ptime).

**Lösung:**
- `sess.max-ptime = 4` setzen (4ms Pakete statt 1ms)
- `sess.latency.msec = 12` setzen (größerer Puffer)
- `resync.ms = 48` (nicht 1.5!)

### 10.2 "timestamp: expected X != actual Y" (5,33ms Lücke)

**Ursache:** Paketverlust durch aufgestaute Timeouts.

**Lösung:** Siehe 8.1. Bei 4ms ptime und stabiler Konfiguration tritt das nur noch ~1x pro Minute auf und ist nicht hörbar.

### 10.3 phc2sys konvergiert nicht / Offset bei ~37s

**Ursache:** `-w`-Flag verwendet, das den UTC-Offset (37s TAI-UTC) von ptp4l abfragt. Bei ptp4l-Slave wird der Offset inkorrekt berechnet.

**Lösung:** `-w` durch `-O 0` ersetzen:
```bash
# FALSCH (bei ptp4l-Slave):
phc2sys -s /dev/ptp0 -c CLOCK_REALTIME -m -w

# RICHTIG:
phc2sys -s /dev/ptp0 -c CLOCK_REALTIME -m -O 0
```

### 8.4 "clock jumped forward" in phc2sys

**Ursache:** Entweder timesyncd läuft parallel (siehe Kapitel 2) oder clockcheck-Schutz bei gleichzeitigem ptp4l-Slave.

**Lösung:**
```bash
# 1. Prüfen ob timesyncd läuft:
systemctl is-active systemd-timesyncd  # muss "inactive"
sudo systemctl stop systemd-timesyncd  # falls nicht

# 2. clockcheck deaktivieren (in phc2sys.conf):
sanity_freq_limit 0
```

### 8.5 Kein /dev/ptpX nach Treiber-Wechsel

**Ursache:** Der Stock-Kernel-Treiber `ax88179_178a` erstellt in neueren Kernel-Versionen (ab 6.17) keinen PTP-Device mehr. Der ASIX-Vendor-Treiber `ax_usb_nic` wird benötigt.

**Lösung:** ASIX-Treiber von der Webseite laden, bauen, installieren (sync67 kann das nicht automatisch). Der Treiber braucht **keine Patches** – die "Hardware-Bug"-Patches waren unnötig.

```bash
# Treiber bauen
cd ASIX_USB_NIC_Linux_Driver_Source_v4.1.0/
make clean && make -j$(nproc)
sudo make install
sudo modprobe -r ax_usb_nic && sudo modprobe ax_usb_nic
```

---

## 9. Referenz: pipewire-aes67.conf (vollständig)

```ini
# PTP-Clock-Driver
{ factory = spa-node-factory
    args = {
        factory.name    = support.node.driver
        node.name       = PTP0-Driver
        node.group      = pipewire.ptp0
        priority.driver = 100000
        clock.name      = "clock.system.ptp0"
        #clock.interface = "enx..."          # AUSKOMMENTIERT!
        clock.id        = "realtime"          # phc2sys regelt REALTIME
        resync.ms       = 48
        max_resync      = 4
        object.export   = true
    }
}

# RTP-Sink (Sender)
{ name = libpipewire-module-rtp-sink
    args = {
        destination.ip = "239.69.150.243"
        destination.port = 5004
        net.mtu = 1280
        net.ttl = 32
        net.loop = false
        sess.min-ptime   = 1    # Minimum (geht ins SDP)
        sess.max-ptime   = 4    # Erlaubt 4ms-Pakete
        sess.name = "Mein AES67 Stream"
        sess.media = "audio"
        sess.ts-refclk = "ptp=traceable"
        sess.ts-offset = 0
        sess.ts-direct = false
        sess.latency.msec = 12   # Puffer (12/4 = 3, sauber)
        audio.format = "S24BE"
        audio.rate = 48000
        audio.channels = 2
        stream.props = {
            node.name = "rtp-sink"
            media.class = "Audio/Sink"
            device.api = aes67
            sess.sap.announce = true
            node.group = pipewire.ptp0
        }
    }
}
```

---

## 10. Glossar

| Begriff | Bedeutung |
|---|---|
| **PTP** | Precision Time Protocol – Netzwerk-Zeitsynchronisation |
| **PHC** | PTP Hardware Clock – Hardware-Zähler auf der Netzwerkkarte |
| **GM** | Grandmaster – die Zeitquelle im PTP-Netzwerk |
| **Slave** | Folgt der Zeit des GM |
| **phc2sys** | Tool zum Kopieren PHC → CLOCK_REALTIME |
| **ptp4l** | PTP-Daemon (regelt PHC via Netzwerk) |
| **AES67** | Audio-over-IP-Standard für professionelles Audio |
| **SDP** | Session Description Protocol – beschreibt einen AES67-Stream |
| **ptime** | Packet Time – Dauer eines RTP-Pakets in ms |
| **Dante** | Proprietäres Audio-over-IP-System von Audinate |
| **timesyncd** | systemd-eigener NTP-Client |

---

*Stand: 2026-06-11. Getestet mit ASIX AX88279A USB + Kernel 6.17 + LinuxPTP v4.4 + PipeWire 1.7.0.*
