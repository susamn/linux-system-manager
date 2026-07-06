# linux-system-manager

A distro-agnostic, configuration-driven CLI system manager and package operations timeline monitor for Linux. 

## Features
- **Distro-Agnostic Architecture**: The parent layer (`sys-manager.py`) is written in Python and is completely independent of distribution-specific logic, loading menu paths and options dynamically from JSON configs.
- **Dynamic Capabilities Map**: Capabilities and menu keys (e.g. `1a`, `32`, `51`) are mapped in a distro's `menu.json` file to run native scripts or binaries.
- **Service Segregation**: Segregates standard system services and timers (Section 4) from repository-installed custom/personal services and timers (Section 5) with built-in controls (start, stop, enable, disable, logs).
- **Boot Safety Validation**: Automatically checks partition status, kernel images, and bootloader configuration before rebooting (supports automatic sudo escalation).
- **Package Timeline Logger**: Log installs, upgrades, reinstalls, and removals via native package manager hooks.
- **Universal Installer**: Setup custom systemd services and register distro package manager hooks (Pacman, APT, DNF, etc.) with a single installer script.

## Directory Structure
```
sys-manager/
├── sys-manager.py               # Main menu runner (distro-agnostic)
├── install.py                   # Service and hooks installer (distro-agnostic)
├── test_sys_manager.py          # Unit test suite
├── SKILL.md                     # Local maintainer & developer guide
├── services/                    # Custom systemd services source directory
└── distros/                     # Distro-specific configuration modules
    └── arch/
        ├── menu.json            # Capabilities menu mapping
        ├── install_hooks.sh     # Hook installer script
        └── *.sh                 # Distro native shell scripts
```

## Getting Started

### 1. Installation
To install custom systemd services and register distro-specific package manager hooks:
```bash
sudo ./install.py
```

### 2. Run the System Manager
To start the interactive CLI menu:
```bash
./sys-manager.py
```

### 3. Running Tests
To verify project integrity:
```bash
python3 test_sys_manager.py
```

## Extending to New Distros
Refer to the project maintainer guide at [SKILL.md](SKILL.md) for step-by-step instructions on adding support for new Linux distributions and modifying capabilities.

## License
Licensed under the MIT License. See [LICENSE](LICENSE) for details.
