import os
import json
import re
import urllib.request
import urllib.parse

from datetime import datetime, timezone
from typing import Optional, List, Any, Dict

import pymysql
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import FileResponse, RedirectResponse

APP = FastAPI(title="Subscene Local Provider API", version="1.3.0")

DB_HOST = os.getenv("DB_HOST", "db.d3lphi3r.com")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "subscene_db")
DB_USER = os.getenv("DB_USER", "subscene_ro")
DB_PASS = os.getenv("DB_PASS", "")
FILES_BASE = os.getenv("FILES_BASE", "/mnt/subscene/files")
API_KEY = os.getenv("API_KEY", "")
OMDB_API_KEY_DEF = os.getenv("OMDB_API_KEY_DEF", "")
FORCE_ENTER_KEYS = os.getenv("FORCE_ENTER_KEYS", "false").strip().lower() in ("1", "true", "yes", "on")


def db_conn():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        read_timeout=20,
        write_timeout=20,
        connect_timeout=8,
    )


def require_key(x_api_key: Optional[str]):
    if API_KEY and (x_api_key != API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")


def safe_relpath(p: str) -> str:
    p = (p or "").strip().lstrip("/").replace("\\", "/")
    if not p:
        raise HTTPException(status_code=400, detail="Invalid file path")
    if ".." in p.split("/"):
        raise HTTPException(status_code=400, detail="Invalid file path")
    return p


def parse_json_maybe(val: Any):
    if val is None:
        return None
    if isinstance(val, (list, dict)):
        return val
    if isinstance(val, str):
        s = val.strip()
        if s.startswith("[") or s.startswith("{"):
            try:
                return json.loads(s)
            except Exception:
                return val
    return val


def imdb_to_int(imdb: str) -> Optional[int]:
    if not imdb:
        return None
    s = imdb.strip()
    if s.startswith("tt"):
        m = re.search(r"(\d+)", s)
        return int(m.group(1)) if m else None
    return int(s) if s.isdigit() else None


_token_re = re.compile(r"[^a-z0-9]+")


def tokens(s: str) -> List[str]:
    if not s:
        return []
    s = s.lower()
    s = _token_re.sub(" ", s).strip()
    if not s:
        return []
    return [p for p in s.split() if len(p) >= 2]


def recency_bonus(dt: Optional[datetime]) -> float:
    if not dt:
        return 0.0
    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0
        if age_days < 0:
            age_days = 0
        return 5.0 / (1.0 + (age_days / 365.0))
    except Exception:
        return 0.0


def score_candidate(release_query: str, row: Dict[str, Any]) -> float:
    rq = tokens(release_query)

    rels = parse_json_maybe(row.get("releases"))
    if isinstance(rels, list):
        rel_text = " ".join([str(x) for x in rels])
    elif isinstance(rels, str):
        rel_text = rels
    else:
        rel_text = ""

    rel_tokens = set(tokens(rel_text))
    title_tokens = set(tokens(str(row.get("title") or "")))
    comment_tokens = set(tokens(str(row.get("comment") or "")))

    score = 0.0

    if rq:
        for t in rq:
            if t in rel_tokens:
                score += 3.0
            elif t in title_tokens:
                score += 1.5
            elif t in comment_tokens:
                score += 0.5

        strong = {
            "bluray", "brrip", "web", "webrip", "webdl", "hdtv",
            "x264", "x265", "hevc", "dv", "hdr",
            "1080p", "2160p", "720p", "remux",
            "ddp", "dts", "truehd", "atmos", "avc"
        }
        score += 0.3 * sum(1 for t in rq if t in strong and t in rel_tokens)

    score += recency_bonus(row.get("date"))
    if rel_text:
        score += 0.5

    return score


def episode_score_bonus(release_query: str, row: Dict[str, Any], season: Optional[int], episode: Optional[int]) -> float:
    if season is None and episode is None:
        return 0.0

    text_parts = []
    rels = parse_json_maybe(row.get("releases"))
    if isinstance(rels, list):
        text_parts.extend([str(x) for x in rels])
    elif isinstance(rels, str):
        text_parts.append(rels)

    text_parts.append(str(row.get("title") or ""))
    text_parts.append(str(row.get("comment") or ""))
    hay = " ".join(text_parts).lower()

    score = 0.0

    if season is not None and episode is not None:
        sxe = f"s{season:02d}e{episode:02d}".lower()
        if sxe in hay:
            score += 8.0

    return score


def serialize_row(r: Dict[str, Any], score: Optional[float] = None) -> Dict[str, Any]:
    out = {
        "id": r["id"],
        "title": r.get("title"),
        "imdb": r.get("imdb"),
        "date": r.get("date").isoformat() if r.get("date") else None,
        "author_name": r.get("author_name"),
        "author_id": r.get("author_id"),
        "lang": r.get("lang"),
        "comment": r.get("comment"),
        "releases": parse_json_maybe(r.get("releases")),
        "subscene_link": r.get("subscene_link"),
        "fileLink": r.get("fileLink"),
        "download_url": f"/api/v1/subtitles/{r['id']}/download",
    }
    if score is not None:
        out["score"] = round(float(score), 3)
    return out


def _languages_impl(x_api_key: Optional[str]):
    require_key(x_api_key)

    sql = """
        SELECT lang, COUNT(*) AS cnt
        FROM all_subs
        WHERE lang IS NOT NULL AND lang <> ''
        GROUP BY lang
        ORDER BY cnt DESC, lang ASC
    """

    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    results = []
    for r in rows or []:
        results.append({
            "lang": r.get("lang"),
            "count": int(r.get("cnt") or 0),
        })

    return {"count": len(results), "results": results}


def _imdb_suggest_impl(q: str, limit: int, x_api_key: Optional[str]):
    require_key(x_api_key)

    q = (q or "").strip()
    if not q:
        return {"count": 0, "results": []}

    limit = max(1, min(int(limit or 20), 50))
    like = f"%{q}%"

    sql = """
        SELECT imdb, title, cnt
        FROM suggest_titles
        WHERE title LIKE %s
        ORDER BY cnt DESC, imdb DESC
        LIMIT %s
    """

    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (like, limit))
                rows = cur.fetchall()
    except Exception as e:
        msg = str(e).lower()
        if "suggest_titles" in msg and ("doesn't exist" in msg or "does not exist" in msg or "1146" in msg):
            raise HTTPException(
                status_code=500,
                detail=(
                    "Missing helper table 'suggest_titles'. "
                    "Please create it once using examples/create_suggest_titles.sql. "
                    "This table is required for fast frontend IMDb/title suggestions."
                )
            )
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    out = []
    for r in rows or []:
        imdb_int = int(r.get("imdb") or 0)
        if imdb_int <= 0:
            continue
        out.append({
            "imdb": imdb_int,
            "imdb_tt": "tt" + str(imdb_int).zfill(7),
            "title": r.get("title") or "",
            "count": int(r.get("cnt") or 0),
        })

    return {"count": len(out), "results": out}

