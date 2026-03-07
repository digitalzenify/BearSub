# SubsDump

Self-hosted subtitle archive and Bazarr provider powered by a Subscene dump.

## Features

- Fast subtitle search by IMDb, title, language, and release
- Direct subtitle pages
- Movie archive pages
- ZIP downloads
- Modern self-hosted web UI
- Bazarr provider integration
- Debian-friendly deployment

## Components

### Backend

FastAPI backend that provides:

- subtitle search
- best-match subtitle selection
- subtitle downloads
- movie archive pages
- direct subtitle routes
- OMDb-backed preview metadata

### Web UI

Frontend for:

- searching subtitles
- browsing movie archives
- opening direct subtitle pages
- downloading ZIP files
- sharing direct links

### Bazarr Provider

Custom Bazarr provider that integrates SubsDump as a subtitle source.

## Project Structure

- `backend/` - FastAPI backend and web UI
- `bazarr-provider/` - Bazarr provider and patch scripts
- `installer/` - installation helpers
- `docs/` - project documentation
- `examples/` - example configs and schema
- `scripts/` - helper scripts

## Quick Start

### Backend

1. Copy `.env.example` to `.env`
2. Adjust database and file paths
3. Run the backend

### Bazarr Provider

Run:

    bash /opt/SubsDump/bazarr-provider/install-bazarr-provider.sh

## Roadmap

- [x] Backend API
- [x] Web UI
- [x] Direct subtitle pages
- [x] Movie archive pages
- [x] Bazarr provider
- [x] Installer / uninstaller
- [ ] GitHub release packaging
- [ ] Dockerized production deployment
- [ ] Better release matching
- [ ] TV episode matching improvements
- [ ] Sonarr / Radarr helper tooling

## Credits

Built by [D3lphi3r](https://github.com/D3lphi3r)

Special thanks to whoever preserved and provided the subtitle dump used in this project.

Long live open-source projects.

## License

MIT

## Database Requirement for Fast Title Suggestions

SubsDump uses a helper table named `suggest_titles` for very fast IMDb/title suggestions in the frontend.

Why this exists:

- the original subtitle dump is large
- the dump is effectively static
- frontend autocomplete should be fast
- repeatedly grouping and counting rows from `all_subs` is slower than querying a prebuilt helper table

Important:

- this table is not part of the original dump
- it must be created once after importing the subtitle database
- the current `_imdb_suggest_impl` expects this table to exist

SQL file:

- `examples/create_suggest_titles.sql`

After importing your original dump, run that SQL file once to build the helper table.
