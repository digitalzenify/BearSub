# SubsDump Bazarr Provider

Custom Bazarr provider for SubsDump.

## What it does

- Adds SubsDump as a subtitle provider inside Bazarr
- Uses the SubsDump API for search and download
- Supports IMDb-based lookups
- Supports release-aware subtitle matching

## Files

- `providers/subsdump.py` - provider implementation
- `patches/patch_config.py` - adds Bazarr config validators
- `patches/patch_get_providers.py` - adds provider auth/config wiring
- `patches/patch_frontend.py` - adds SubsDump to Bazarr provider UI
- `install-bazarr-provider.sh` - installer helper
- `uninstall-bazarr-provider.sh` - uninstall helper

## Current status

Work in progress.
