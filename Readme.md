![sync67](assets/hero-header.png)

# sync67

A Linux desktop tool for managing, monitoring and configuring **AES67 audio streaming** with **PipeWire**.

> **sync67 does NOT replace patchbay tools** like qpwgraph, helvum or coppwr.
> Those are used alongside sync67 for audio routing and patching.

---

## Features

### PTP Tab
- Network interface selection (via `ip link show`)
- ptp4l start/stop with live terminal output
- Sync status indicator (traffic light: green ≤200ns, yellow ≤1000ns, red)
- ethtool/ip link optimization settings (gro, gso, tso, sg, rx-usecs, multicast)
- **PTP4L Config Editor**: full GUI editor for `/etc/linuxptp/ptp4l.conf`
  - 119 parameters across 7 tabs (Quick, Default, Port, Runtime, Servo, Transport, Interface)
  - Quick tab with 10 essential parameters
  - Format-preserving parser, Reset Config button
  - Deviation highlighting, tooltips, dark theme

### AES67 Tab
- pipewire-aes67 start/stop with live terminal output
- Open config file in external editor
- **AES67 Config Editor**: full GUI editor for `pipewire-aes67.conf`
  - 40 parameters across 4 tabs (PTP Clock, RTP SAP Input, RTP Sink Output, Expert)
  - Format-preserving SPA parser (comments and formatting preserved)
  - RTP Sink multi-instance support (add/remove)
  - System Clock checkbox (bypasses PHC timestamp-0 issue when running as root)
  - Deviation highlighting when value differs from default
  - stream.rules raw editor in Expert tab
  - Dark theme

### PipeWire Tab
- Sample Rate control (48000, 96000, 192000) with Apply/Reset/Refresh
- Quantum control (16-8192, editable) with Apply/Reset/Refresh
  - Uses `clock.force-rate` / `clock.force-quantum` for immediate node effect
- Effective value display from `pw-top` when metadata is default
- Latency display (calculated from Quantum × Sample Rate)
- Xruns counter (click to reset)
- DSP Load with colored progress bar (green/yellow/red)
- **Node table** with tree structure (parent-child via `└─`)
  - Columns: ID, Status (Running/Idle/Closed), Name, Quantum, Format, CH, DSP, Waiting, Busy, Xruns, Rate
  - Read-only, column widths remembered via QSettings
  - Updates every 2s via `pw-top` (second iteration for effective Running states)

### Session Tab
- **Quick-Start**: Start ptp4l + pipewire-aes67 in the correct order with one button
  - Start sequence: ptp4l → 2s delay → pipewire-aes67
  - Stop sequence: aes67 → ptp4l
- **System Status**: overview of PTP, AES67, and PipeWire at a glance
- PTP Sync traffic light + offset display
- Xruns counter + DSP load bar (from PipeWire tab)
- **Versions block**: PipeWire, LinuxPTP, Python, PyQt6 (installed/missing)
- **Routing Tools**: buttons to launch qpwgraph, helvum, coppwr (native + Flatpak detection)
- **About dialog**: version info, author, license, technology stack

---

## Requirements

| Component | Usage |
|---|---|
| Python 3 | Runtime |
| PyQt6 | GUI Framework |
| PipeWire | Audio backend (with pipewire-aes67, pw-top, pw-metadata, pw-cli) |
| LinuxPTP (ptp4l) | PTP clock synchronization |
| qpwgraph / helvum / coppwr | Optional – external routing/patchbay tools |

---

## Installation

*(Instructions to be added – currently in early development / Proof-of-Concept phase)*

**Quick start:**
```bash
sudo python3 main.py
```

The app runs as root (`os.getuid() == 0`). Environment variables `XDG_RUNTIME_DIR`,
`DBUS_SESSION_BUS_ADDRESS`, and `HOME` are automatically set to the original user's
values via `SUDO_UID` to ensure PipeWire and D-Bus connectivity.

---

## Project Structure

```
sync67/
├── main.py                  # Application entry point
├── core/
│   ├── aes67_config.py      # SPA config parser/serializer
│   ├── aes67_config_meta.py # Parameter definitions (~40 params)
│   ├── ptp4l_config.py      # PTP4L config parser/serializer
│   ├── ptp4l_config_meta.py # Parameter definitions (~119 params)
│   ├── ptp4l_default.cfg    # Default PTP4L config for reset
│   └── version.py           # Version, app info, license
├── ui/
│   ├── main_window.py       # Main window with tab widget
│   ├── ptp_tab.py           # PTP clock tab
│   ├── aes67_tab.py         # AES67 control tab
│   ├── aes67_settings_dialog.py  # Config editor dialog
│   ├── pipewire_tab.py      # PipeWire monitoring tab
│   ├── session_tab.py       # Session management tab
│   ├── about_dialog.py      # About dialog
│   ├── ptp4l_config_dialog.py # PTP4L config editor dialog
│   └── settings_dialog.py   # PTP ethtool settings
├── docs/
│   ├── mvp.md               # MVP roadmap
│   └── impl-aes67-config-editor.md  # Implementation plan
├── AGENTS.md                # Agent guidance (internal)
├── Handout.md               # Project overview (German)
└── README.md                # This file
```

---

## Architecture Principles

- **Small steps**: No huge monolithic solutions. Small, testable features.
- **No over-engineering**: Understandable, maintainable, pragmatic.
- **Modularity**: UI, services, core logic, widgets are separated.
- **UI ↔ Logic separation**: UI → Service Layer → System process.
- **GUI grows organically** with features, not designed upfront.
- **Existing Linux audio tools are respected**: sync67 complements qpwgraph, helvum, coppwr.

---

## License

MIT License

Copyright 2026 jaxcfgj

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## Name

**sync67** stands for:

- AES**67**
- **Sync**hronization
- PTP Clocking
- Realtime Audio Networking
