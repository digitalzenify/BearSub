#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/opt/BearSub"
BAZARR_ROOT="/opt/bazarr"

PROVIDER_SRC="$PROJECT_ROOT/bazarr-provider/providers/bearsub.py"
PROVIDER_DST_DIR="$BAZARR_ROOT/custom_libs/subliminal_patch/providers"
PROVIDER_DST="$PROVIDER_DST_DIR/bearsub.py"

PATCH_CONFIG="$PROJECT_ROOT/bazarr-provider/patches/patch_config.py"
PATCH_GET_PROVIDERS="$PROJECT_ROOT/bazarr-provider/patches/patch_get_providers.py"
PATCH_FRONTEND="$PROJECT_ROOT/bazarr-provider/patches/patch_frontend.py"

echo
echo "========================================"
echo "   BearSub Bazarr Provider Installer"
echo "========================================"
echo

if [[ ! -d "$BAZARR_ROOT" ]]; then
    echo "ERROR: Bazarr root not found at: $BAZARR_ROOT"
    exit 1
fi

if [[ ! -f "$PROVIDER_SRC" ]]; then
    echo "ERROR: Provider source file not found:"
    echo "       $PROVIDER_SRC"
    exit 1
fi

if [[ ! -f "$PATCH_CONFIG" || ! -f "$PATCH_GET_PROVIDERS" || ! -f "$PATCH_FRONTEND" ]]; then
    echo "ERROR: One or more patch scripts are missing"
    exit 1
fi

echo "Step 1: Installing provider file"
mkdir -p "$PROVIDER_DST_DIR"
cp -f "$PROVIDER_SRC" "$PROVIDER_DST"

echo "Installed provider:"
echo "  $PROVIDER_DST"
echo

echo "Step 2: Patching Bazarr config"
python3 "$PATCH_CONFIG"
echo

echo "Step 3: Patching Bazarr get_providers"
python3 "$PATCH_GET_PROVIDERS"
echo

echo "Step 4: Patching Bazarr frontend"
python3 "$PATCH_FRONTEND"
echo

echo "Step 5: Restarting Bazarr"
systemctl restart bazarr

sleep 2

echo
echo "Step 6: Bazarr status"
systemctl status bazarr --no-pager
echo

echo "========================================"
echo " BearSub provider installation complete"
echo "========================================"
echo
echo "Next:"
echo "  1) Open Bazarr"
echo "  2) Go to Settings -> Providers"
echo "  3) Enable BearSub"
echo "  4) Set API URL to your BearSub backend (default: http://localhost:8765)"
echo "  5) Set API Key if required"
echo
