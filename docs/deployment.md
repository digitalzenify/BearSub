# Deployment

This document describes the minimum deployment steps for SubsDump.

--------------------------------------------------

REQUIREMENTS

- Debian-based system
- MariaDB or MySQL
- subtitle dump imported into database `subscene_db`
- subtitle ZIP files available on disk
- Python 3
- Nginx optional but recommended
- Bazarr optional if provider integration is needed

--------------------------------------------------

STEP 1: IMPORT THE ORIGINAL SUBTITLE DUMP

Import your original dump into:

subscene_db

Main table expected by SubsDump:

all_subs

--------------------------------------------------

STEP 2: BUILD THE SUGGEST TITLES HELPER TABLE

SubsDump frontend title suggestions depend on a helper table:

suggest_titles

This table is not part of the original dump.

It must be created once after importing the database.

Why this is needed:

- the original dump is large
- the dump content is mostly static
- frontend IMDb/title suggestions should be very fast
- precomputing grouped title data is much faster than scanning all_subs for every suggestion query

Run:

mysql -u root -p subscene_db < /opt/SubsDump/examples/create_suggest_titles.sql

If your API user already has SELECT on subscene_db.*, no extra privilege changes are required.

If not, you may grant SELECT on this helper table only.

--------------------------------------------------

STEP 3: CONFIGURE ENVIRONMENT

Copy:

.env.example

to:

.env

Then set at least:

- DB_HOST
- DB_PORT
- DB_NAME
- DB_USER
- DB_PASS
- FILES_BASE
- API_KEY
- OMDB_API_KEY_DEF
- FORCE_ENTER_KEYS

--------------------------------------------------

STEP 4: RUN THE BACKEND

Example development run:

bash /opt/SubsDump/scripts/dev-run-backend.sh

Or use your preferred systemd / container deployment.

--------------------------------------------------

STEP 5: OPTIONAL NGINX REVERSE PROXY

A sample Nginx configuration is included in:

backend/nginx/subs.d3lphi3r.com.conf

--------------------------------------------------

STEP 6: OPTIONAL BAZARR INTEGRATION

Install the provider:

bash /opt/SubsDump/bazarr-provider/install-bazarr-provider.sh

Then open Bazarr and enable:

SubsDump

--------------------------------------------------

NOTES

If the frontend title suggestion feature is slow or broken, the first thing to verify is whether the suggest_titles table exists.

Example check:

mysql -u root -p -e "USE subscene_db; SHOW TABLES LIKE 'suggest_titles';"

If it does not exist, create it using:

/opt/SubsDump/examples/create_suggest_titles.sql
