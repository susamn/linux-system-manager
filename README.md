# linux-system-manager

A distro-agnostic, configuration-driven CLI system manager and package operations timeline monitor for Linux. 

## Features
- **Distro-Agnostic Architecture**: The parent layer (`linux-system-manager.sh`) is written in Python and is completely independent of distribution-specific logic, loading menu paths and options dynamically from JSON configs.
- **Dynamic Capabilities Map**: Capabilities and menu keys (e.g. `1a`, `32`, `51`) are mapped in a distro's `menu.json` file to run native scripts or binaries.
- **Service Segregation**: Segregates standard system services and timers (Section 4) from repository-installed custom/personal services and timers (Section 5) with built-in controls (start, stop, enable, disable, logs).
- **Boot Safety Validation**: Automatically checks partition status, kernel images, and bootloader configuration before rebooting (supports automatic sudo escalation).
- **Package Timeline Logger**: Log installs, upgrades, reinstalls, and removals via native package manager hooks.
- **Universal Installer**: Setup custom systemd services and register distro package manager hooks (Pacman, APT, DNF, etc.) with a single installer script.

## Directory Structure
```
linux-system-manager/
├── linux-system-manager.sh      # Main menu runner (distro-agnostic)
├── install.py                   # Service and hooks installer (distro-agnostic)
├── test_*.py                    # Unit, contract, and regression suites
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
./linux-system-manager.sh
```

### 3. Running Tests
To run the full suite:
```bash
python3 -m unittest discover -s . -p 'test_*.py' -v
```

| Suite | Covers |
|---|---|
| `test_sys_manager.py` | Distro detection, menu loading/rendering, action dispatch, installer |
| `test_menu_config.py` | Every `menu.json`: schema, unique action codes, and that each `exec` resolves |
| `test_regressions.py` | Bugs that actually shipped — each verified to fail against the pre-fix code |

Shell scripts are linted separately in CI. To reproduce locally:
```bash
shellcheck --severity=warning --exclude=SC2155 distros/*/*.sh services/*.sh
```

## Extending to New Distros
Refer to the project maintainer guide at [SKILL.md](SKILL.md) for step-by-step instructions on adding support for new Linux distributions and modifying capabilities.

## License
Licensed under the MIT License. See [LICENSE](LICENSE) for details.
