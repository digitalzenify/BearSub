# SubsDump Architecture

SubsDump is a self-hosted subtitle archive and API designed to integrate with tools like Bazarr.

The system has four main layers:

1. Subtitle Database
2. Backend API
3. Bazarr Provider
4. Client Applications (Bazarr / Web UI / Users)

--------------------------------------------------

HIGH LEVEL FLOW

User
  │
  │  requests subtitles
  ▼
Bazarr
  │
  │  calls provider
  ▼
SubsDump Provider (Bazarr plugin)
  │
  │  sends API request
  ▼
SubsDump Backend API
  │
  │  queries subtitle database
  ▼
Subtitle Database

--------------------------------------------------

SUBTITLE DATABASE

The database contains a dump of subtitle metadata including:

- movie title
- imdb id
- language
- release names
- subtitle author
- upload date
- download file path

The database does not store raw subtitle text inside rows.
Instead it references ZIP files stored on disk.

--------------------------------------------------

BACKEND API

The backend is implemented using FastAPI.

Responsibilities:

- searching subtitles
- ranking subtitles by release match
- returning best match results
- serving subtitle downloads
- providing archive browsing endpoints
- exposing metadata for the frontend

Main endpoint example:

/api/v1/subtitles/search

The backend performs scoring based on:

- imdb id match
- language match
- release name similarity

--------------------------------------------------

BAZARR PROVIDER

Bazarr does not call the database directly.

Instead it uses a provider plugin:

subsdump.py

The provider translates Bazarr search requests into API calls.

Example flow:

Bazarr searches for a movie subtitle

Bazarr calls provider

Provider calls:

/api/v1/subtitles/search

The provider receives results and returns them in a format Bazarr understands.

--------------------------------------------------

WHY RELEASE MATCHING MATTERS

Bazarr provides the video filename to the provider.

Example:

Edge.of.Tomorrow.2014.REMUX.mkv

This release name is forwarded to the API.

The API uses it to score subtitle results based on release similarity.

This improves subtitle synchronization accuracy.

--------------------------------------------------

WEB USER INTERFACE

The web interface allows direct browsing of subtitles without Bazarr.

Features:

- search movies
- browse subtitle languages
- view subtitle pages
- download subtitle ZIP files

Example routes:

/movie/tt1631867
/movie/tt1631867/arabic
/subtitle/about-time/arabic/870894

--------------------------------------------------

COMPONENT SUMMARY

Database
Stores subtitle metadata and references to ZIP files.

Backend API
Search engine and download server.

Bazarr Provider
Integration layer between Bazarr and SubsDump.

Frontend
Optional user interface for manual browsing.

--------------------------------------------------

DESIGN GOALS

The architecture focuses on:

- self-hosting
- high search speed
- compatibility with Bazarr
- simple deployment
- minimal external dependencies

--------------------------------------------------

FUTURE EXTENSIONS

Possible improvements:

- distributed subtitle mirrors
- better release similarity scoring
- TV episode matching improvements
- caching layer
- API rate limiting
- multi-provider support
