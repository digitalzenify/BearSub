# Bazarr Integration

SubsDump can be integrated into Bazarr as a custom subtitle provider.

--------------------------------------------------

OVERVIEW

The integration consists of:

- custom Bazarr provider (subsdump.py)
- Bazarr config patch
- Bazarr provider wiring patch
- Bazarr frontend patch

--------------------------------------------------

PROVIDER BEHAVIOR

The provider:

- searches by imdb id
- maps Bazarr languages to SubsDump language names
- sends release name for scoring
- downloads subtitle ZIP files

--------------------------------------------------

IMPORTANT MATCHING NOTE

The provider sends:

release=<video filename>

The provider intentionally does NOT send:

q=<release>

Reason:

Using q as the release name can over-filter results because the API treats q as an extra text search filter.

--------------------------------------------------

INSTALL

Run:

bash /opt/SubsDump/bazarr-provider/install-bazarr-provider.sh

The installer performs:

1. copy provider file
2. patch Bazarr config
3. patch get_providers
4. patch frontend assets
5. restart Bazarr

--------------------------------------------------

ENABLE IN BAZARR

After installation:

Open Bazarr

Settings -> Providers

Enable:

SubsDump

Then configure:

API URL
API Key (optional)

Example API URL:

https://subs.d3lphi3r.com

--------------------------------------------------

UNINSTALL

Run:

bash /opt/SubsDump/bazarr-provider/uninstall-bazarr-provider.sh

The uninstaller:

- removes provider
- restores Bazarr backups
- restarts Bazarr

--------------------------------------------------

FILES

Project files:

bazarr-provider/providers/subsdump.py
bazarr-provider/patches/patch_config.py
bazarr-provider/patches/patch_get_providers.py
bazarr-provider/patches/patch_frontend.py

Installer scripts:

bazarr-provider/install-bazarr-provider.sh
bazarr-provider/uninstall-bazarr-provider.sh

--------------------------------------------------

BAZARR FILES MODIFIED

During install the following Bazarr files are patched:

/opt/bazarr/custom_libs/subliminal_patch/providers/subsdump.py
/opt/bazarr/bazarr/app/config.py
/opt/bazarr/bazarr/app/get_providers.py
/opt/bazarr/frontend/build/assets/index-*.js

--------------------------------------------------

BACKUPS

Patch scripts automatically create backups.

Examples:

config.py.bak.subsdump.TIMESTAMP
get_providers.py.bak.subsdump.TIMESTAMP
index-xxxxx.js.bak.subsdump.TIMESTAMP

--------------------------------------------------

TROUBLESHOOTING

Provider appears but returns no results:

Check that the provider is NOT sending q=release.

Provider does not appear in Bazarr:

Verify patch_frontend.py executed correctly.

Check:

grep -Rni 'key:"subsdump"' /opt/bazarr/frontend/build/assets/index-*.js

Backend logs:

journalctl -u bazarr -f
