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
    """LLM plans 8-12 scene beats with image prompts for FLUX."""
    model = env("OPENROUTER_MODEL", default="google/gemini-2.0-flash-001")
    client = _build_client()
    duration_ms = int(duration_sec * 1000)
    target_scenes = max(6, min(12, round(duration_sec / 6.5)))

    logger.info(f"Planning {target_scenes} scenes for {duration_sec:.1f}s via {model}")

    prompt = f"""You are a documentary YouTube Shorts visual director. Your style references: Hoog, Vox, Vice News.

## Approved script
{script_text}

## Audio duration
{duration_sec:.1f} seconds ({duration_ms}ms)

## Task
Break this script into exactly {target_scenes} scene beats. Together they MUST cover all {duration_ms}ms, with no gaps.

For each beat, write a SPECIFIC photorealistic image prompt for FLUX AI image generation. Each prompt must include:
- A specific concrete subject (NOT generic — name the place, object, action, or scene)
- Setting/location (e.g., "war room", "city street at dusk", "mountain pass")
- Lighting & mood (e.g., "dramatic chiaroscuro", "harsh midday sun", "neon-lit rain")
- Camera angle (e.g., "low-angle hero shot", "overhead drone view", "shallow depth of field")
- Style descriptors: "cinematic", "documentary photography", "9:16 portrait composition", "Hoog channel aesthetic", "moody color grading"

CRITICAL rules:
- Avoid showing identifiable real people's faces (use silhouettes, hands, backs, crowds, partial figures)
- Avoid logos, brand names, copyrighted symbols
- Be visually concrete — bad: "tension rising". Good: "smoke rising from a destroyed police station at dusk, debris in foreground"
- Vary scenes — maps, locations, objects, abstract symbolism, dramatic moments. Don't repeat similar shots.
- Mix scene types: establishing shot → close-up detail → wide → object → location → human silhouette

Motion for each beat — one of:
- "zoom_in"  — slow push toward subject (use for revelations, tension building)
- "zoom_out" — slow pull back (use for context, scope reveals)
- "pan_left" / "pan_right" — horizontal slide (use for landscapes, transitions)
- "static"   — no motion (use sparingly, only for impactful single shots)

## Output (JSON only, no other text)
{{
  "scenes": [
    {{"start_ms": 0, "end_ms": 4000, "prompt": "...", "motion": "zoom_in"}},
    {{"start_ms": 4000, "end_ms": 8500, "prompt": "...", "motion": "pan_right"}},
    ...
  ]
}}"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85,
        max_tokens=2500,
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
