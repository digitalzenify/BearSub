# BearSub

**BearSub** is a self-hosted personal subtitle repository. Upload `.srt` files via the web UI or API, sync automatically from Bazarr, and serve subtitles to media players and tools like Bazarr through a clean REST API.

---

## Key Features

- **SQLite backend** – zero-config, file-based database
- **File upload API** – upload `.srt` subtitles with full metadata
- **Bazarr sync** – automatic background sync from your Bazarr history
- **Full CRUD API** – search, download, update, delete
- **Web UI** – built-in search, upload, and stats interface
- **Bazarr provider** – drop-in Bazarr subtitle provider
- **Docker-ready** – single `docker-compose up` deployment

---

## Installation (CasaOS / Docker)

### 1. Clone the repository

```bash
git clone https://github.com/BearSub/BearSub /opt/BearSub
cd /opt/BearSub
```

### 2. Configure environment

```bash
cp .env.example .env
nano .env   # edit settings as needed
```

Key settings:

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8765` | HTTP port |
| `DB_PATH` | `./data/db/subtitles.db` | SQLite database path |
| `SUBS_DIR` | `./data/subs` | Subtitle file storage |
| `API_KEY` | _(empty)_ | Optional auth key |
| `OMDB_API_KEY` | _(empty)_ | OMDb key for movie posters |
| `BAZARR_SYNC_ENABLED` | `false` | Enable Bazarr auto-sync |
| `BAZARR_URL` | `http://localhost:6767` | Bazarr address |
| `BAZARR_API_KEY` | _(empty)_ | Bazarr API key |
| `BAZARR_SYNC_INTERVAL_HOURS` | `6` | Sync interval |
| `MEDIA_ROOT_DIR` | `/media` | Media root for Bazarr paths |

### 3. Start with Docker Compose

```bash
docker-compose up -d
```

### 4. Verify

```bash
curl http://localhost:8765/healthz
# {"status":"ok"}
```

Open `http://localhost:8765` in your browser.

---

## Bazarr Provider Setup

### Install

```bash
cd /opt/BearSub
bash bazarr-provider/install-bazarr-provider.sh
```

The script copies `bearsub.py` to Bazarr's provider directory and patches the Bazarr config.

### Configure in Bazarr

1. Go to **Settings → Providers**
2. Enable **BearSub**
3. Set **API URL** to `http://localhost:8765` (or your host)
4. Set **API Key** if you configured one in `.env`
5. Save and restart Bazarr

### Uninstall

```bash
bash bazarr-provider/uninstall-bazarr-provider.sh
```

### Troubleshoot

- Check Bazarr logs: `journalctl -u bazarr -f`
- Test manually:
  ```bash
  curl "http://localhost:8765/api/v1/subtitles/search?imdb=tt0111161&lang=english"
  ```

---

## Usage Guide

### Upload via Web UI

1. Open `http://localhost:8765`
2. Scroll down to **Upload Subtitle**
3. Click **Show**, then drag-and-drop a `.srt` file
4. Fill in the metadata fields and click **Upload**

### Upload via API

```bash
curl -X POST http://localhost:8765/api/subtitles/upload \
  -F "file=@/path/to/subtitle.srt" \
  -F "imdb_id=tt0111161" \
  -F "title=The Shawshank Redemption" \
  -F "year=1994" \
  -F "language=english" \
  -F "release_name=Shawshank.1994.BluRay.x264"
```

### Search

```bash
curl "http://localhost:8765/api/v1/subtitles/search?imdb=tt0111161&lang=english"
```

### Download

```bash
curl -OJ "http://localhost:8765/api/v1/subtitles/1/download"
```

### Bazarr Sync (manual trigger)

```bash
curl -X POST http://localhost:8765/api/sync/bazarr
```

### Stats

```bash
curl http://localhost:8765/api/subtitles/stats
```

### Backup

```bash
./scripts/backup.sh
```

Backups are saved to `./backups/` by default.

### Restore

```bash
./scripts/restore.sh backups/subtitles_20240101_120000.db backups/subs_20240101_120000.tar.gz
```

---

## API Reference

All endpoints support optional `X-API-Key` header when `API_KEY` is configured.

### Health

| Method | Path | Description |
|---|---|---|
| GET | `/healthz` | Health check |

### Search & Download

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/subtitles/search` | Search subtitles |
| GET | `/api/v1/subtitles/best` | Best-match subtitle |
| GET | `/api/v1/subtitles/{id}/download` | Download as ZIP |
| GET | `/api/v1/subtitles/best/download` | Download best match as ZIP |
| GET | `/api/v1/movie/{imdb}` | Movie summary |
| GET | `/api/v1/movie/{imdb}/{lang}` | Movie subtitles by language |

**Search parameters:** `imdb`, `lang`, `q`, `release`, `season`, `episode`, `limit`

```bash
# Search by IMDb + language
curl "http://localhost:8765/api/v1/subtitles/search?imdb=tt0111161&lang=english&limit=20"

# Best match with release hint
curl "http://localhost:8765/api/v1/subtitles/best?imdb=tt0111161&lang=english&release=Shawshank.1994.BluRay.x264"
```

### Upload / CRUD

| Method | Path | Description |
|---|---|---|
| POST | `/api/subtitles/upload` | Upload single .srt |
| POST | `/api/subtitles/upload/bulk` | Upload multiple .srt files |
| PUT | `/api/subtitles/{id}` | Update metadata / replace file |
| DELETE | `/api/subtitles/{id}` | Delete subtitle |

### Stats

| Method | Path | Description |
|---|---|---|
| GET | `/api/subtitles/stats` | Totals by language and source |

### Sync

| Method | Path | Description |
|---|---|---|
| POST | `/api/sync/bazarr` | Trigger Bazarr sync |
| GET | `/api/sync/status` | Last sync state |

### Meta

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/meta/languages` | Languages with counts |
| GET | `/api/v1/meta/imdb/suggest` | Title autocomplete |
| GET | `/api/v1/meta/config` | Server config |
| GET | `/api/v1/meta/omdb` | OMDb proxy |

> All `/api/v1/*` routes also available as `/v1/*` for backward compatibility.

---

## License

See [LICENSE](LICENSE).
