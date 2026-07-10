#!/bin/bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

grub_cfg="/boot/grub/grub.cfg"

if [[ ! -f "$grub_cfg" ]]; then
    echo -e "${RED}✗ GRUB config not found at $grub_cfg${NC}"
    exit 1
fi

echo -e "${BLUE}━━━ GRUB Menu Entries ━━━${NC}"
echo ""

menu_entries=$(grep "^menuentry" "$grub_cfg" | sed "s/menuentry '\([^']*\)'.*/\1/")
entry_count=$(echo "$menu_entries" | wc -l)

echo -e "${GREEN}Found $entry_count menu entries:${NC}"
echo ""

counter=1
while IFS= read -r entry; do
    if echo "$entry" | grep -q "linux"; then
        echo -e "  ${GREEN}$counter.${NC} ${CYAN}$entry${NC}"
    else
        echo -e "  ${GREEN}$counter.${NC} $entry"
    fi
    ((counter++))
done <<< "$menu_entries"
