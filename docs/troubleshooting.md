# Troubleshooting

This document covers common problems when running SubsDump or integrating it with Bazarr.

--------------------------------------------------

PROVIDER APPEARS IN BAZARR BUT RETURNS NO RESULTS

Possible cause:

The provider is sending q=<release> together with release=<filename>.

This can over-filter the results because the API treats q as an additional
database text filter.

Correct behavior:

The provider should send:

release=<video filename>

And should NOT send:

q=<release>

--------------------------------------------------

PROVIDER DOES NOT APPEAR IN BAZARR

Check if the frontend patch was applied.

Run:

grep -Rni 'key:"subsdump"' /opt/bazarr/frontend/build/assets/index-*.js

If nothing appears, run the frontend patch again:

python3 /opt/SubsDump/bazarr-provider/patches/patch_frontend.py

Then restart Bazarr.

--------------------------------------------------

BAZARR CANNOT CONNECT TO THE API

Check API URL configured in Bazarr provider settings.

Example correct value:

https://subs.d3lphi3r.com

Also verify backend is reachable:

curl https://subs.d3lphi3r.com/healthz

--------------------------------------------------

BAZARR RETURNS DOWNLOAD ERRORS

Check that subtitle ZIP files exist in the configured storage path.

Also verify file permissions allow the backend to read the files.

--------------------------------------------------

PROVIDER WORKS IN MANUAL PYTHON TEST BUT NOT IN BAZARR

Check:

1. Bazarr logs
2. API URL
3. API key
4. frontend patch status
5. provider configuration

Bazarr logs:

journalctl -u bazarr -f

--------------------------------------------------

FRONTEND DOES NOT SHOW NEW PROVIDER

Bazarr frontend is compiled into JavaScript assets.

The installer patches the compiled asset.

Verify patch:

grep -Rni 'subsdump' /opt/bazarr/frontend/build/assets/index-*.js

If missing:

run installer again.

--------------------------------------------------

API RETURNS RESULTS BUT BAZARR DOES NOT DOWNLOAD

Check that download URLs returned by the API are reachable.

Example:

/api/v1/subtitles/{id}/download

Test manually with curl.

--------------------------------------------------

CHECK BACKEND LOGS

If the backend is running as a systemd service:

journalctl -u subsdump -f

If running manually:

watch the FastAPI console logs.

--------------------------------------------------

CHECK BAZARR PROVIDER FILE

Verify provider exists:

/opt/bazarr/custom_libs/subliminal_patch/providers/subsdump.py

--------------------------------------------------

GENERAL DEBUGGING STEPS

1. Confirm API is reachable
2. Confirm provider installed
3. Confirm Bazarr restarted
4. Confirm frontend patched
5. Confirm subtitle database contains entries
