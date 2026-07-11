#!/bin/bash
# Runner script for rclone-mount systemd service template.
# Reads configuration from $HOME/.config/rclone-sync-profiles/<profile>.conf.

set -euo pipefail

PROFILE="$1"
CONF_FILE="$HOME/.config/rclone-sync-profiles/${PROFILE}.conf"

if [[ ! -f "$CONF_FILE" ]]; then
    echo "Error: Configuration file $CONF_FILE not found." >&2
    exit 1
fi

# Load configuration
REMOTE=""
REMOTE_PATH=""
LOCAL_PATH=""
SYNC_TYPE=""
RCLONE_CONFIG=""
RCLONE_OPTS=""

# Source the configuration file
# shellcheck disable=SC1090
source "$CONF_FILE"

# Validation
if [[ -z "$REMOTE" || -z "$LOCAL_PATH" || -z "$SYNC_TYPE" ]]; then
    echo "Error: Missing required variables in $CONF_FILE." >&2
    echo "Required: REMOTE, LOCAL_PATH, SYNC_TYPE" >&2
    exit 1
fi

# Resolve default config path if not set
if [[ -z "$RCLONE_CONFIG" ]]; then
    RCLONE_CONFIG="$HOME/.config/rclone/rclone.conf"
fi

# Ensure local mount point directory exists
mkdir -p "$LOCAL_PATH"

echo "=== Rclone Mount Profile: $PROFILE ==="
echo "Local Path: $LOCAL_PATH"
echo "Remote: $REMOTE:$REMOTE_PATH"
echo "======================================"

# Run rclone mount
# We use exec so rclone replaces this shell process and receives systemd signals directly
exec rclone mount "$REMOTE:$REMOTE_PATH" "$LOCAL_PATH" \
    --config "$RCLONE_CONFIG" \
    --vfs-cache-mode writes \
    --vfs-cache-max-age 24h \
    --vfs-read-chunk-size 16M \
    $RCLONE_OPTS
