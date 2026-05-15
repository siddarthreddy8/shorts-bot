from __future__ import annotations

import json

from openai import OpenAI

from src.seo.models import SeoMetadata
from src.utils.config import env
from src.utils.logger import logger

_SYSTEM = (
    "You are an expert YouTube/TikTok/Reels SEO strategist. You deeply analyze "
    "short-form video scripts and generate high-performing metadata that real users "
    "actively search for. Never use generic tags. Every keyword must be directly "
    "traceable to the script's specific topic, emotion, or hook."
)

_PROMPT_PREFIX = """\
## Script
"""

_PROMPT_SUFFIX = """\


## Context
- Language: {language}
- Style: {styles}
- Target platform: YouTube Shorts (also optimized for TikTok/Reels)
- Source topic: {topic_hint}

## Task
Step 1 — Analyze the script:
  * Main topic and sub-topics
  * Key named entities (people, places, events, brands)
  * Dominant emotion and audience intent
  * Viral hook pattern used
  * Niche (news, history, tech, crime, etc.)

Step 2 — Generate metadata:
  * title: attention-grabbing, 60 chars max, strongest keyword first
  * description: 150-200 words, natural language, secondary and long-tail keywords
    woven in, ends with CTA linking to original video
  * hashtags: list of 15-20 — broad (3), niche (10), trending-adjacent (5-7);
    no spaces inside tags
  * thumbnail_phrases: 3 short options 6 words max each, high shock/curiosity value
  * niche: single word or short phrase for content category

Return ONLY valid JSON — no markdown, no explanation:
{{
  "title": "...",
  "description": "...",
  "hashtags": ["...", "..."],
  "thumbnail_phrases": ["...", "...", "..."],
  "niche": "..."
}}"""


def _make_client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=env("OPENROUTER_API_KEY", required=True),
    )


def _parse(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


def generate(
    script: str,
    topic_hint: str,
    styles: list[str],
    language: str,
) -> SeoMetadata:
    client = _make_client()
    model = env("AI_MODEL", default="anthropic/claude-sonnet-4-6")
    user_msg = (
        _PROMPT_PREFIX
        + script
        + _PROMPT_SUFFIX.format(
            language=language,
            styles=", ".join(styles),
            topic_hint=topic_hint,
        )
    )
    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user_msg},
    ]

    last_raw = ""
    for attempt in range(2):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
        )
        last_raw = resp.choices[0].message.content or ""
        try:
            data = _parse(last_raw)
            return SeoMetadata(
                title=data["title"],
                description=data["description"],
                hashtags=data["hashtags"],
                thumbnail_phrases=data["thumbnail_phrases"],
                niche=data["niche"],
            )
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning(f"SEO analyzer bad JSON on attempt {attempt + 1}: {exc}")
            if attempt == 0:
                messages.append({"role": "assistant", "content": last_raw})
                messages.append({
                    "role": "user",
                    "content": "Return ONLY valid JSON matching the schema above. No extra text.",
                })

    raise ValueError(
        f"SEO analyzer failed after 2 attempts. Last response: {last_raw[:200]}"
    )
