#!/usr/bin/env bash
set -euo pipefail

BAZARR_ROOT="/opt/bazarr"
PROVIDER_DST="$BAZARR_ROOT/custom_libs/subliminal_patch/providers/bearsub.py"

restore_latest_backup() {
    local target="$1"
    local pattern="$2"

    local target_dir
    target_dir="$(dirname "$target")"

    local latest
    latest="$(find "$target_dir" -maxdepth 1 -type f -name "$pattern" | sort | tail -n 1 || true)"

    if [[ -n "$latest" && -f "$latest" ]]; then
        cp -f "$latest" "$target"
        echo "Restored:"
        echo "  target: $target"
        echo "  source: $latest"
    else
        echo "No backup found for:"
        echo "  $target"
    fi
}

echo
echo "========================================"
echo "   BearSub Bazarr Provider Uninstaller"
echo "========================================"
echo

if [[ ! -d "$BAZARR_ROOT" ]]; then
    echo "ERROR: Bazarr root not found at: $BAZARR_ROOT"
    exit 1
fi

echo "Step 1: Removing provider file"
if [[ -f "$PROVIDER_DST" ]]; then
    rm -f "$PROVIDER_DST"
    echo "Removed: $PROVIDER_DST"
else
    echo "Provider file not found, skipping"
fi
echo

echo "Step 2: Restoring Bazarr Python files from latest backups"
restore_latest_backup \
    "$BAZARR_ROOT/bazarr/app/config.py" \
    "config.py.bak.bearsub.*"

restore_latest_backup \
    "$BAZARR_ROOT/bazarr/app/get_providers.py" \
    "get_providers.py.bak.bearsub.*"

restore_latest_backup \
    "$BAZARR_ROOT/custom_libs/subliminal_patch/providers/__init__.py" \
    "__init__.py.bak.bearsub.*"
echo

echo "Step 3: Restoring Bazarr frontend assets from latest backups"
find "$BAZARR_ROOT/frontend/build/assets" -maxdepth 1 -type f -name 'index-*.js' | while read -r js; do
    base="$(basename "$js")"
    dir="$(dirname "$js")"
    latest="$(find "$dir" -maxdepth 1 -type f -name "${base}.bak.bearsub.*" | sort | tail -n 1 || true)"

    if [[ -n "$latest" && -f "$latest" ]]; then
        cp -f "$latest" "$js"
        echo "Restored:"
        echo "  target: $js"
        echo "  source: $latest"
    fi
done
echo

echo "Step 4: Restarting Bazarr"
systemctl restart bazarr

sleep 2

echo
echo "Step 5: Bazarr status"
systemctl status bazarr --no-pager
echo

echo "========================================"
echo " BearSub provider uninstall complete"
echo "========================================"
echo
