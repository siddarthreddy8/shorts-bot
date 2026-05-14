from __future__ import annotations

import json
import re
from typing import Literal

from openai import OpenAI

from src.utils.config import env
from src.utils.logger import logger

MotionType = Literal["zoom_in", "zoom_out", "pan_left", "pan_right", "static"]


def _build_client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=env("OPENROUTER_API_KEY", required=True),
        default_headers={"HTTP-Referer": "https://github.com/shorts-bot"},
    )


def plan_scenes(script_text: str, duration_sec: float) -> list[dict]:
    """LLM plans scene beats with visual type grammar for political documentary style."""
    model = env("OPENROUTER_MODEL", default="anthropic/claude-3-5-haiku")
    client = _build_client()
    duration_ms = int(duration_sec * 1000)
    # 2–5s average cut for political documentary rhythm
    target_scenes = max(15, min(50, round(duration_sec / 4)))

    logger.info(f"Planning {target_scenes} scenes for {duration_sec:.1f}s via {model}")

    prompt = f"""You are a political documentary YouTube Shorts visual director. Style references: Hoog, Vox, Vice News, DW Documentary.

## Approved script
{script_text}

## Audio duration
{duration_sec:.1f} seconds ({duration_ms}ms)

## Task
Break this script into exactly {target_scenes} visual scene beats. Together they MUST cover all {duration_ms}ms with no gaps. Target 2–5 seconds per scene — short, punchy cuts that match the spoken rhythm.

For each scene:

### VISUAL TYPE — pick the most appropriate for the content at that moment
- "map"       — geographic territory, borders, routes, satellite overview. Use when mentioning countries, regions, conflicts, trade routes.
- "headline"  — news chyron, newspaper front page, TV broadcast screen, breaking news graphic. Use when citing events or announcements.
- "satellite" — aerial/drone view of a specific location, military installation, city district. Use for location establishing shots.
- "graph"     — data chart, economic graph, infographic, statistics display. Use when citing numbers, growth, decline.
- "flag"      — nation's flag, bilateral summit, diplomatic meeting exterior. Use for country-to-country relations.
- "crowd"     — street protest, political rally, parliament session, public gathering. Use for public reaction or mass events.
- "document"  — treaty signing, classified file, official letter, UN resolution paper. Use for agreements or official decisions.
- "portrait"  — a named politician, leader, or public figure being discussed at this exact moment. Use whenever the script names a specific real person.
- "footage"   — cinematic recreation of the key moment: street scene, military movement, port, factory floor, convoy. Use for action beats.

### PORTRAIT scenes — IMPORTANT
When the script mentions a specific real person by name (politician, minister, party leader), use visual_type "portrait" and add a "subject_name" field with their full commonly-known English name.
- Use "subject_name": "Mamata Banerjee" (not "Chief Minister" or "the minister")
- Use "subject_name": "" only for generic/anonymous figures with no named individual

### VISUAL PROMPT rules
- Be concrete: name the place, object, or scene. Bad: "tension rising". Good: "smoke rising from port of Karachi, container ships in background, dusk light"
- For portrait scenes: describe the setting or context around the person, not their face — the real photo will be sourced separately
- Include: lighting & mood · camera angle · "9:16 portrait composition" · "cinematic documentary" · "Hoog channel aesthetic"
- Avoid logos, brand names, copyrighted symbols
- Vary the sequence — alternate wide establishing shots with tight detail/evidence shots
- Match visual type to script content at that exact moment

### MOTION — one of:
- "zoom_in"   — slow push toward subject (revelations, tension build)
- "zoom_out"  — slow pull back (context, scope reveals)
- "pan_left" / "pan_right" — horizontal sweep (landscapes, transitions)
- "static"    — no motion (use sparingly, for maximum impact stills)

## Output (JSON only, no other text)
{{
  "scenes": [
    {{"start_ms": 0, "end_ms": 3500, "prompt": "...", "motion": "zoom_in", "visual_type": "map", "subject_name": ""}},
    {{"start_ms": 3500, "end_ms": 7000, "prompt": "...", "motion": "static", "visual_type": "portrait", "subject_name": "Mamata Banerjee"}},
    {{"start_ms": 7000, "end_ms": 10500, "prompt": "...", "motion": "pan_right", "visual_type": "headline", "subject_name": ""}},
    ...
  ]
}}"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
        max_tokens=4000,
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"LLM returned non-JSON: {raw[:300]}")
        data = json.loads(match.group())

    scenes = data.get("scenes", [])
    scenes = _normalise_timing(scenes, duration_ms)
    logger.info(f"Planned {len(scenes)} scenes")
    return scenes


def _normalise_timing(scenes: list[dict], total_ms: int) -> list[dict]:
    """Ensure scenes cover [0, total_ms] continuously without gaps."""
    if not scenes:
        return []
    scenes = sorted(scenes, key=lambda s: s["start_ms"])
    # Stitch any gaps closed; clamp to total_ms.
    for i, s in enumerate(scenes):
        if i == 0:
            s["start_ms"] = 0
        else:
            s["start_ms"] = scenes[i - 1]["end_ms"]
        if i == len(scenes) - 1:
            s["end_ms"] = total_ms
        s["start_ms"] = max(0, s["start_ms"])
        s["end_ms"] = min(total_ms, s["end_ms"])
    return [s for s in scenes if s["end_ms"] > s["start_ms"]]
