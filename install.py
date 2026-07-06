#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess

# --- Colors ---
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
GREEN = '\033[0;32m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def check_root():
    if os.geteuid() != 0:
        print(f"{YELLOW}This installation script requires root privileges to install systemd services and pacman hooks.{NC}")
        print(f"Re-running with sudo...")
        try:
            # Re-execute the script with sudo
            os.execvp('sudo', ['sudo', sys.executable] + sys.argv)
        except Exception as e:
            print(f"{RED}Failed to elevate privileges: {e}{NC}")
            sys.exit(1)

def detect_distro():
    if not os.path.exists('/etc/os-release'):
        print(f"{RED}Error: /etc/os-release not found. Cannot determine distro.{NC}")
        sys.exit(1)
        
    info = {}
    with open('/etc/os-release') as f:
        for line in f:
            if '=' in line:
                k, v = line.strip().split('=', 1)
                info[k] = v.strip('"')
                
    distro_id = info.get('ID')
    if distro_id and os.path.isdir(os.path.join(SCRIPT_DIR, 'distros', distro_id)):
        return distro_id, info.get('NAME', distro_id)
        
    for like in info.get('ID_LIKE', '').split():
        if os.path.isdir(os.path.join(SCRIPT_DIR, 'distros', like)):
            return like, info.get('NAME', like)
            
    return None, info.get('NAME', 'Unknown')

def install_systemd_services():
    services_src_dir = os.path.join(SCRIPT_DIR, 'services')
    dest_dir = '/etc/systemd/system'
    
    if not os.path.isdir(services_src_dir):
        print(f"{YELLOW}ℹ No 'services' directory found. Skipping systemd service installation.{NC}")
        return
        
    service_files = [f for f in os.listdir(services_src_dir) if f.endswith('.service') or f.endswith('.timer')]
    
    if not service_files:
        print(f"{YELLOW}ℹ No systemd services or timers found in {services_src_dir}.{NC}")
        return
        
    print(f"{BLUE}⚙ Installing custom systemd services & timers...{NC}")
    for file in service_files:
        src_path = os.path.join(services_src_dir, file)
        dest_path = os.path.join(dest_dir, file)
        
        try:
            shutil.copy2(src_path, dest_path)
            # Ensure permissions are correct (644 for systemd services)
            os.chmod(dest_path, 0o644)
            print(f"  {GREEN}✓ Installed: {file} → {dest_path}{NC}")
        except Exception as e:
            print(f"  {RED}✗ Failed to install {file}: {e}{NC}")
            
    print(f"  {BLUE}Reloading systemd daemon...{NC}")
    try:
        subprocess.run(['systemctl', 'daemon-reload'], check=True)
        print(f"  {GREEN}✓ Systemd daemon reloaded successfully.{NC}")
    except Exception as e:
        print(f"  {RED}✗ Failed to reload systemd: {e}{NC}")

def run_distro_installer(distro_id):
    distro_install_script = os.path.join(SCRIPT_DIR, 'distros', distro_id, 'install_hooks.sh')
    
    if not os.path.exists(distro_install_script):
        print(f"{YELLOW}ℹ No hook installer script found for {distro_id} at {distro_install_script}.{NC}")
        return
        
    print(f"{BLUE}⚙ Executing distro-specific hooks installer ({distro_id})...{NC}")
    
    # Ensure it's executable
    if not os.access(distro_install_script, os.X_OK):
        os.chmod(distro_install_script, 0o755)
        
    try:
        result = subprocess.run([distro_install_script], cwd=os.path.dirname(distro_install_script))
        if result.returncode == 0:
            print(f"  {GREEN}✓ Distro-specific installer finished successfully.{NC}")
        else:
            print(f"  {RED}✗ Distro-specific installer failed with code: {result.returncode}{NC}")
    except Exception as e:
        print(f"  {RED}✗ Failed to execute distro installer: {e}{NC}")

def main():
    print(f"{CYAN}╔════════════════════════════════════════════════╗{NC}")
    print(f"{CYAN}║     sys-manager Global Installation Setup      ║{NC}")
    print(f"{CYAN}╚════════════════════════════════════════════════╝{NC}")
    print()
    
    check_root()
    
    distro_id, distro_name = detect_distro()
    if not distro_id:
        print(f"{RED}Error: Distro '{distro_name}' is not supported yet.{NC}")
        print(f"Aborting installation.")
        sys.exit(1)
        
    print(f"{BLUE}Detected Distribution:{NC} {GREEN}{distro_name} ({distro_id}){NC}")
    print()
    
    install_systemd_services()
    print()
    
    run_distro_installer(distro_id)
    print()
    
    print(f"{GREEN}✓ Global Installation Sequence Completed.{NC}")
    print(f"You can now run system manager with: python3 {os.path.join(SCRIPT_DIR, 'sys-manager.py')}")

if __name__ == '__main__':
    main()
