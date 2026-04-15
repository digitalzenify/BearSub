"""BearSub – personal subtitle repository backend."""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import os
import re
import shutil
import sqlite3
import threading
import urllib.parse
import urllib.request
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp
from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    FastAPI,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8765"))
DB_PATH = os.getenv("DB_PATH", "./data/db/subtitles.db")
SUBS_DIR = os.getenv("SUBS_DIR", "./data/subs")
API_KEY = os.getenv("API_KEY", "")
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "")
FORCE_ENTER_KEYS = os.getenv("FORCE_ENTER_KEYS", "false").strip().lower() in (
    "1", "true", "yes", "on",
)
BAZARR_SYNC_ENABLED = os.getenv("BAZARR_SYNC_ENABLED", "false").strip().lower() in (
    "1", "true", "yes", "on",
)
BAZARR_URL = os.getenv("BAZARR_URL", "http://localhost:6767").rstrip("/")
BAZARR_API_KEY = os.getenv("BAZARR_API_KEY", "")
BAZARR_SYNC_INTERVAL_HOURS = max(0.1, float(os.getenv("BAZARR_SYNC_INTERVAL_HOURS", "6")))
MEDIA_ROOT_DIR = os.getenv("MEDIA_ROOT_DIR", "/media")
BACKUP_DIR = os.getenv("BACKUP_DIR", "./backups")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("bearsub")

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
_DB_LOCK = threading.Lock()

DDL = """
CREATE TABLE IF NOT EXISTS subtitles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imdb_id TEXT,
    title TEXT,
    year INTEGER,
    type TEXT DEFAULT 'movie',
    season INTEGER,
    episode INTEGER,
    language TEXT,
    release_name TEXT,
    file_path TEXT,
    file_hash TEXT,
    source TEXT DEFAULT 'manual',
    added_date TEXT,
    file_size INTEGER
);

CREATE INDEX IF NOT EXISTS idx_imdb_id ON subtitles(imdb_id);
CREATE INDEX IF NOT EXISTS idx_language ON subtitles(language);
CREATE INDEX IF NOT EXISTS idx_title ON subtitles(title);
CREATE INDEX IF NOT EXISTS idx_release_name ON subtitles(release_name);
CREATE INDEX IF NOT EXISTS idx_source ON subtitles(source);

CREATE TABLE IF NOT EXISTS suggest_titles (
    imdb_id TEXT PRIMARY KEY,
    title TEXT,
    year INTEGER,
    cnt INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sync_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sync_type TEXT,
    last_sync_timestamp TEXT,
    last_sync_status TEXT,
    items_synced INTEGER DEFAULT 0
);
"""


def _db_connect() -> sqlite3.Connection:
    """Open a SQLite connection with row-factory set."""
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def db_read() -> sqlite3.Connection:
    """Return a connection suitable for read queries (no lock needed)."""
    return _db_connect()


def init_db() -> None:
    """Create tables and indexes on first startup."""
    with _DB_LOCK:
        conn = _db_connect()
        conn.executescript(DDL)
        conn.commit()
        conn.close()
    log.info("Database initialised at %s", DB_PATH)


# ---------------------------------------------------------------------------
# File / path helpers
# ---------------------------------------------------------------------------

def sanitize_path_component(s: str) -> str:
    """Remove characters unsafe for filesystem path components."""
    s = (s or "").strip()
    s = re.sub(r"[^\w\-. ]", "_", s)
    s = re.sub(r"\s+", "_", s)
    s = s.strip("._")
    return s or "unknown"


