# pipewire-aes67 – Quantum & Latenz-Konfiguration

## Warum die Quantum-Einstellung entscheidend ist

Die `quantum`-Einstellung in PipeWire determines die Blockgröße für die Audio-Verarbeitung. Sie wirkt sich direkt auf die Latenz und die Stabilität des AES67-Streams aus.

**Bei 48kHz Sample-Rate:**
- `quantum = 48` → 1ms (ein RTP-Paket)
- `quantum = 192` → 4ms (vier RTP-Pakete)
- `quantum = 128` → ~2,67ms (zwischenwert, nicht empfohlen)

## Warum 1ms ptime bei USB-ASIX problematisch ist

Der ASIX AX88279A USB-Adapter führt zu intermittierenden Latenz-Spitzen von 2-10ms im USB-Transfer-Layer. Bei `ptime = 1ms` (48 Samples) kommt es häufig zu `missing timeout`-Events, weil der PipeWire-Scheduler das nächste Paket nicht rechtzeitig fertigstellen kann, wenn der Timer feuert.

**Das Ergebnis:** Alle 30-60 Sekunden ein `expected != actual`-Event (verlustetes Paket = 256 Samples ≈ 5,33ms) und `missing timeout`-Events.

### Warum 4ms ptime die Lösung ist

Bei `sess.max-ptime = 4` (4ms-Pakete):
- Der PipeWire-Scheduler muss nur alle 4ms einen Timer feuern
- Die Wahrscheinlichkeit, dass ein USB-Jitter den Timer trifft, sinkt um den Faktor 4
- `missing timeout` tritt fast gar nicht mehr auf
- `expected != actual` tritt nur noch alle 1-2 Minuten auf (und ist nur ein einziger Paketverlust ≈ 5,33ms ≈ 1,3 Pakete bei 4ms ptime – für das menschliche Ohr meist unverhehrlich)

### Die Faustregel

| ptime | expected != actual Häufigkeit | hörbare Artefakte |
|---|---|---|
| 1ms | Alle 30-60s | deutlich |
| 4ms | Alle 60-120s | kaum bis gar nicht |

### Die config-Parameter im Zusammenspiel

| Parameter | Wert | Begründung |
|---|---|---|
| `sess.max-ptime` | `4` | Begrenzt die Paketgröße auf 4ms (192 Samples bei 48kHz) |
| `sess.latency.msec` | `12` | Puffer (muss Vielfaches von max-ptime sein: 12/4=3) |
| `resync.ms` | `48` | Alle 48ms wird der PTP-Abgleich geprüft (nicht 1,5!) |
| `max_resync` | `4` | Maximale Freeze-Zeit beim Resync (nicht 48!) |

**Wichtig:** `sess.latency.msec` muss ein Vielfaches von `sess.max-ptime` sein. 12/4 = 3 (ganzzahlig), 10/4 = 2,5 (Warning im Log).

## DAW-Einstellungen (DAW = Digital Audio Workstation)

Die DAW-Software (z.B. Behringer X32 mit X-Dante Card, Merging Horus) muss die Einstellungen des Senders unterstützen.

### Wichtigste Einstellungen in der DAW:

| Parameter | Empfehlung | Begründung |
|---|---|---|
| **Packet Time (ptime)** | `4ms` (192 Samples bei 48kHz) | Entspricht `sess.max-ptime = 4`; sorgt für Stabilität |
| **Buffer Size** | `12ms` (576 Samples) | Entspricht `sess.latency.msec = 12`; Puffer für USB-Jitter |
| **Crossfade** | `deaktiviert` | Vermeidetunstimmungen im Takt |
| **Sample Format** | `24-bit S24BE` | Entspricht der Pipewire-aes67 Konfig |

### Empfohlene DAW-Einstellungen (Beispiel Behringer X32)

| Einstellung | Wert | Anmerkung |
|---|---|---|
| **Input Sampling Rate** | `48000 Hz` | Standard für AES67 |
| **Packet Time (ptime)** | `4ms` (192 Samples) | Entspricht `sess.max-ptime = 4` |
| **Buffer Size** | `12ms` (576 Samples) | Entspricht `sess.latency.msec = 12` |
| **Crossfade** | `deaktiviert` | Vermeidetunstimmungen im Takt |
| **Sample Format** | `24-bit S24BE` | Entspricht der Pipewire-aes67 Konfig |

### Verbindung zum Sender (sync67)

Der Sender (Laptop mit sync67) sendet mit folgenden Parameter:

- `sess.max-ptime = 4` → Sender sendet 4ms-Pakete
- `sess.latency.msec = 12` → Sender puffernt 12ms Puffer vor dem Senden
- `sess.min-ptime = 1` → SDP signalisiert `ptime:1` (Kompatibilität mit alten Empfängern)

**Wichtig:** Der Empfänger muss können, 4ms-Pakete zu verarbeiten. Wenn der Empfänger nur `1ms` kann, entsteht ein Konflikt, der zu `expected != actual`-Events führt.

### Zusammenfassung der Konfig-Entwicklung

| Parameter | Stand vor Testreihe | Empfohlener Wert | Grund |
|---|---|---|---|
| `sess.max-ptime` | 1 (Standard) | `4` | Vermeidet `missing timeout` bei USB-Jitter |
| `sess.latency.msec` | 3 (Standard) | `12` | Vielfaches von max-ptime, mehr Puffer |
| `resync.ms` | 1,5 (Standard) | `48` | Vermeidet zu häufiges Resyncing |
| `max_resync` | nicht gesetzt | `4` | Begrenzt Freeze-Dauer beim Resync |

### Zusammenfassung

Die Kombination aus **4ms ptime**, **12ms Puffer** und **deaktiviertem systemd-timesyncd** hat sich als stabilste Konfiguration für AES67 über USB-ASIX erwiesen. Die Einstellungen der DAW sollten diese Parameter unterstützen, um optimale Ergebnisse zu erzielen.

---

*Stand: Juni 2026. Getestet mit ASIX AX88279A, Kernel 6.17 und PipeWire 1.7.0.*