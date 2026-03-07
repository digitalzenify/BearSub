# SubsDump API

SubsDump provides a FastAPI backend for subtitle search, downloads, and archive browsing.

Base URL example:

https://subs.d3lphi3r.com

--------------------------------------------------

AUTHENTICATION

Some endpoints may require an API key through header:

X-API-Key: your_api_key_here

--------------------------------------------------

HEALTH CHECK

GET /healthz

Returns backend health status.

Example response:

{
  "ok": true,
  "ts": "2026-03-07T03:21:00Z"
}

--------------------------------------------------

CONFIG METADATA

GET /api/v1/meta/config

Returns frontend related backend configuration.

Example response:

{
  "force_enter_keys": false,
  "omdb_proxy_enabled": true
}

--------------------------------------------------

LANGUAGES

GET /api/v1/meta/languages

Returns available subtitle languages.

Example response:

{
  "count": 77,
  "results": [
    {
      "lang": "arabic",
      "count": 284744
    }
  ]
}

--------------------------------------------------

IMDB SUGGESTIONS

GET /api/v1/meta/imdb/suggest?q=edge

Returns title suggestions grouped by IMDb ID.

--------------------------------------------------

OMDB PROXY

GET /api/v1/meta/omdb?i=tt1631867

Returns movie metadata.

Example response:

{
  "Title": "Edge of Tomorrow",
  "Year": "2014",
  "Runtime": "113 min",
  "imdbRating": "7.9",
  "Poster": "https://...",
  "imdbID": "tt1631867"
}

--------------------------------------------------

SUBTITLE SEARCH

GET /api/v1/subtitles/search

Parameters:

imdb     -> imdb id example: tt1631867
lang     -> language example: arabic
release  -> video filename or release name
q        -> optional free text search
limit    -> max results

Example:

/api/v1/subtitles/search?imdb=tt1631867&lang=arabic&release=Edge.of.Tomorrow.2014.REMUX.mkv&limit=50

Important:

The Bazarr provider sends:

release=<filename>

The provider intentionally does NOT send:

q=<release>

because q acts as an additional SQL filter and may hide valid matches.

--------------------------------------------------

BEST MATCH

GET /api/v1/subtitles/best

Returns the highest ranked subtitle.

Example:

/api/v1/subtitles/best?imdb=tt1631867&lang=arabic&release=Edge.of.Tomorrow.2014.REMUX.mkv

--------------------------------------------------

DIRECT DOWNLOAD

GET /api/v1/subtitles/{id}/download

Example:

/api/v1/subtitles/597361/download

--------------------------------------------------

BEST MATCH DOWNLOAD

GET /api/v1/subtitles/best/download

Example:

/api/v1/subtitles/best/download?imdb=tt1631867&lang=arabic&release=Edge.of.Tomorrow.2014.REMUX.mkv

--------------------------------------------------

MOVIE ARCHIVE

GET /api/v1/movie/{imdb}

Example:

/api/v1/movie/tt2194499

Returns subtitle counts grouped by language.

--------------------------------------------------

MOVIE LANGUAGE PAGE

GET /api/v1/movie/{imdb}/{lang}

Example:

/api/v1/movie/tt2194499/arabic

--------------------------------------------------

FRONTEND ROUTES

The web UI supports routes like:

/movie/tt1631867
/movie/tt1631867/arabic
/subtitle/about-time/arabic/870894

These routes are resolved by the frontend using the API endpoints above.
