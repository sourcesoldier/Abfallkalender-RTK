#!/usr/bin/env bash
# Deploy the integration and blueprints to a mounted Home Assistant config.
# Usage: ./deploy.sh [HA_CONFIG_DIR]   (default: /Volumes/config)
set -euo pipefail

HA_CONFIG="${1:-/Volumes/config}"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ ! -d "$HA_CONFIG" ]]; then
  echo "HA config dir not found: $HA_CONFIG" >&2
  echo "Mount the HAOS Samba share or pass the path as an argument." >&2
  exit 1
fi

INTEGRATION_DST="$HA_CONFIG/custom_components/abfallkalender_rtk"
BLUEPRINT_DST="$HA_CONFIG/blueprints/automation/abfallkalender_rtk"

mkdir -p "$INTEGRATION_DST" "$BLUEPRINT_DST"

# SMB-safe rsync: no perms/owner/times and --inplace avoid metadata/temp-file
# operations that fail on Samba shares.
RSYNC_OPTS=(-rc --delete --inplace --no-perms --no-owner --no-group
  --no-times --omit-dir-times)

rsync "${RSYNC_OPTS[@]}" --exclude '__pycache__' \
  "$SRC_DIR/custom_components/abfallkalender_rtk/" "$INTEGRATION_DST/"
rsync "${RSYNC_OPTS[@]}" \
  "$SRC_DIR/blueprints/automation/abfallkalender_rtk/" "$BLUEPRINT_DST/"

echo
echo "Deployed. Restart Home Assistant to load code changes."