@APP.get("/v1/meta/imdb/suggest")
def imdb_suggest_v1(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=50),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    return _imdb_suggest_impl(q=q, limit=limit, x_api_key=x_api_key)


@APP.get("/api/v1/meta/imdb/suggest")
def imdb_suggest_api_v1(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=50),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    return _imdb_suggest_impl(q=q, limit=limit, x_api_key=x_api_key)


@APP.get("/v1/meta/languages")
def languages_v1(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    return _languages_impl(x_api_key)


@APP.get("/api/v1/meta/languages")
def languages_api_v1(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    return _languages_impl(x_api_key)


@APP.get("/api/v1/meta/config")
def meta_config():
    return {
        "force_enter_keys": bool(FORCE_ENTER_KEYS),
        "omdb_proxy_enabled": bool(OMDB_API_KEY_DEF),
    }


@APP.get("/v1/meta/config")
def meta_config_v1():
    return meta_config()


@APP.get("/api/v1/meta/omdb")
def meta_omdb(i: str = Query(..., min_length=3)):
    if not OMDB_API_KEY_DEF:
        raise HTTPException(status_code=404, detail="OMDb proxy disabled")
    imdb_tt = (i or "").strip()
    if not imdb_tt.startswith("tt"):
        raise HTTPException(status_code=400, detail="Invalid IMDb id (expected ttXXXXXXX)")
    try:
        qs = urllib.parse.urlencode({"i": imdb_tt, "apikey": OMDB_API_KEY_DEF})
        url = "https://www.omdbapi.com/?" + qs
        req = urllib.request.Request(url, headers={"User-Agent": "subs.d3lphi3r.com"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8", "replace")
        data = json.loads(raw)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OMDb fetch failed: {e}")

    if not isinstance(data, dict) or data.get("Response") != "True":
        raise HTTPException(status_code=404, detail="OMDb not found")

    return {
        "Title": data.get("Title"),
        "Year": data.get("Year"),
        "Rated": data.get("Rated"),
        "Runtime": data.get("Runtime"),
        "imdbRating": data.get("imdbRating"),
        "Plot": data.get("Plot"),
        "Poster": data.get("Poster"),
        "imdbID": data.get("imdbID"),
    }


@APP.get("/v1/meta/omdb")
def meta_omdb_v1(i: str = Query(..., min_length=3)):
    return meta_omdb(i=i)




def _movie_summary_impl(imdb: str, x_api_key: Optional[str]):
    require_key(x_api_key)

    imdb_int = imdb_to_int(imdb)
    if imdb_int is None:
        raise HTTPException(status_code=400, detail="Invalid imdb parameter")

    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        MAX(title) AS title,
                        imdb,
                        COUNT(*) AS total_subs,
                        MIN(date) AS first_date,
                        MAX(date) AS last_date
                    FROM all_subs
                    WHERE imdb = %s
                    GROUP BY imdb
                    LIMIT 1
                """, (imdb_int,))
                meta = cur.fetchone()

                if not meta:
                    raise HTTPException(status_code=404, detail="Movie not found")

                cur.execute("""
                    SELECT lang, COUNT(*) AS cnt
                    FROM all_subs
                    WHERE imdb = %s
                    GROUP BY lang
                    ORDER BY cnt DESC, lang ASC
                """, (imdb_int,))
                langs = cur.fetchall()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return {
        "title": meta.get("title"),
        "imdb": meta.get("imdb"),
        "imdb_tt": "tt" + str(meta.get("imdb")).zfill(7),
        "total_subs": int(meta.get("total_subs") or 0),
        "first_date": meta.get("first_date").isoformat() if meta.get("first_date") else None,
        "last_date": meta.get("last_date").isoformat() if meta.get("last_date") else None,
        "languages": [
            {"lang": r.get("lang"), "count": int(r.get("cnt") or 0)}
            for r in (langs or [])
        ]
    }


def _movie_lang_impl(imdb: str, lang: str, limit: int, x_api_key: Optional[str]):
    require_key(x_api_key)

    imdb_int = imdb_to_int(imdb)
    if imdb_int is None:
        raise HTTPException(status_code=400, detail="Invalid imdb parameter")

    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id,title,imdb,date,author_name,author_id,lang,comment,releases,subscene_link,fileLink
                    FROM all_subs
                    WHERE imdb = %s AND lang = %s
                    ORDER BY id DESC
                    LIMIT %s
                """, (imdb_int, lang, limit))
                rows = cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return {
        "count": len(rows or []),
        "results": [serialize_row(r) for r in (rows or [])]
    }


@APP.get("/v1/movie/{imdb}")
def movie_summary_v1(
    imdb: str,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    return _movie_summary_impl(imdb, x_api_key)


@APP.get("/api/v1/movie/{imdb}")
def movie_summary_api_v1(
    imdb: str,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    return _movie_summary_impl(imdb, x_api_key)


@APP.get("/v1/movie/{imdb}/{lang}")
def movie_lang_v1(
    imdb: str,
    lang: str,
    limit: int = Query(default=200, ge=1, le=1000),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    return _movie_lang_impl(imdb, lang, limit, x_api_key)


@APP.get("/api/v1/movie/{imdb}/{lang}")
def movie_lang_api_v1(
    imdb: str,
    lang: str,
    limit: int = Query(default=200, ge=1, le=1000),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    return _movie_lang_impl(imdb, lang, limit, x_api_key)


@APP.get("/healthz")
def healthz():
    return {"ok": True, "ts": datetime.utcnow().isoformat() + "Z"}


def _search_impl(
    imdb: Optional[str],
    lang: Optional[str],
    q: Optional[str],
    release: Optional[str],
    season: Optional[int],
    episode: Optional[int],
    limit: int,
    x_api_key: Optional[str],
):
    require_key(x_api_key)

    where = []
    params: List[Any] = []

    if imdb:
        imdb_int = imdb_to_int(imdb)
        if imdb_int is not None:
            where.append("imdb = %s")
            params.append(imdb_int)

    if lang:
        where.append("lang = %s")
        params.append(lang)

    if q:
        where.append("(title LIKE %s OR comment LIKE %s OR releases LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like, like])

    sql = """
        SELECT id,title,imdb,date,author_name,author_id,lang,comment,releases,subscene_link,fileLink
        FROM all_subs
    """
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT %s"
    params.append(max(limit * 5, 200))

    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    scored = []
    relq = release or q or ""

    for r in rows or []:
        score = score_candidate(relq, r)
        score += episode_score_bonus(relq, r, season, episode)
        scored.append((score, r))

    scored.sort(key=lambda x: (x[0], x[1].get("id") or 0), reverse=True)
    scored = scored[:limit]

    results = [serialize_row(r, score=s) for s, r in scored]
    return {"count": len(results), "results": results}


@APP.get("/v1/subtitles/search")
def search_v1(
    imdb: Optional[str] = Query(default=None),
    lang: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    release: Optional[str] = Query(default=None),
    season: Optional[int] = Query(default=None),
    episode: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    return _search_impl(imdb, lang, q, release, season, episode, limit, x_api_key)


@APP.get("/api/v1/subtitles/search")
def search_api_v1(
    imdb: Optional[str] = Query(default=None),
    lang: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    release: Optional[str] = Query(default=None),
    season: Optional[int] = Query(default=None),
    episode: Optional[int] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    return _search_impl(imdb, lang, q, release, season, episode, limit, x_api_key)


def _best_impl(imdb: str, lang: str, release: Optional[str], q: Optional[str], limit: int, x_api_key: Optional[str]):
    require_key(x_api_key)

    imdb_int = imdb_to_int(imdb)
    if imdb_int is None:
        raise HTTPException(status_code=400, detail="Invalid imdb parameter (expected ttXXXXXXX or digits)")

    where = ["imdb = %s", "lang = %s"]
    params: List[Any] = [imdb_int, lang]

    if q:
        where.append("(title LIKE %s OR comment LIKE %s OR releases LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like, like])

    sql = """
        SELECT id,title,imdb,date,author_name,author_id,lang,comment,releases,subscene_link,fileLink
        FROM all_subs
    """
    sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT %s"
    params.append(limit)

    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    if not rows:
        raise HTTPException(status_code=404, detail="No subtitles found for imdb/lang")

    release_query = release or ""
    best_row = None
    best_score = -1e9

    for r in rows:
        s = score_candidate(release_query, r)
        if s > best_score:
            best_score = s
            best_row = r

    assert best_row is not None

    return {"best": serialize_row(best_row, score=best_score)}


@APP.get("/v1/subtitles/best")
def best_v1(
    imdb: str = Query(..., description="tt1234567 or numeric"),
    lang: str = Query(...),
    release: Optional[str] = Query(default=None, description="release filename / video name"),
    q: Optional[str] = Query(default=None, description="extra keyword filter"),
    limit: int = Query(default=800, ge=10, le=5000),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    return _best_impl(imdb, lang, release, q, limit, x_api_key)


@APP.get("/api/v1/subtitles/best")
def best_api_v1(
    imdb: str = Query(..., description="tt1234567 or numeric"),
    lang: str = Query(...),
    release: Optional[str] = Query(default=None, description="release filename / video name"),
    q: Optional[str] = Query(default=None, description="extra keyword filter"),
    limit: int = Query(default=800, ge=10, le=5000),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    return _best_impl(imdb, lang, release, q, limit, x_api_key)


@APP.api_route("/v1/subtitles/{sub_id}/download", methods=["GET", "HEAD"])
def download_v1(sub_id: int, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    require_key(x_api_key)

    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT fileLink FROM all_subs WHERE id=%s LIMIT 1", (sub_id,))
                row = cur.fetchone()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    if not row or not row.get("fileLink"):
        raise HTTPException(status_code=404, detail="Subtitle not found")

    rel = safe_relpath(row["fileLink"])
    full = os.path.join(FILES_BASE, rel)

    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail=f"File not found on disk: {rel}")

    return FileResponse(full, filename=os.path.basename(full), media_type="application/zip")


@APP.api_route("/api/v1/subtitles/{sub_id}/download", methods=["GET", "HEAD"])
def download_api_v1(sub_id: int, x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")):
    return download_v1(sub_id=sub_id, x_api_key=x_api_key)


@APP.get("/v1/subtitles/best/download")
def best_download_v1(
    imdb: str = Query(...),
    lang: str = Query(...),
    release: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=800, ge=10, le=5000),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    data = _best_impl(imdb, lang, release, q, limit, x_api_key)
    sid = data["best"]["id"]
    return RedirectResponse(url=f"/api/v1/subtitles/{sid}/download", status_code=302)


@APP.get("/api/v1/subtitles/best/download")
def best_download_api_v1(
    imdb: str = Query(...),
    lang: str = Query(...),
    release: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    limit: int = Query(default=800, ge=10, le=5000),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    return best_download_v1(imdb=imdb, lang=lang, release=release, q=q, limit=limit, x_api_key=x_api_key)


@APP.get("/v1/subtitles/by-link/{link:path}")
@APP.get("/api/v1/subtitles/by-link/{link:path}")
def by_link(
    link: str,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    require_key(x_api_key)

    try:
        with db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM all_subs WHERE subscene_link=%s LIMIT 1",
                    (link,)
                )
                row = cur.fetchone()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    if not row:
        raise HTTPException(status_code=404, detail="Subtitle not found")

    releases = parse_json_maybe(row.get("releases"))

    return {
        "id": row["id"],
        "title": row.get("title"),
        "imdb": row.get("imdb"),
        "date": row.get("date").isoformat() if row.get("date") else None,
        "author_name": row.get("author_name"),
        "author_id": row.get("author_id"),
        "lang": row.get("lang"),
        "comment": row.get("comment"),
        "releases": releases,
        "subscene_link": row.get("subscene_link"),
        "fileLink": row.get("fileLink"),
        "download_url": f"/api/v1/subtitles/{row['id']}/download"
    }