def subtitle_file_path(imdb_id: str, language: str, release_name: str) -> str:
    """Return an absolute path for storing a subtitle file.

    Sanitizes all path components and ensures the result stays within SUBS_DIR.
    Appends a counter suffix when the file already exists.
    """
    safe_imdb = sanitize_path_component(imdb_id)
    safe_lang = sanitize_path_component(language)
    safe_rel = sanitize_path_component(release_name)

    subs_root = os.path.realpath(SUBS_DIR)
    directory = os.path.normpath(os.path.join(subs_root, safe_imdb, safe_lang))

    # Prevent path traversal escaping SUBS_DIR
    if not directory.startswith(subs_root + os.sep) and directory != subs_root:
        raise ValueError(f"Computed path escapes SUBS_DIR: {directory}")

    os.makedirs(directory, exist_ok=True)

    candidate = os.path.join(directory, f"{safe_rel}.srt")
    if not os.path.exists(candidate):
        return candidate

    counter = 2
    while True:
        candidate = os.path.join(directory, f"{safe_rel}_{counter}.srt")
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def md5_of_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


# ---------------------------------------------------------------------------
# Row serialisation
# ---------------------------------------------------------------------------

def serialize_row(r: Any, score: Optional[float] = None) -> Dict[str, Any]:
    """Serialise a SQLite Row (or dict) to the API response shape."""
    if isinstance(r, sqlite3.Row):
        r = dict(r)
    return {
        "id": r["id"],
        "title": r.get("title"),
        "imdb": r.get("imdb_id"),
        "year": r.get("year"),
        "type": r.get("type"),
        "season": r.get("season"),
        "episode": r.get("episode"),
        "lang": r.get("language"),
        "language": r.get("language"),
        "release_name": r.get("release_name"),
        "releases": [r.get("release_name")] if r.get("release_name") else [],
        "source": r.get("source"),
        "added_date": r.get("added_date"),
        "file_hash": r.get("file_hash"),
        "download_url": f"/api/v1/subtitles/{r['id']}/download",
        # Legacy fields for Bazarr provider backward compat
        "subscene_link": None,
        "fileLink": r.get("file_path"),
        "author_name": r.get("source"),
        "comment": r.get("release_name"),
        **({"score": round(float(score), 3)} if score is not None else {}),
    }


# ---------------------------------------------------------------------------
# Search / scoring
# ---------------------------------------------------------------------------

def _tokenize(s: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9]+", (s or "").lower())


