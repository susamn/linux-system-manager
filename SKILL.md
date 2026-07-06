---
name: linux-system-manager-maintainer
description: Maintain, enhance, and extend the system-agnostic linux-system-manager toolset. Use this skill when adding new features, modifying distro menus, replicating functionality across all distros, managing systemd services, or running tests.
version: 1.1.0
triggers:
  - "how to add a new feature to linux-system-manager"
  - "add distro-agnostic capability"
  - "replicate functionality to all distros"
  - "manage linux-system-manager project"
intent: system
config_dir: ./config
created_at: 2026-07-06
updated_at: 2026-07-06
---

# Linux-System-Manager Project Maintainer & Developer Guide

This local skill governs the design, maintenance, and expansion of the `linux-system-manager` project.

---

## 1. Project Philosophy & Core Architecture

The `linux-system-manager` toolset is a **stateless, configuration-driven system management pipeline**. It is designed around complete isolation between presentation and implementation:

- **Parent Orchestrator (`linux-system-manager.sh`):** Distro-blind. Handles terminal clearance, interactive menus, OS detection (`/etc/os-release`), dynamic JSON menu parsing, and process execution context.
- **Distribution Modules (`distros/<distro_id>/`):** Self-contained. Declare their capabilities in `menu.json` and implement execution logic in distro-native scripts/binaries.
- **Privilege Boundary:** The parent orchestrator and main menu run as a regular user. Distro-specific scripts must call `sudo` internally if they perform privileged actions (like checking systemd configs or writing backups).

---

## 2. Directory Layout Reference

```
linux-system-manager/
├── linux-system-manager.sh      # Main menu runner (distro-agnostic)
├── install.py                   # Service and hooks installer (distro-agnostic)
├── test_sys_manager.py          # Unit test suite
├── SKILL.md                     # Local maintainer & developer guide
├── services/                    # Custom systemd services source directory
│   └── sys-manager-cleanup.service
├── distros/                     # Distro-specific logic folders
│   ├── arch/
│   │   ├── menu.json            # Capabilities menu mapping
│   │   ├── install_hooks.sh     # Hooks copy script
│   │   └── *.sh                 # Inspection & management scripts
│   └── <new-distro>/
│       ├── menu.json
│       ├── install_hooks.sh
│       └── ...
└── SKILL.md                     # This maintainer guide
```

---

## 3. Workflow: Replicating a New Feature Across All Distros

To add a new option or section (e.g., "Disk Space Analyzer" or "Logs Monitor") and make it available across all supported distributions, use this sequence:

### Step 1: Scan for Available Distributions
Run a command or inspect the file system to list directories in `distros/`:
```bash
ls -d distros/*/ | grep -v "common/"
```

### Step 2: Update `menu.json` in Each Distro Directory
Under each directory found (e.g. `distros/arch/`, `distros/debian/`), edit `menu.json` to insert the new option under the correct section.
- **Example:**
```json
{
  "key": "8",
  "label": "Disk Space Analysis",
  "exec": "analyze_disk.sh"
}
```

### Step 3: Implement the Distro-Specific Execution Scripts
Write the script for each distro.
- In `distros/arch/analyze_disk.sh`, you might use `pacman` cache size analysis combined with standard `df` commands.
- In `distros/debian/analyze_disk.sh`, you might use `apt` clean/cache checks.
*Ensure all scripts are made executable:*
```bash
chmod +x distros/*/analyze_disk.sh
```

## 4. Workflow: Adding & Managing Custom (Personal) Systemd Services

To deploy and manage custom background utility services (e.g., a backup cleanup timer or sync daemon) and segregate them from standard system services:

1. **Place unit files in `services/`**: Write the service or timer unit files under the `services/` directory (e.g., `services/sys-manager-cleanup.service` and `services/sys-manager-cleanup.timer`).
2. **Installation**: Run `install.py` (which escalates via `sudo` automatically). The installer copies all `services/*.{service,timer}` files to `/etc/systemd/system/` and runs `systemctl daemon-reload`.
3. **Menu Segregation**:
   - Standard system services are monitored and inspected under **Section 4 (Services & Scripts)**.
   - Local/personal services from this repository are segregated and monitored under **Section 5 (Personal Services & Timers)**.
   - Distro-specific logic (e.g. `services_scripts.sh`) dynamically detects these services by scanning the `services/` directory in the repository relative to its runtime path, and checks their status, failures, and toggling states via `systemctl`.

---

## 5. Workflow: Hook Registration & Package Triggers

When package operations occur, native hook systems should notify our scripts:
- **Arch Linux:** `install_hooks.sh` copies hooks under `distros/arch/hooks/` to `/etc/pacman.d/hooks/`.
- **Debian/Ubuntu (APT):** Create `distros/debian/hooks/` and write an APT configuration trigger file (e.g., `99sysmanager`) to be copied to `/etc/apt/apt.conf.d/` by `install_hooks.sh`.
- **Fedora/RHEL (DNF):** Write a DNF plugin or trigger command inside the Fedora hooks section.

---

## 6. Testing & Quality Gate

Every change to the orchestrator or installer script **MUST** be verified by running the unit test suite:
```bash
python3 test_sys_manager.py
```

### Writing New Tests
If you modify `linux-system-manager.sh` or `install.py`:
1. Open `test_sys_manager.py`.
2. Add a new test method to `TestSysManager` or `TestInstaller` utilizing standard `unittest.mock` strategies (patching filesystem, process executions, and environment inputs).
3. Confirm all tests pass locally and in the GitHub Actions runner environment before committing changes.

---

## 7. Developer Guardrails
- **Zero Third-Party Packages:** Never import packages outside the Python standard library in `linux-system-manager.sh`, `install.py`, or `test_sys_manager.py`.
- **Stateless Operation:** Never write user settings or operation logs inside the project source tree. Use `~/.local/state/` or `/var/log/` for distro logs.
- **Fail Gracefully:** Never allow python `subprocess` exceptions to crash the main menu loop. Always catch execution failures and log them to standard error.
