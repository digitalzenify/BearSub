#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/opt/SubsDump"
BAZARR_ROOT="/opt/bazarr"
PROVIDER_SRC="$PROJECT_ROOT/bazarr-provider/providers/subsdump.py"
PATCHES_DIR="$PROJECT_ROOT/bazarr-provider/patches"
PROVIDER_DST_DIR="$BAZARR_ROOT/custom_libs/subliminal_patch/providers"
PROVIDER_DST="$PROVIDER_DST_DIR/subsdump.py"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

echo "==> SubsDump Bazarr provider installer"
echo "==> Project root: $PROJECT_ROOT"
echo "==> Bazarr root:  $BAZARR_ROOT"

if [[ ! -d "$BAZARR_ROOT" ]]; then
  echo "ERROR: Bazarr root not found at $BAZARR_ROOT"
  exit 1
fi

if [[ ! -f "$PROVIDER_SRC" ]]; then
  echo "ERROR: Provider source file not found: $PROVIDER_SRC"
  exit 1
fi

mkdir -p "$PROVIDER_DST_DIR"

echo "==> Creating backups"
cp -a "$BAZARR_ROOT/custom_libs/subliminal_patch/providers/__init__.py" \
      "$BAZARR_ROOT/custom_libs/subliminal_patch/providers/__init__.py.bak.subsdump.$TIMESTAMP"

cp -a "$BAZARR_ROOT/bazarr/app/config.py" \
      "$BAZARR_ROOT/bazarr/app/config.py.bak.subsdump.$TIMESTAMP"

cp -a "$BAZARR_ROOT/bazarr/app/get_providers.py" \
      "$BAZARR_ROOT/bazarr/app/get_providers.py.bak.subsdump.$TIMESTAMP"

echo "==> Installing provider"
cp -f "$PROVIDER_SRC" "$PROVIDER_DST"

echo "==> Provider copied to:"
echo "    $PROVIDER_DST"

echo "==> Patch scripts available in:"
echo "    $PATCHES_DIR"

echo
echo "Next steps:"
echo "  1) Run patch_config.py"
echo "  2) Run patch_get_providers.py"
echo "  3) Run patch_frontend.py"
echo "  4) Restart Bazarr"
echo
echo "Example:"
echo "  python3 $PATCHES_DIR/patch_config.py"
echo "  python3 $PATCHES_DIR/patch_get_providers.py"
echo "  python3 $PATCHES_DIR/patch_frontend.py"
echo "  systemctl restart bazarr"
