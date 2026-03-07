import io
import logging
import os
import zipfile

from urllib.parse import urljoin, urlparse

import requests
from requests import Session

from babelfish import Language as BabelLanguage
from subzero.language import Language
from subliminal import Episode, Movie
from subliminal_patch.subtitle import Subtitle
from subliminal.subtitle import fix_line_ending
from subliminal_patch.providers import Provider
from subliminal_patch.providers import utils

logger = logging.getLogger(__name__)

_LANG_FALLBACK = {
    "ara": "arabic",
    "eng": "english",
    "fra": "french",
    "deu": "german",
    "spa": "spanish",
    "ita": "italian",
    "por": "portuguese",
    "rus": "russian",
    "tur": "turkish",
    "jpn": "japanese",
    "kor": "korean",
    "zho": "chinese-bg-code",
    "hin": "hindi",
    "nld": "dutch",
    "swe": "swedish",
    "dan": "danish",
    "fin": "finnish",
    "ell": "greek",
    "pol": "polish",
    "ces": "czech",
    "ron": "romanian",
    "heb": "hebrew",
    "fas": "farsi_persian",
    "urd": "urdu",
    "ind": "indonesian",
    "vie": "vietnamese",
    "mal": "malayalam",
    "ben": "bengali",
    "tha": "thai",
    "hun": "hungarian",
    "nor": "norwegian",
}

_BASE_LANGS = tuple(_LANG_FALLBACK.keys())


def _normalize_api_base(url: str) -> str:
    url = (url or "").strip()
    if not url:
        url = "https://subs.d3lphi3r.com"

    url = url.rstrip("/")

    if url.endswith("/api/v1"):
        return url + "/"

    return url + "/api/v1/"


def _site_root_from_api(api_url: str) -> str:
    p = urlparse(api_url)
    return f"{p.scheme}://{p.netloc}"


def _lang_to_api_name(lang: Language):
    alpha3 = getattr(lang, "alpha3", None)
    if not alpha3:
        return None

    try:
        name = BabelLanguage.fromalpha3(alpha3).name.lower()
    except Exception:
        name = _LANG_FALLBACK.get(alpha3)

    if not name:
        return None

    special = {
        "persian": "farsi_persian",
        "brazilian portuguese": "brazillian-portuguese",
        "brazilian-portuguese": "brazillian-portuguese",
        "norwegian bokmal": "norwegian",
        "norwegian nynorsk": "norwegian",
        "chinese": "chinese-bg-code",
    }

    return special.get(name, name.replace(" ", "-"))


def _safe_imdb(video):
    imdb_id = ""
    if isinstance(video, Episode):
        imdb_id = getattr(video, "series_imdb_id", None) or getattr(video, "imdb_id", None) or ""
    else:
        imdb_id = getattr(video, "imdb_id", None) or ""

    imdb_id = str(imdb_id).strip()
    if not imdb_id:
        return ""

    if imdb_id.isdigit():
        return "tt" + imdb_id

    if imdb_id.startswith("tt"):
        return imdb_id

    stripped = imdb_id.replace("tt", "")
    if stripped.isdigit():
        return "tt" + stripped

    return imdb_id


def _safe_release_name(video):
    for attr in ("release_info", "original_name", "name"):
        v = getattr(video, attr, None)
        if isinstance(v, str) and v.strip():
            return v.strip()

    if isinstance(video, Episode):
        parts = []
        if getattr(video, "series", None):
            parts.append(str(video.series))
        if getattr(video, "season", None) is not None and getattr(video, "episode", None) is not None:
            parts.append("S%02dE%02d" % (video.season, video.episode))
        return ".".join(parts).strip(".")

    title = getattr(video, "title", None) or ""
    year = getattr(video, "year", None)
    if title and year:
        return f"{title}.{year}"
    return str(title).strip()


class SubsDumpSubtitle(Subtitle):
    provider_name = "subsdump"
    hash_verifiable = False
    hearing_impaired_verifiable = True

    def __init__(
        self,
        language,
        forced,
        hearing_impaired,
        subtitle_id,
        page_link,
        download_link,
        release_names,
        uploader,
        season=None,
        episode=None,
        comment="",
    ):
        super().__init__(language)
        language = Language.rebuild(language, hi=hearing_impaired, forced=forced)

        self.language = language
        self.forced = forced
        self.hearing_impaired = hearing_impaired

        self.subtitle_id = int(subtitle_id)
        self.page_link = page_link
        self.download_link = download_link

        self.release_names = release_names or []
        self.release_info = ", ".join([str(x).strip() for x in self.release_names if str(x).strip()])
        self.uploader = uploader or ""
        self.comment = comment or ""

        self.season = season
        self.episode = episode
        self.matches = None

    @property
    def id(self):
        return str(self.subtitle_id)

    def get_matches(self, video):
        matches = set()

        if isinstance(video, Episode):
            matches.add("series")

            if self.season is not None and getattr(video, "season", None) == self.season:
                matches.add("season")

            if self.episode is not None and getattr(video, "episode", None) == self.episode:
                matches.add("episode")

            if getattr(video, "series_imdb_id", None):
                matches.add("series_imdb_id")
        else:
            if getattr(video, "title", None):
                matches.add("title")
            if getattr(video, "imdb_id", None):
                matches.add("imdb_id")

        if getattr(video, "year", None):
            matches.add("year")

        if self.release_info:
            try:
                utils.update_matches(matches, video, self.release_info)
            except Exception as e:
                logger.debug("subsdump: update_matches failed for %r: %s", self.release_info, e)

        self.matches = matches
        return matches


