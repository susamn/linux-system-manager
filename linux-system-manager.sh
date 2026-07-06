#!/usr/bin/env python3
import os
import sys
import json
import subprocess

# --- Colors ---
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
GREEN = '\033[0;32m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
MAGENTA = '\033[0;35m'
NC = '\033[0m'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def clear_screen():
    os.system('clear')

def print_header(title):
    print(f"{CYAN}╔══════════════════════════════════════════════════════════════╗{NC}")
    print(f"{CYAN}║                                                              ║{NC}")
    # Center the title in the header block
    padding = (60 - len(title)) // 2
    extra = (60 - len(title)) % 2
    print(f"{CYAN}║{' ' * padding}{MAGENTA}{title}{CYAN}{' ' * (padding + extra)}║{NC}")
    print(f"{CYAN}║                                                              ║{NC}")
    print(f"{CYAN}╚══════════════════════════════════════════════════════════════╝{NC}")
    print()

def print_section_header(title):
    clear_screen()
    print_header(title)

def pause():
    print()
    input("Press ENTER to continue...")

def detect_distro():
    if not os.path.exists('/etc/os-release'):
        raise FileNotFoundError("Could not find /etc/os-release to detect distro.")
        
    info = {}
    with open('/etc/os-release') as f:
        for line in f:
            if '=' in line:
                k, v = line.strip().split('=', 1)
                info[k] = v.strip('"')
                
    distro_id = info.get('ID')
    # Try ID first
    if distro_id and os.path.isdir(os.path.join(SCRIPT_DIR, 'distros', distro_id)):
        return distro_id, info.get('NAME', distro_id)
        
    # Try ID_LIKE fallbacks
    for like in info.get('ID_LIKE', '').split():
        if os.path.isdir(os.path.join(SCRIPT_DIR, 'distros', like)):
            return like, info.get('NAME', like)
            
    return None, info.get('NAME', 'Unknown')

def load_menu(distro_id):
    menu_path = os.path.join(SCRIPT_DIR, 'distros', distro_id, 'menu.json')
    if not os.path.exists(menu_path):
        raise FileNotFoundError(f"Menu capabilities file not found at {menu_path}")
        
    with open(menu_path) as f:
        return json.load(f)

def render_menu(menu_data, distro_name):
    clear_screen()
    print_header(f"{distro_name} System Manager")
    
    sections = menu_data.get("sections", [])
    
    # Store flat mapping for quick action triggers: e.g. "1a" -> item dict
    action_map = {}
    
    for section in sections:
        sec_id = section.get("id")
        sec_title = section.get("title")
        print(f"{GREEN}{sec_id}{NC})   {BLUE}⚙️  {sec_title}{NC}")
        
        items = section.get("items", [])
        for item in items:
            key = item.get("key")
            label = item.get("label")
            action_code = f"{sec_id}{key}"
            action_map[action_code.lower()] = item
            print(f"      {MAGENTA}{key}{NC})  {YELLOW}{label}{NC}")
        print()
        
    print(f"{RED}0{NC})   Exit")
    print()
    return action_map

def run_action(distro_id, item):
    label = item.get("label")
    exec_file = item.get("exec")
    args = item.get("args", [])
    
    print_section_header(label)
    
    # Resolve script path
    script_path = os.path.join(SCRIPT_DIR, 'distros', distro_id, exec_file)
    if not os.path.exists(script_path):
        print(f"{RED}✗ Executable script not found: {script_path}{NC}")
        pause()
        return
        
    # Check if executable, make it executable if not
    if not os.access(script_path, os.X_OK):
        try:
            os.chmod(script_path, 0o755)
        except Exception as e:
            print(f"{YELLOW}⚠ Warning: Could not set executable permissions: {e}{NC}")
            
    print(f"{BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{NC}")
    print(f"{YELLOW}Running: {label}{NC}")
    print(f"{BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{NC}")
    print()
    
    try:
        # Run process inheriting stdin/stdout/stderr for interactive support
        result = subprocess.run([script_path] + args, cwd=os.path.join(SCRIPT_DIR, 'distros', distro_id))
        print()
        if result.returncode == 0:
            print(f"{GREEN}✓ Completed successfully{NC}")
        else:
            print(f"{RED}✗ Command exited with code: {result.returncode}{NC}")
    except Exception as e:
        print(f"{RED}✗ Execution failed: {e}{NC}")
        
    pause()

def main():
    try:
        distro_id, distro_name = detect_distro()
        if not distro_id:
            print(f"{RED}Error: Distro '{distro_name}' is not supported yet.{NC}")
            print(f"To add support, refer to the distro-manager skill under:")
            print(f"  sys-manager/SKILL.md")
            sys.exit(1)
            
        menu_data = load_menu(distro_id)
        
        while True:
            action_map = render_menu(menu_data, distro_name)
            choice = input(f"{CYAN}Select option (e.g., 1a, 21, 0):{NC} ").strip().lower()
            
            if choice == '0':
                print()
                print(f"{GREEN}Goodbye!{NC}")
                print()
                break
                
            if choice in action_map:
                run_action(distro_id, action_map[choice])
            else:
                print(f"{RED}Invalid option. Please try again.{NC}")
                subprocess.run(["sleep", "1"])
                
    except KeyboardInterrupt:
        print(f"\n{GREEN}Goodbye!{NC}\n")
        sys.exit(0)
    except Exception as e:
        print(f"{RED}Error starting System Manager: {e}{NC}")
        sys.exit(1)

if __name__ == '__main__':
    main()
