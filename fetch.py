"""Polite, cached HTTP fetching for pa.liftingdatabase.com.

Every page is cached under raw_html/ so re-parsing/re-loading costs no network,
and the crawl is safe to stop and resume.
"""
from __future__ import annotations

import os
import time
import pathlib
import hashlib

import requests
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

load_dotenv()

BASE_URL = os.getenv("BASE_URL", "https://pa.liftingdatabase.com").rstrip("/")
DELAY = float(os.getenv("SCRAPE_DELAY_SECONDS", "1.0"))
CACHE_DIR = pathlib.Path(__file__).parent / "raw_html"
CACHE_DIR.mkdir(exist_ok=True)

_SESSION = requests.Session()
_SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }
)

_last_request = 0.0


def _cache_path(key: str, ext: str = "html") -> pathlib.Path:
    safe = key.replace("/", "_").replace("?", "_").replace("=", "_").replace("&", "_")
    if len(safe) > 120:
        safe = safe[:80] + "_" + hashlib.md5(key.encode()).hexdigest()[:12]
    return CACHE_DIR / f"{safe}.{ext}"


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type((requests.RequestException,)),
    reraise=True,
)
def _http_get(url: str) -> str:
    global _last_request
    elapsed = time.monotonic() - _last_request
    if elapsed < DELAY:
        time.sleep(DELAY - elapsed)
    resp = _SESSION.get(url, timeout=30)
    _last_request = time.monotonic()
    resp.raise_for_status()
    return resp.text


def get(path: str, *, cache_key: str | None = None, ext: str = "html",
        force: bool = False) -> str:
    """Fetch BASE_URL/path, using the on-disk cache unless force=True.

    path may be a full URL or a site-relative path like 'competitions-view?id=899'.
    """
    url = path if path.startswith("http") else f"{BASE_URL}/{path.lstrip('/')}"
    key = cache_key or (path if not path.startswith("http") else url)
    cpath = _cache_path(key, ext)
    if not force and cpath.exists():
        return cpath.read_text(encoding="utf-8")
    text = _http_get(url)
    cpath.write_text(text, encoding="utf-8")
    return text


def competition(comp_id: int, force: bool = False) -> str:
    return get(f"competitions-view?id={comp_id}", cache_key=f"comp_{comp_id}", force=force)


def lifter(lifter_id: int, force: bool = False) -> str:
    return get(f"lifters-view?id={lifter_id}", cache_key=f"lifter_{lifter_id}", force=force)


def team(team_id: int, force: bool = False) -> str:
    return get(f"clubs-view?id={team_id}", cache_key=f"team_{team_id}", force=force)


def competition_list(force: bool = False) -> str:
    return get("competitions", cache_key="competition_list", force=force)


def records_csv(sex: str, force: bool = False) -> str:
    assert sex in ("m", "f")
    return get(f"records-allCSV?sex={sex}", cache_key=f"records_{sex}", ext="csv", force=force)