class SubsDumpProvider(Provider):
    provider_name = "subsdump"
    video_types = (Episode, Movie)

    languages = set()
    for _a3 in _BASE_LANGS:
        try:
            _base = Language(_a3)
            languages.add(_base)
            languages.add(Language.rebuild(_base, hi=True))
            languages.add(Language.rebuild(_base, forced=True))
            languages.add(Language.rebuild(Language.rebuild(_base, hi=True), forced=True))
        except Exception:
            pass

    def __init__(self, api_key=None, api_url=None, **kwargs):
        self.api_key = (api_key or os.getenv("SUBSDUMP_API_KEY", "")).strip()
        self.api_v1 = _normalize_api_base(
            api_url or os.getenv("SUBSDUMP_API_URL", "") or "https://subs.d3lphi3r.com"
        )
        self.site_root = _site_root_from_api(self.api_v1)

        self.session = Session()
        self.session.headers = {
            "Accept": "application/json",
            "User-Agent": os.environ.get("SZ_USER_AGENT", "Sub-Zero/2"),
        }
        if self.api_key:
            self.session.headers.update({"X-API-Key": self.api_key})

    def initialize(self):
        return

    def terminate(self):
        self.session.close()

    @staticmethod
    def _is_hi(item):
        text = " ".join([
            str(item.get("comment") or ""),
            " ".join(item.get("releases") or []) if isinstance(item.get("releases"), list) else str(item.get("releases") or ""),
            str(item.get("fileLink") or ""),
            str(item.get("download_url") or ""),
        ]).lower()

        non_hi_tags = ["hi remove", "non hi", "nonhi", "non-hi", "non-sdh", "non sdh", "nonsdh", "sdh remove"]
        if any(tag in text for tag in non_hi_tags):
            return False

        hi_tags = ["_hi_", " hi ", ".hi.", "hi_", "_hi", "sdh", "hearing impaired", "hearing-impaired"]
        return any(tag in text for tag in hi_tags)

    @staticmethod
    def _is_forced(item):
        text = " ".join([
            str(item.get("comment") or ""),
            " ".join(item.get("releases") or []) if isinstance(item.get("releases"), list) else str(item.get("releases") or ""),
        ]).lower()
        return any(tag in text for tag in ("forced", "foreign"))

    def _search(self, imdb_id, lang_name, release, video):
        url = urljoin(self.api_v1, "subtitles/search")
        params = {
            "imdb": imdb_id,
            "lang": lang_name,
            "release": release,
            "q": release,
            "limit": 50,
        }

        if isinstance(video, Episode):
            season = getattr(video, "season", None)
            episode = getattr(video, "episode", None)
            if season is not None:
                params["season"] = season
            if episode is not None:
                params["episode"] = episode

        logger.debug("subsdump: GET %s params=%r", url, params)

        r = self.session.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json() or {}
        return list(data.get("results") or [])

    def query(self, languages, video):
        imdb_id = _safe_imdb(video)
        if not imdb_id:
            logger.debug("subsdump: no imdb id on video, skipping")
            return []

        release = _safe_release_name(video)
        subtitles = []

        for lang in languages:
            lang_name = _lang_to_api_name(lang)
            if not lang_name:
                logger.debug("subsdump: unsupported language object=%r alpha3=%r", lang, getattr(lang, "alpha3", None))
                continue

            try:
                results = self._search(imdb_id=imdb_id, lang_name=lang_name, release=release, video=video)
            except Exception as e:
                logger.warning(
                    "subsdump: search failed imdb=%s lang=%s release=%s err=%s",
                    imdb_id, lang_name, release, e
                )
                continue

            for item in results:
                sid = item.get("id")
                dl = item.get("download_url") or ""
                if not sid or not dl:
                    continue

                releases = item.get("releases") or []
                if not isinstance(releases, list):
                    releases = [str(releases)] if releases else []

                page_link = item.get("subscene_link") or ""
                if page_link:
                    page_link = urljoin(self.site_root + "/", "subtitle/" + str(page_link).lstrip("/"))

                subtitle = SubsDumpSubtitle(
                    language=Language.rebuild(lang, forced=self._is_forced(item), hi=self._is_hi(item)),
                    forced=self._is_forced(item),
                    hearing_impaired=self._is_hi(item),
                    subtitle_id=int(sid),
                    page_link=page_link,
                    download_link=str(dl),
                    release_names=releases,
                    uploader=item.get("author_name") or "",
                    season=item.get("season"),
                    episode=item.get("episode"),
                    comment=item.get("comment") or "",
                )

                subtitle.get_matches(video)

                if subtitle.language in languages:
                    subtitles.append(subtitle)

        return subtitles

    def list_subtitles(self, video, languages):
        return self.query(languages, video)

    def download_subtitle(self, subtitle):
        logger.debug("Downloading subtitle %r", subtitle)

        dl = subtitle.download_link or ""
        if dl.startswith("http://") or dl.startswith("https://"):
            url = dl
        elif dl.startswith("/"):
            url = f"{self.site_root.rstrip('/')}{dl}"
        else:
            url = f"{self.api_v1.rstrip('/')}/{dl.lstrip('/')}"

        r = self.session.get(url, timeout=60)
        r.raise_for_status()

        if not r:
            subtitle.content = None
            return

        archive_stream = io.BytesIO(r.content)
        content = None

        try:
            with zipfile.ZipFile(archive_stream) as archive:
                names = archive.namelist()
                candidates = []
                for name in names:
                    ln = name.lower()
                    if ln.endswith(".srt") or ln.endswith(".ass") or ln.endswith(".ssa") or ln.endswith(".sub"):
                        candidates.append(name)

                if not candidates and names:
                    candidates = names[:]

                if candidates:
                    content = archive.read(candidates[0])
        except Exception:
            content = r.content

        subtitle.content = fix_line_ending(content) if content else None
