# SubsDump Bazarr Provider

Custom Bazarr provider for SubsDump.

## Features

- IMDb-based subtitle search
- Release-aware subtitle matching
- Direct ZIP subtitle downloads
- Self-hosted API support
- Bazarr UI integration via patching

## Requirements

- Bazarr installed at `/opt/bazarr`
- Python 3 available
- Systemd-based Bazarr service (`bazarr.service`)

## Files

- `providers/subsdump.py` - provider implementation
- `patches/patch_config.py` - adds Bazarr config validators
- `patches/patch_get_providers.py` - adds auth/config wiring
- `patches/patch_frontend.py` - adds SubsDump to Bazarr provider UI
- `install-bazarr-provider.sh` - install helper
- `uninstall-bazarr-provider.sh` - uninstall helper

## Install

Run:

    bash /opt/SubsDump/bazarr-provider/install-bazarr-provider.sh

Then open Bazarr:

- Settings
- Providers
- Enable `SubsDump`

Set:

- API URL: `https://subs.d3lphi3r.com`
- API Key: optional

## Uninstall

Run:

    bash /opt/SubsDump/bazarr-provider/uninstall-bazarr-provider.sh

## Notes

- The provider sends `release` to the SubsDump API for scoring and matching.
- The provider intentionally does not send `q=release`, because that can over-filter valid results.
- The Bazarr UI entry is patched into the compiled frontend asset.

## Status

Working prototype.
