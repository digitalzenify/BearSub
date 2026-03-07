# SubsDump

Self-hosted subtitle archive and Bazarr provider powered by a Subscene dump.

## Features

- Fast subtitle search by IMDb, title, language, and release
- Direct subtitle pages
- Movie archive pages
- ZIP downloads
- Self-hosted modern web UI
- Bazarr provider integration
- Simple deployment on Debian-based systems

## Components

### Backend
FastAPI backend that provides:
- subtitle search
- best-match subtitle selection
- subtitle downloads
- movie archive routes
- direct subtitle pages
- OMDb-powered preview metadata

### Web UI
Modern frontend for:
- searching subtitles
- browsing movie archives
- opening direct subtitle pages
- downloading ZIP files
- sharing direct links

### Bazarr Provider
Custom provider for Bazarr that integrates SubsDump as a subtitle source.

## Project Structure

- `backend/` - FastAPI backend and web UI
- `bazarr-provider/` - Bazarr provider and patch scripts
- `installer/` - installation helpers
- `docs/` - documentation
- `examples/` - example configs and schema
- `scripts/` - maintenance and testing scripts

## Quick Start

### Backend only
1. Copy `.env.example` to `.env`
2. Adjust database and file paths
3. Start the backend

### Bazarr integration
Run the provider installer script from `bazarr-provider/`.

## Status

SubsDump is under active development.

## Roadmap

- [x] Backend API
- [x] Web UI
- [x] Direct subtitle pages
- [x] Movie archive pages
- [x] Bazarr provider prototype
- [ ] Automated Bazarr installer
- [ ] Frontend patch automation
- [ ] Dockerized deployment
- [ ] GitHub release packaging
- [ ] Sonarr/Radarr helper tooling

## License

MIT License

## Credits

Built by [D3lphi3r](https://github.com/D3lphi3r)

Special thanks to whoever preserved and provided the subtitle dump used by this project.

Long live open-source projects.
