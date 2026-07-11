#!/bin/bash
set -euo pipefail

RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

action=""
if [[ $# -gt 0 ]]; then
    action="$1"
fi

case "$action" in
    --active)
        echo -e "${CYAN}Currently running services:${NC}"
        echo ""
        systemctl list-units --type=service --state=running --no-pager | head -30
        echo ""
        echo -e "${BLUE}Showing first 30 services. Use 'systemctl list-units --type=service' for complete list.${NC}"
        ;;
    --failed)
        failed=$(systemctl list-units --type=service --state=failed --no-pager)
        if echo "$failed" | grep -q "0 loaded units listed"; then
            echo -e "${GREEN}✓ No failed services!${NC}"
        else
            echo -e "${RED}Failed service units:${NC}"
            echo ""
            echo "$failed"
        fi
        ;;
    --timers)
        echo -e "${CYAN}Active systemd timers:${NC}"
        echo ""
        systemctl list-timers --all --no-pager
        ;;
    --cron)
        echo -e "${CYAN}System crontab (/etc/crontab):${NC}"
        echo ""
        if [[ -f /etc/crontab ]]; then
            cat /etc/crontab | grep -v "^#" | grep -v "^$" || echo "  No entries"
        else
            echo "  Not found"
        fi

        echo ""
        echo -e "${CYAN}User crontab ($USER):${NC}"
        echo ""
        crontab -l 2>/dev/null || echo "  No crontab for $USER"

        echo ""
        echo -e "${CYAN}System cron directories:${NC}"
        echo ""
        for dir in /etc/cron.{hourly,daily,weekly,monthly}; do
            if [[ -d "$dir" ]]; then
                count=$(ls -1 "$dir" 2>/dev/null | wc -l)
                echo -e "  ${BLUE}$dir${NC}: $count scripts"
            fi
        done
        ;;
    --user-scripts)
        echo -e "${CYAN}Custom scripts in /usr/local/bin:${NC}"
        echo ""
        if [[ -d /usr/local/bin ]]; then
            ls -lh /usr/local/bin | grep -E "arch-.*\.sh$" || echo "  No arch-*.sh scripts found"
        fi

        echo ""
        echo -e "${CYAN}Scripts in ~/bin or ~/.local/bin:${NC}"
        echo ""
        for dir in ~/bin ~/.local/bin; do
            if [[ -d "$dir" ]]; then
                echo -e "${BLUE}$dir:${NC}"
                ls -1 "$dir" | head -10
                echo ""
            fi
        done
        ;;
    --enabled)
        echo -e "${CYAN}Services enabled at boot:${NC}"
        echo ""
        systemctl list-unit-files --type=service --state=enabled --no-pager | head -30
        echo ""
        echo -e "${BLUE}Showing first 30 enabled services.${NC}"
        ;;
    --recent-changes)
        echo -e "${CYAN}Recently modified systemd units:${NC}"
        echo ""
        find /etc/systemd/system /usr/lib/systemd/system -type f -name "*.service" -mtime -30 2>/dev/null | while read -r file; do
            mtime=$(stat -c %y "$file" | cut -d'.' -f1)
            echo -e "  ${YELLOW}$mtime${NC}  $(basename "$file")"
        done | head -20
        ;;
    --active-personal)
        echo -e "${CYAN}Personal Services & Timers Status:${NC}"
        echo ""
        for file in ../../services/*.{service,timer}; do
            [[ -f "$file" ]] || continue
            name=$(basename "$file")
            if [[ "$name" == *@.service || "$name" == *@.timer ]]; then
                template_base="${name%.*}"
                instances=()
                while read -r inst; do
                    if [[ -n "$inst" && "$inst" != "$name" ]]; then
                        instances+=("$inst")
                    fi
                done < <(systemctl list-units --all --no-legend --no-pager "${template_base}*" 2>/dev/null | awk '{print $1}' || true)
                
                if [[ ${#instances[@]} -gt 0 ]]; then
                    for inst in "${instances[@]}"; do
                        state=$(systemctl is-active "$inst" 2>/dev/null || echo "inactive")
                        if [[ "$state" == "active" ]]; then
                            echo -e "  ${GREEN}●${NC} $inst (${GREEN}active/running${NC})"
                        else
                            echo -e "  ${RED}○${NC} $inst (${RED}inactive/stopped${NC})"
                        fi
                    done
                else
                    echo -e "  ${BLUE}ℹ${NC} $name (No active instances)"
                fi
            else
                state=$(systemctl is-active "$name" 2>/dev/null || echo "inactive")
                if [[ "$state" == "active" ]]; then
                    echo -e "  ${GREEN}●${NC} $name (${GREEN}active/running${NC})"
                else
                    echo -e "  ${RED}○${NC} $name (${RED}inactive/stopped${NC})"
                fi
            fi
        done
        ;;
    --failed-personal)
        echo -e "${CYAN}Failed Personal Services & Timers Check:${NC}"
        echo ""
        failed_count=0
        for file in ../../services/*.{service,timer}; do
            [[ -f "$file" ]] || continue
            name=$(basename "$file")
            if [[ "$name" == *@.service || "$name" == *@.timer ]]; then
                template_base="${name%.*}"
                while read -r inst; do
                    if [[ -n "$inst" && "$inst" != "$name" ]]; then
                        state=$(systemctl show -p ActiveState --value "$inst" 2>/dev/null || echo "")
                        substate=$(systemctl show -p SubState --value "$inst" 2>/dev/null || echo "")
                        if [[ "$state" == "failed" ]] || [[ "$substate" == "failed" ]]; then
                            echo -e "  ${RED}✗ $inst is failed${NC}"
                            systemctl status "$inst" --no-pager | sed 's/^/    /'
                            echo ""
                            ((failed_count++))
                        fi
                    fi
                done < <(systemctl list-units --all --no-legend --no-pager "${template_base}*" 2>/dev/null | awk '{print $1}' || true)
            else
                state=$(systemctl show -p ActiveState --value "$name" 2>/dev/null || echo "")
                substate=$(systemctl show -p SubState --value "$name" 2>/dev/null || echo "")
                if [[ "$state" == "failed" ]] || [[ "$substate" == "failed" ]]; then
                    echo -e "  ${RED}✗ $name is failed${NC}"
                    systemctl status "$name" --no-pager | sed 's/^/    /'
                    echo ""
                    ((failed_count++))
                fi
            fi
        done
        if [[ $failed_count -eq 0 ]]; then
            echo -e "${GREEN}✓ No failed personal services/timers!${NC}"
        fi
        ;;
    --manage-personal)
        echo -e "${CYAN}Manage Personal Services & Timers:${NC}"
        echo ""
        units=()
        for file in ../../services/*.{service,timer}; do
            [[ -f "$file" ]] || continue
            units+=($(basename "$file"))
        done

        if [[ ${#units[@]} -eq 0 ]]; then
            echo "No personal services/timers found."
            exit 0
        fi

        echo "Select a personal unit to manage:"
        echo ""
        i=1
        for unit in "${units[@]}"; do
            echo -e "  ${GREEN}$i${NC}) $unit"
            ((i++))
        done
        echo -e "  ${RED}0${NC}) Cancel"
        echo ""
        read -p "Select unit (1-$((i-1))): " choice
        
        if [[ ! "$choice" =~ ^[0-9]+$ ]] || [[ "$choice" -lt 1 ]] || [[ "$choice" -ge "$i" ]]; then
            echo "Cancelled or invalid selection."
            exit 0
        fi
        
        selected_unit="${units[$((choice-1))]}"
        echo ""
        
        # If template, resolve instance
        if [[ "$selected_unit" == *@.service || "$selected_unit" == *@.timer ]]; then
            template_base="${selected_unit%.*}"
            echo "Scanning for instantiated units of $selected_unit..."
            
            # Find active or configured instances
            instances=()
            while read -r line; do
                if [[ -n "$line" ]]; then
                    instances+=("$line")
                fi
            done < <(systemctl list-units --all --no-legend --no-pager "${template_base}*" 2>/dev/null | awk '{print $1}' || true)
            
            # Check enabled/disabled ones too
            while read -r line; do
                if [[ -n "$line" && "$line" == *.* ]]; then
                    exists=false
                    for inst in "${instances[@]:-}"; do
                        if [[ "$inst" == "$line" ]]; then
                            exists=true
                            break
                        fi
                    done
                    if [[ "$exists" = false ]]; then
                        instances+=("$line")
                    fi
                fi
            done < <(systemctl list-unit-files --no-legend --no-pager "${template_base}*" 2>/dev/null | awk '{print $1}' || true)

            # Filter base template
            filtered_instances=()
            for inst in "${instances[@]:-}"; do
                if [[ "$inst" != "$selected_unit" && "$inst" != "${template_base}.service" && "$inst" != "${template_base}.timer" ]]; then
                    filtered_instances+=("$inst")
                fi
            done
            
            if [[ ${#filtered_instances[@]} -eq 0 ]]; then
                echo -e "${YELLOW}No instances of $selected_unit are currently configured or running on the system.${NC}"
                echo -e "You can configure them from Section 6 (Cloud Sync Management)."
                exit 0
            fi
            
            echo "Select an instance to manage:"
            inst_idx=1
            for inst in "${filtered_instances[@]}"; do
                echo -e "  ${GREEN}$inst_idx${NC}) $inst"
                ((inst_idx++))
            done
            echo -e "  ${RED}0${NC}) Cancel"
            echo ""
            read -p "Select instance (1-$((inst_idx-1))): " inst_choice
            if [[ ! "$inst_choice" =~ ^[0-9]+$ ]] || [[ "$inst_choice" -lt 1 ]] || [[ "$inst_choice" -ge "$inst_idx" ]]; then
                echo "Cancelled."
                exit 0
            fi
            selected_unit="${filtered_instances[$((inst_choice-1))]}"
            echo ""
        fi

        echo -e "Selected unit: ${CYAN}$selected_unit${NC}"
        echo "1) Start & Enable"
        echo "2) Stop & Disable"
        echo "3) View status logs"
        read -p "Select action: " act
        
        case "$act" in
            1)
                echo "Enabling and starting $selected_unit..."
                sudo systemctl enable --now "$selected_unit"
                ;;
            2)
                echo "Stopping and disabling $selected_unit..."
                sudo systemctl disable --now "$selected_unit"
                ;;
            3)
                echo ""
                systemctl status "$selected_unit" --no-pager
                ;;
            *)
                echo "Invalid action."
                ;;
        esac
        ;;
    *)
        echo -e "${RED}Unknown action: $action${NC}"
        exit 1
        ;;
esac
