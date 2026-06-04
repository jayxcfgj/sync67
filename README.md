![sync67](assets/hero-header.png)

# sync67

A Linux desktop tool for managing, monitoring and configuring **AES67 audio streaming** with **PipeWire**.

> sync67 does **not** replace patchbay tools like qpwgraph, helvum or coppwr.
> Those are used alongside sync67 for audio routing and patching.

---

## Features

### PTP Tab

- ptp4l start/stop with live terminal output
- Sync indicator (traffic light: green ≤200ns, yellow ≤1000ns, red) + port state
- Interface optimization (gro/gso/tso/sg, rx-usecs, PHC reset, multicast, WoL disable)
- **PTP4L Config Editor**: format-preserving GUI for `/etc/linuxptp/ptp4l.conf` (119 parameters, 7 tabs, auto-detected supported params)
- **phc2sys**: start/stop with status ampel + config editor, auto-detected PHC device

### AES67 Tab

- pipewire-aes67 start/stop with live terminal output, verbose mode toggle
- Stream health monitor with DSP load and log-based severity (green/yellow/red)
- **AES67 Config Editor**: format-preserving GUI for `pipewire-aes67.conf` (40 parameters, 4 tabs, RTP Sink multi-instance, stream.rules raw editor)

### PipeWire Tab

- Sample rate / quantum control with Apply/Reset/Refresh
- Node table with tree structure (ID, status, name, quantum, format, channels, DSP, xruns, rate)
- Xruns counter (click to reset), DSP load bar, latency display

### Session Tab

- **Quick-Start**: single-button start/stop with correct ordering
  - Optional phc2sys integration (checkbox, default off)
  - Start: ptp4l → (phc2sys) → AES67, polls each stage until ready
  - Stop: AES67 → phc2sys → ptp4l
- System status overview (PTP, phc2sys, AES67, PipeWire)
- PTP + phc2sys + AES67 health traffic lights + xruns + DSP
- Version block with minimum version checks
- Routing tool launchers (qpwgraph, helvum, coppwr) – native + Flatpak + AppImage

---

## Requirements

| Component | Usage |
|---|---|
| Python 3 | Runtime |
| PyQt6 | GUI Framework |
| PipeWire | Audio backend (with pipewire-aes67, pw-top, pw-metadata) |
| LinuxPTP (ptp4l) | PTP clock synchronization |
| qpwgraph / helvum / coppwr | Optional – external routing tools |

---

## Installation

```bash
git clone https://github.com/jayxcfgj/sync67.git
cd sync67
```

*Debian / Ubuntu / Linux Mint:*
```bash
sudo apt install python3-pyqt6 linuxptp
```

*Arch Linux:*
```bash
sudo pacman -S python-pyqt6 linuxptp
```

*Fedora:*
```bash
sudo dnf install python3-qt6 linuxptp
```

> PipeWire is required and already installed on most systems.

```bash
sudo python3 main.py
```

---

## License

MIT License

Copyright 2026 jayxcfgj

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
