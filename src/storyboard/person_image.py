from __future__ import annotations

from pathlib import Path

import httpx

from src.utils.config import env
from src.utils.logger import logger

_WIKI_API = "https://en.wikipedia.org/w/api.php"
_HEADERS = {"User-Agent": "ShortsBot/1.0 (https://github.com/shorts-bot; sidr3d@gmail.com)"}


def fetch_person_image(name: str, output_path: Path) -> bool:
    """Try to get a real photo of `name`. Priority: Wikipedia → Google CSE.

    Returns True and writes image to output_path on success; False otherwise.
    """
    if output_path.exists():
        logger.info(f"Person image cached: {output_path.name}")
        return True

    if _try_wikipedia(name, output_path):
        return True

    if _try_google_cse(name, output_path):
        return True

    logger.info(f"No real photo found for '{name}' — will use AI generation")
    return False


# ── Wikipedia ─────────────────────────────────────────────────────────────────

def _try_wikipedia(name: str, output_path: Path) -> bool:
    try:
        img_url = _wiki_image_url(name)

        if not img_url:
            # Try a full-text search and pick the best hit
            r = httpx.get(
                _WIKI_API,
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": name,
                    "format": "json",
                    "srlimit": 5,
                },
                headers=_HEADERS,
                timeout=15,
            )
            r.raise_for_status()
            for hit in r.json()["query"]["search"]:
                img_url = _wiki_image_url(hit["title"])
                if img_url:
                    break

        if not img_url:
            logger.info(f"Wikipedia: no image found for '{name}'")
            return False

        img = httpx.get(img_url, timeout=30, follow_redirects=True, headers=_HEADERS)
        img.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(img.content)
        logger.info(
            f"Wikipedia photo saved for '{name}': {output_path.name} "
            f"({len(img.content) // 1024} KB)"
        )
        return True

    except Exception as e:
        logger.warning(f"Wikipedia fetch failed for '{name}': {e}")
        return False


def _wiki_image_url(title: str) -> str | None:
    """Return the best thumbnail URL for a Wikipedia page title, or None."""
    try:
        r = httpx.get(
            _WIKI_API,
            params={
                "action": "query",
                "titles": title,
                "prop": "pageimages",
                "format": "json",
                "pithumbsize": 800,
                "pilimit": 1,
            },
            headers=_HEADERS,
            timeout=15,
        )
        r.raise_for_status()
        pages = r.json()["query"]["pages"]
        page = next(iter(pages.values()))
        if str(list(pages.keys())[0]) == "-1":
            return None
        thumb = page.get("thumbnail")
        return thumb["source"] if thumb else None
    except Exception:
        return None


# ── Google Custom Search (optional — needs GOOGLE_CSE_API_KEY + GOOGLE_CSE_ID) ─

def _try_google_cse(name: str, output_path: Path) -> bool:
    api_key = env("GOOGLE_CSE_API_KEY", default="")
    cse_id = env("GOOGLE_CSE_ID", default="")
    if not api_key or not cse_id:
        return False

    try:
        r = httpx.get(
            "https://www.googleapis.com/customsearch/v1",
            params={
                "key": api_key,
                "cx": cse_id,
                "q": f"{name} politician India photo",
                "searchType": "image",
                "imgType": "face",
                "num": 3,
                "safe": "active",
            },
            timeout=15,
        )
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            return False

        for item in items:
            try:
                img_url = item["link"]
                img = httpx.get(img_url, timeout=20, follow_redirects=True)
                img.raise_for_status()
                if len(img.content) < 5000:
                    continue
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(img.content)
                logger.info(
                    f"Google CSE photo saved for '{name}': {output_path.name} "
                    f"({len(img.content) // 1024} KB)"
                )
                return True
            except Exception:
                continue

        return False

    except Exception as e:
        logger.warning(f"Google CSE fetch failed for '{name}': {e}")
        return False
