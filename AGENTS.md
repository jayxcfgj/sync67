# sync67 Agent Guidance

## Project Structure
- `ui/` - Qt windows, tabs, widgets
- `services/` - System services and process management (ptp_service.py, pipewire_service.py, aes67_service.py)
- `core/` - Shared helper functions and infrastructure
- `widgets/` - Reusable GUI components

## Key Conventions
- Strict separation of UI and logic: UI → Service Layer → System Process
- Develop small, vertical features (e.g., complete PTP tab before moving to next module)
- No GNOME-specific technologies; desktop-independent architecture
- Distribution-independent (test on Linux Mint, Debian, Ubuntu, Arch)

## Technology Stack
- Python 3
- Qt6 / PyQt6 (PySide6 not available in this environment)
- PipeWire
- Linux PTP (ptp4l)

## Current State
- Early development / proof-of-concept phase
- main.py is the application entry point
- PTP tab implemented with:
  * Network interface dropdown (populated via `ip link show`)
  * Settings dialog for ethtool/ip link configuration (gro, gso, tso, sg, rx-usecs, multicast)
  * START PTP button that runs configuration commands then launches `ptp4l -i $IFACE -m -l 6 -H`
  * Terminal output area displaying command output
- No build/test/lint configuration present yet

## When Adding Features
1. Follow the modular structure above
2. Keep UI separate from system logic (use services/ for system commands)
3. Implement small, testable increments
4. Refer to docs/mvp.md for planned feature order
5. For system commands, use QProcess with proper error handling
6. Store user settings with QSettings