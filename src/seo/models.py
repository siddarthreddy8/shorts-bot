from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SeoMetadata:
    title: str
    description: str
    hashtags: list[str]
    thumbnail_phrases: list[str]
    niche: str
    thumbnail_phrase: str | None = None