def score_candidate(
    row: Dict[str, Any],
    query_tokens: List[str],
    release_tokens: List[str],
) -> float:
    """Score a subtitle row against query and release tokens.

    Higher score = better match.
    """
    score = 0.0
    release_name = (row.get("release_name") or "").lower()
    row_tokens = _tokenize(release_name)
    token_set = set(row_tokens)

    # Exact release match bonus
    for tok in release_tokens:
        if tok in token_set:
            score += 2.0

    # Query token match
    for tok in query_tokens:
        if tok in token_set:
            score += 1.5

    # Prefer longer, more specific releases
    score += min(len(row_tokens) * 0.05, 1.0)

    return score


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def require_key(x_api_key: Optional[str]) -> None:
    if API_KEY and (x_api_key != API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")


# ---------------------------------------------------------------------------
# Bazarr sync
# ---------------------------------------------------------------------------

async def sync_bazarr_once() -> Dict[str, Any]:
    """Perform a single Bazarr history sync, return summary dict."""
    log.info("Bazarr sync: starting")
    conn = _db_connect()

    # Retrieve last sync timestamp
    row = conn.execute(
        "SELECT last_sync_timestamp FROM sync_state WHERE sync_type=? ORDER BY id DESC LIMIT 1",
        ("bazarr",),
    ).fetchone()
    last_ts: Optional[str] = row["last_sync_timestamp"] if row else None

    items_synced = 0
    errors = 0

    async with aiohttp.ClientSession() as session:
        for endpoint in ("history/episodes", "history/movies"):
            url = f"{BAZARR_URL}/api/{endpoint}"
            params = {
                "apikey": BAZARR_API_KEY,
                "page": 1,
                "per_page": 100,
                "action": 1,
            }
            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        log.warning("Bazarr sync: %s returned %s", url, resp.status)
                        continue
                    data = await resp.json(content_type=None)
            except Exception as exc:
                log.warning("Bazarr sync: failed to reach %s: %s", url, exc)
                continue

            records = data.get("data") or []
            is_episode = "episodes" in endpoint

            for item in records:
                try:
                    ts = item.get("timestamp") or item.get("date") or ""
                    if last_ts and ts and ts <= last_ts:
                        continue

                    video_path: str = item.get("video_path") or item.get("path") or ""
                    sub_path: str = item.get("subtitles_path") or item.get("subtitle_path") or ""
                    if not sub_path:
                        # Try to derive from video path
                        if video_path:
                            base = os.path.splitext(video_path)[0]
                            sub_path = base + ".srt"
                        else:
                            continue

                    # Resolve against MEDIA_ROOT_DIR if not absolute
                    if not os.path.isabs(sub_path):
                        sub_path = os.path.join(MEDIA_ROOT_DIR, sub_path.lstrip("/"))

                    # Validate that resolved path stays within MEDIA_ROOT_DIR
                    media_root_real = os.path.realpath(MEDIA_ROOT_DIR)
                    sub_path_real = os.path.realpath(sub_path)
                    if not sub_path_real.startswith(media_root_real + os.sep) and sub_path_real != media_root_real:
                        log.warning("Bazarr sync: path escapes MEDIA_ROOT_DIR, skipping: %s", sub_path)
                        continue

                    if not os.path.isfile(sub_path):
                        log.debug("Bazarr sync: subtitle file not found: %s", sub_path)
                        continue

                    with open(sub_path, "rb") as fh:
                        content = fh.read()

                    file_hash = md5_of_bytes(content)

                    # Deduplication by hash
                    existing = conn.execute(
                        "SELECT id FROM subtitles WHERE file_hash=?", (file_hash,)
                    ).fetchone()
                    if existing:
                        continue

                    imdb_id: str = str(item.get("imdb_id") or item.get("series_imdb_id") or "")
                    if imdb_id and imdb_id.isdigit():
                        imdb_id = "tt" + imdb_id
                    title: str = item.get("title") or item.get("series_title") or os.path.basename(video_path)
                    language: str = item.get("language") or item.get("lang") or "unknown"
                    release_name: str = item.get("release_info") or os.path.splitext(os.path.basename(sub_path))[0]
                    season = item.get("season")
                    episode = item.get("episode")
                    media_type = "episode" if is_episode else "movie"
                    year_val = item.get("year")

                    dest_path = subtitle_file_path(imdb_id or "unknown", language, release_name)
                    with open(dest_path, "wb") as fh:
                        fh.write(content)

                    now = datetime.now(timezone.utc).isoformat()
                    with _DB_LOCK:
                        conn.execute(
                            """INSERT INTO subtitles
                               (imdb_id, title, year, type, season, episode, language,
                                release_name, file_path, file_hash, source, added_date, file_size)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (
                                imdb_id, title, year_val, media_type, season, episode,
                                language, release_name, dest_path, file_hash,
                                "bazarr-sync", now, len(content),
                            ),
                        )
                        if imdb_id:
                            conn.execute(
                                """INSERT INTO suggest_titles (imdb_id, title, year, cnt)
                                   VALUES (?,?,?,1)
                                   ON CONFLICT(imdb_id) DO UPDATE SET cnt=cnt+1""",
                                (imdb_id, title, year_val),
                            )
                        conn.commit()

                    items_synced += 1
                    log.info("Bazarr sync: imported %s -> %s", sub_path, dest_path)

                except Exception as exc:
                    log.warning("Bazarr sync: error processing item: %s", exc)
                    errors += 1

    now = datetime.now(timezone.utc).isoformat()
    status = "ok" if errors == 0 else f"partial ({errors} errors)"
    with _DB_LOCK:
        conn.execute(
            """INSERT INTO sync_state (sync_type, last_sync_timestamp, last_sync_status, items_synced)
               VALUES (?,?,?,?)""",
            ("bazarr", now, status, items_synced),
        )
        conn.commit()
    conn.close()

    log.info("Bazarr sync: done. synced=%d errors=%d", items_synced, errors)
    return {"synced": items_synced, "errors": errors, "timestamp": now, "status": status}


async def bazarr_sync_loop() -> None:
    """Background task: wait 30 s, then sync on interval."""
    await asyncio.sleep(30)
    while True:
        try:
            await sync_bazarr_once()
        except Exception as exc:
            log.error("Bazarr sync loop error: %s", exc)
        await asyncio.sleep(BAZARR_SYNC_INTERVAL_HOURS * 3600)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: init DB, start sync task."""
    os.makedirs(SUBS_DIR, exist_ok=True)
    init_db()
    task: Optional[asyncio.Task] = None
    if BAZARR_SYNC_ENABLED:
        log.info("Bazarr sync enabled, scheduling background task")
        task = asyncio.create_task(bazarr_sync_loop())
    yield
    if task:
        task.cancel()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

APP = FastAPI(title="BearSub API", version="2.0.0", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Auth dependency helper
# ---------------------------------------------------------------------------


def _check_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> None:
    require_key(x_api_key)


# ---------------------------------------------------------------------------
# Helper: build search query
# ---------------------------------------------------------------------------

def _search_rows(
    imdb: Optional[str] = None,
    lang: Optional[str] = None,
    q: Optional[str] = None,
    release: Optional[str] = None,
    season: Optional[int] = None,
    episode: Optional[int] = None,
    limit: int = 60,
) -> List[Dict[str, Any]]:
    """Execute a subtitle search and return list of row dicts."""
    conn = db_read()
    conditions: List[str] = []
    params: List[Any] = []

    if imdb:
        # Normalise tt prefix
        imdb_norm = imdb.strip()
        if imdb_norm.isdigit():
            imdb_norm = "tt" + imdb_norm
        conditions.append("imdb_id=?")
        params.append(imdb_norm)

    if lang:
        conditions.append("LOWER(language)=LOWER(?)")
        params.append(lang)

    if season is not None:
        conditions.append("season=?")
        params.append(season)

    if episode is not None:
        conditions.append("episode=?")
        params.append(episode)

    if q:
        conditions.append("(LOWER(release_name) LIKE ? OR LOWER(title) LIKE ?)")
        pattern = f"%{q.lower()}%"
        params.extend([pattern, pattern])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"SELECT * FROM subtitles {where} ORDER BY id DESC LIMIT ?"
    params.append(min(limit, 500))

    rows = conn.execute(sql, params).fetchall()
    conn.close()

    result = [dict(r) for r in rows]

    # Score & re-sort if release hint given
    if release:
        rel_tokens = _tokenize(release)
        q_tokens = _tokenize(q or "")
        scored = [(score_candidate(r, q_tokens, rel_tokens), r) for r in result]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [(sc, r) for sc, r in scored]

    return [(None, r) for r in result]


# ---------------------------------------------------------------------------
# OMDb proxy
# ---------------------------------------------------------------------------

def _omdb_fetch(params: Dict[str, str]) -> Dict[str, Any]:
    key = OMDB_API_KEY
    if not key:
        raise HTTPException(status_code=503, detail="OMDB_API_KEY not configured")
    params["apikey"] = key
    qs = urllib.parse.urlencode(params)
    url = f"https://www.omdbapi.com/?{qs}"
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            return json.loads(resp.read())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"OMDb error: {exc}") from exc


# ---------------------------------------------------------------------------
# Routes: health
# ---------------------------------------------------------------------------

@APP.get("/healthz", tags=["meta"])
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Routes: meta
# ---------------------------------------------------------------------------

@APP.get("/api/v1/meta/config", tags=["meta"])
@APP.get("/v1/meta/config", tags=["meta"])
def meta_config(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> Dict[str, Any]:
    require_key(x_api_key)
    return {"force_enter_keys": FORCE_ENTER_KEYS, "version": "2.0.0"}


@APP.get("/api/v1/meta/languages", tags=["meta"])
@APP.get("/v1/meta/languages", tags=["meta"])
def meta_languages(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> Dict[str, Any]:
    require_key(x_api_key)
    conn = db_read()
    rows = conn.execute(
        "SELECT language AS lang, COUNT(*) AS count FROM subtitles GROUP BY language ORDER BY count DESC"
    ).fetchall()
    conn.close()
    return {"results": [dict(r) for r in rows]}


@APP.get("/api/v1/meta/imdb/suggest", tags=["meta"])
@APP.get("/v1/meta/imdb/suggest", tags=["meta"])
def meta_suggest(
    q: str = Query(""),
    limit: int = Query(18),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    require_key(x_api_key)
    conn = db_read()
    pattern = f"%{q.strip()}%"
    rows = conn.execute(
        """SELECT imdb_id AS imdb_tt, title, year, cnt AS count
           FROM suggest_titles
           WHERE title LIKE ? OR imdb_id LIKE ?
           ORDER BY cnt DESC LIMIT ?""",
        (pattern, pattern, min(limit, 100)),
    ).fetchall()
    conn.close()
    return {"results": [dict(r) for r in rows]}


@APP.get("/api/v1/meta/omdb", tags=["meta"])
@APP.get("/v1/meta/omdb", tags=["meta"])
def meta_omdb(
    i: Optional[str] = Query(None),
    t: Optional[str] = Query(None),
    y: Optional[str] = Query(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    require_key(x_api_key)
    params: Dict[str, str] = {}
    if i:
        params["i"] = i
    if t:
        params["t"] = t
    if y:
        params["y"] = y
    return _omdb_fetch(params)


# ---------------------------------------------------------------------------
# Routes: subtitle search / best
# ---------------------------------------------------------------------------

@APP.get("/api/v1/subtitles/search", tags=["subtitles"])
@APP.get("/v1/subtitles/search", tags=["subtitles"])
def subtitles_search(
    imdb: Optional[str] = Query(None),
    lang: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    release: Optional[str] = Query(None),
    season: Optional[int] = Query(None),
    episode: Optional[int] = Query(None),
    limit: int = Query(60),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    require_key(x_api_key)
    scored = _search_rows(
        imdb=imdb, lang=lang, q=q, release=release,
        season=season, episode=episode, limit=limit,
    )
    results = [serialize_row(r, sc) for sc, r in scored]
    return {"count": len(results), "results": results}


@APP.get("/api/v1/subtitles/best", tags=["subtitles"])
@APP.get("/v1/subtitles/best", tags=["subtitles"])
def subtitles_best(
    imdb: Optional[str] = Query(None),
    lang: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    release: Optional[str] = Query(None),
    season: Optional[int] = Query(None),
    episode: Optional[int] = Query(None),
    limit: int = Query(1400),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    require_key(x_api_key)
    rel_tokens = _tokenize(release or "")
    q_tokens = _tokenize(q or "")
    scored = _search_rows(
        imdb=imdb, lang=lang, q=q, release=release,
        season=season, episode=episode, limit=limit,
    )
    if not scored:
        raise HTTPException(status_code=404, detail="No results found")

    # Re-score using both release and q tokens
    rescored = [
        (score_candidate(r, q_tokens, rel_tokens), r)
        for _, r in scored
    ]
    rescored.sort(key=lambda x: x[0], reverse=True)
    best_sc, best_row = rescored[0]
    return {"best": serialize_row(best_row, best_sc)}


# ---------------------------------------------------------------------------
# Routes: download
# ---------------------------------------------------------------------------

def _make_zip(file_path: str, arc_name: str) -> bytes:
    """Wrap a file in an in-memory ZIP archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(file_path, arc_name)
    return buf.getvalue()


@APP.get("/api/v1/subtitles/{sub_id}/download", tags=["subtitles"])
@APP.get("/v1/subtitles/{sub_id}/download", tags=["subtitles"])
def subtitle_download(
    sub_id: int,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> StreamingResponse:
    require_key(x_api_key)
    conn = db_read()
    row = conn.execute("SELECT * FROM subtitles WHERE id=?", (sub_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Subtitle not found")

    file_path: str = row["file_path"] or ""
    if not file_path:
        raise HTTPException(status_code=404, detail="Subtitle file not found on disk")

    # Validate path stays within SUBS_DIR to prevent stored path injection
    subs_root = os.path.realpath(SUBS_DIR)
    file_path_real = os.path.realpath(file_path)
    if not file_path_real.startswith(subs_root + os.sep) and file_path_real != subs_root:
        raise HTTPException(status_code=403, detail="File path is outside allowed directory")

    if not os.path.isfile(file_path_real):
        raise HTTPException(status_code=404, detail="Subtitle file not found on disk")

    release = (row["release_name"] or f"subtitle_{sub_id}").replace(" ", "_")
    arc_name = f"{release}.srt"
    zip_name = f"{release}.zip"
    data = _make_zip(file_path_real, arc_name)

    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
    )


@APP.get("/api/v1/subtitles/best/download", tags=["subtitles"])
@APP.get("/v1/subtitles/best/download", tags=["subtitles"])
def subtitle_best_download(
    imdb: Optional[str] = Query(None),
    lang: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    release: Optional[str] = Query(None),
    season: Optional[int] = Query(None),
    episode: Optional[int] = Query(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> StreamingResponse:
    require_key(x_api_key)
    result = subtitles_best(
        imdb=imdb, lang=lang, q=q, release=release,
        season=season, episode=episode, limit=1400,
        x_api_key=x_api_key,
    )
    best = result["best"]
    return subtitle_download(sub_id=best["id"], x_api_key=x_api_key)


# ---------------------------------------------------------------------------
# Routes: movie summary
# ---------------------------------------------------------------------------

@APP.get("/api/v1/movie/{imdb}", tags=["movie"])
@APP.get("/v1/movie/{imdb}", tags=["movie"])
def movie_summary(
    imdb: str,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    require_key(x_api_key)
    imdb_norm = imdb.strip()
    if imdb_norm.isdigit():
        imdb_norm = "tt" + imdb_norm

    conn = db_read()
    rows = conn.execute(
        "SELECT * FROM subtitles WHERE imdb_id=? ORDER BY id DESC",
        (imdb_norm,),
    ).fetchall()
    conn.close()

    if not rows:
        raise HTTPException(status_code=404, detail="No subtitles found for this title")

    languages = list({r["language"] for r in rows if r["language"]})
    title = rows[0]["title"] if rows else None
    return {
        "imdb_tt": imdb_norm,
        "title": title,
        "total_subs": len(rows),
        "languages": languages,
    }


@APP.get("/api/v1/movie/{imdb}/{lang}", tags=["movie"])
@APP.get("/v1/movie/{imdb}/{lang}", tags=["movie"])
def movie_by_lang(
    imdb: str,
    lang: str,
    limit: int = Query(100),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    require_key(x_api_key)
    scored = _search_rows(imdb=imdb, lang=lang, limit=limit)
    results = [serialize_row(r, sc) for sc, r in scored]
    return {"count": len(results), "results": results}


# ---------------------------------------------------------------------------
# Routes: CRUD – upload
# ---------------------------------------------------------------------------

@APP.post("/api/subtitles/upload", tags=["upload"])
async def upload_subtitle(
    file: UploadFile,
    imdb_id: str = Form(...),
    title: str = Form(...),
    year: Optional[int] = Form(None),
    language: str = Form(...),
    release_name: str = Form(...),
    type: str = Form("movie"),
    season: Optional[int] = Form(None),
    episode: Optional[int] = Form(None),
    source: str = Form("manual"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Upload a single .srt subtitle file with metadata."""
    require_key(x_api_key)

    if not file.filename or not file.filename.lower().endswith(".srt"):
        raise HTTPException(status_code=400, detail="Only .srt files are accepted")

    content = await file.read()
    file_hash = md5_of_bytes(content)

    # Deduplicate
    conn = db_read()
    existing = conn.execute(
        "SELECT id FROM subtitles WHERE file_hash=?", (file_hash,)
    ).fetchone()
    conn.close()
    if existing:
        raise HTTPException(status_code=409, detail="Subtitle already exists (duplicate hash)")

    # Normalise imdb
    imdb_norm = imdb_id.strip()
    if imdb_norm.isdigit():
        imdb_norm = "tt" + imdb_norm

    dest_path = subtitle_file_path(imdb_norm, language, release_name)
    with open(dest_path, "wb") as fh:
        fh.write(content)

    now = datetime.now(timezone.utc).isoformat()
    with _DB_LOCK:
        wconn = _db_connect()
        cur = wconn.execute(
            """INSERT INTO subtitles
               (imdb_id, title, year, type, season, episode, language,
                release_name, file_path, file_hash, source, added_date, file_size)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                imdb_norm, title, year, type, season, episode,
                language, release_name, dest_path, file_hash,
                source, now, len(content),
            ),
        )
        new_id = cur.lastrowid
        wconn.execute(
            """INSERT INTO suggest_titles (imdb_id, title, year, cnt)
               VALUES (?,?,?,1)
               ON CONFLICT(imdb_id) DO UPDATE SET cnt=cnt+1, title=excluded.title""",
            (imdb_norm, title, year),
        )
        wconn.commit()
        wconn.close()

    return {
        "id": new_id,
        "file_path": dest_path,
        "download_url": f"/api/v1/subtitles/{new_id}/download",
    }


@APP.post("/api/subtitles/upload/bulk", tags=["upload"])
async def upload_bulk(
    files: List[UploadFile],
    imdb_id: str = Form(...),
    title: str = Form(...),
    year: Optional[int] = Form(None),
    language: str = Form(...),
    release_name: str = Form(...),
    type: str = Form("movie"),
    season: Optional[int] = Form(None),
    episode: Optional[int] = Form(None),
    source: str = Form("manual"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Upload multiple .srt files sharing the same metadata."""
    require_key(x_api_key)
    results = []
    for f in files:
        try:
            res = await upload_subtitle(
                file=f,
                imdb_id=imdb_id,
                title=title,
                year=year,
                language=language,
                release_name=release_name,
                type=type,
                season=season,
                episode=episode,
                source=source,
                x_api_key=x_api_key,
            )
            results.append({"filename": f.filename, **res})
        except HTTPException as exc:
            results.append({"filename": f.filename, "error": exc.detail})
    return {"uploaded": len([r for r in results if "id" in r]), "results": results}


# ---------------------------------------------------------------------------
# Routes: CRUD – delete / update
# ---------------------------------------------------------------------------

@APP.delete("/api/subtitles/{sub_id}", tags=["subtitles"])
def delete_subtitle(
    sub_id: int,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Delete a subtitle record and its file from disk."""
    require_key(x_api_key)
    conn = db_read()
    row = conn.execute("SELECT * FROM subtitles WHERE id=?", (sub_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Subtitle not found")

    file_path: str = row["file_path"] or ""
    if file_path and os.path.isfile(file_path):
        os.remove(file_path)

    with _DB_LOCK:
        wconn = _db_connect()
        wconn.execute("DELETE FROM subtitles WHERE id=?", (sub_id,))
        wconn.commit()
        wconn.close()

    return {"deleted": sub_id}


@APP.put("/api/subtitles/{sub_id}", tags=["subtitles"])
async def update_subtitle(
    sub_id: int,
    title: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    language: Optional[str] = Form(None),
    release_name: Optional[str] = Form(None),
    source: Optional[str] = Form(None),
    file: Optional[UploadFile] = None,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Update subtitle metadata and optionally replace the .srt file."""
    require_key(x_api_key)
    conn = db_read()
    row = conn.execute("SELECT * FROM subtitles WHERE id=?", (sub_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Subtitle not found")

    updates: Dict[str, Any] = {}
    if title is not None:
        updates["title"] = title
    if year is not None:
        updates["year"] = year
    if language is not None:
        updates["language"] = language
    if release_name is not None:
        updates["release_name"] = release_name
    if source is not None:
        updates["source"] = source

    if file and file.filename:
        if not file.filename.lower().endswith(".srt"):
            raise HTTPException(status_code=400, detail="Only .srt files accepted")
        content = await file.read()
        file_hash = md5_of_bytes(content)
        old_path: str = row["file_path"] or ""
        # Validate old_path before reusing it
        subs_root = os.path.realpath(SUBS_DIR)
        old_path_real = os.path.realpath(old_path) if old_path else ""
        path_safe = (
            old_path_real
            and os.path.isfile(old_path_real)
            and (old_path_real.startswith(subs_root + os.sep) or old_path_real == subs_root)
        )
        dest_path = old_path_real if path_safe else subtitle_file_path(
            row["imdb_id"] or "unknown",
            updates.get("language") or row["language"] or "unknown",
            updates.get("release_name") or row["release_name"] or f"sub_{sub_id}",
        )
        with open(dest_path, "wb") as fh:
            fh.write(content)
        updates["file_path"] = dest_path
        updates["file_hash"] = file_hash
        updates["file_size"] = len(content)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [sub_id]
    with _DB_LOCK:
        wconn = _db_connect()
        wconn.execute(f"UPDATE subtitles SET {set_clause} WHERE id=?", values)
        wconn.commit()
        wconn.close()

    return {"updated": sub_id}


# ---------------------------------------------------------------------------
# Routes: stats
# ---------------------------------------------------------------------------

@APP.get("/api/subtitles/stats", tags=["stats"])
def subtitles_stats(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Return aggregate statistics."""
    require_key(x_api_key)
    conn = db_read()
    total = conn.execute("SELECT COUNT(*) FROM subtitles").fetchone()[0]
    by_lang = [
        dict(r)
        for r in conn.execute(
            "SELECT language, COUNT(*) AS count FROM subtitles GROUP BY language ORDER BY count DESC"
        ).fetchall()
    ]
    by_source = [
        dict(r)
        for r in conn.execute(
            "SELECT source, COUNT(*) AS count FROM subtitles GROUP BY source ORDER BY count DESC"
        ).fetchall()
    ]
    recent = [
        serialize_row(r)
        for r in conn.execute(
            "SELECT * FROM subtitles ORDER BY id DESC LIMIT 10"
        ).fetchall()
    ]
    conn.close()
    return {"total": total, "by_language": by_lang, "by_source": by_source, "recent": recent}


# ---------------------------------------------------------------------------
# Routes: sync
# ---------------------------------------------------------------------------

@APP.post("/api/sync/bazarr", tags=["sync"])
async def sync_bazarr_now(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Manually trigger a Bazarr sync."""
    require_key(x_api_key)
    if not BAZARR_SYNC_ENABLED and not BAZARR_API_KEY:
        raise HTTPException(status_code=503, detail="Bazarr sync not configured")
    return await sync_bazarr_once()


@APP.get("/api/sync/status", tags=["sync"])
def sync_status(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> Dict[str, Any]:
    """Return the most recent sync state."""
    require_key(x_api_key)
    conn = db_read()
    row = conn.execute(
        "SELECT * FROM sync_state ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return {"sync_type": None, "last_sync_timestamp": None, "last_sync_status": None, "items_synced": 0}
    return dict(row)


# ---------------------------------------------------------------------------
# Static files (serve www/ at root)
# ---------------------------------------------------------------------------

_WWW_DIR = os.path.join(os.path.dirname(__file__), "www")
if os.path.isdir(_WWW_DIR):
    APP.mount("/", StaticFiles(directory=_WWW_DIR, html=True), name="static")
