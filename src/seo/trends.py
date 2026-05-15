from __future__ import annotations

import dataclasses

import requests
from pytrends.request import TrendReq

from src.seo.models import SeoMetadata
from src.utils.logger import logger


def _score_keywords(keywords: list[str]) -> dict[str, int]:
    scores: dict[str, int] = {}
    try:
        pt = TrendReq(hl="en-US", tz=330)
        for i in range(0, len(keywords), 5):
            batch = keywords[i : i + 5]
            try:
                pt.build_payload(batch, timeframe="now 7-d")
                df = pt.interest_over_time()
                for kw in batch:
                    if kw in df.columns:
                        scores[kw] = int(df[kw].mean())
            except Exception as exc:
                logger.warning(f"pytrends batch {batch} failed: {exc}")
    except Exception as exc:
        logger.warning(f"pytrends init failed: {exc}")
    return scores


def _youtube_autocomplete(query: str, language: str) -> list[str]:
    lang_code = "hi" if language == "hindi" else "en"
    try:
        r = requests.get(
            "https://suggestqueries.google.com/complete/search",
            params={"client": "youtube", "q": query, "hl": lang_code},
            timeout=5,
        )
        r.raise_for_status()
        suggestions = r.json()[1]
        return [s[0] for s in suggestions]
    except Exception as exc:
        logger.warning(f"YouTube autocomplete failed: {exc}")
        return []


def enrich(metadata: SeoMetadata, topic_hint: str, language: str) -> SeoMetadata:
    try:
        title_tokens = [w.lower() for w in metadata.title.split() if len(w) > 3]
        tag_tokens = [h.lstrip("#") for h in metadata.hashtags[:10]]
        candidates = list(dict.fromkeys(title_tokens + tag_tokens))

        scores = _score_keywords(candidates)

        def _rank(tag: str) -> int:
            score = scores.get(tag.lstrip("#").lower(), -1)
            if score >= 40:
                return 0
            if score >= 1:
                return 1
            return 2

        ranked = sorted(metadata.hashtags, key=_rank)

        existing = {h.lstrip("#").lower() for h in ranked}
        injected = 0
        for suggestion in _youtube_autocomplete(topic_hint, language):
            if injected >= 5:
                break
            normalized = suggestion.lower()
            if normalized not in existing:
                ranked.append("#" + suggestion.replace(" ", "").lower())
                existing.add(normalized)
                injected += 1

        return dataclasses.replace(metadata, hashtags=ranked)

    except Exception as exc:
        logger.warning(f"Trending enrichment failed, returning unchanged: {exc}")
        return metadata
