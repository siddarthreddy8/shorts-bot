from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAI

from src.db.database import get_conn, log_event
from src.utils.config import env, project_root
from src.utils.logger import logger

_SCRIPTS_DIR = project_root() / "data" / "scripts"
_SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

_STYLE_PROMPTS: dict[str, str] = {
    "documentary": (
        "Calm, authoritative narrator — think BBC/Vice. "
        "Use a 3-act arc: establish the world → introduce the rupture → deliver the revelation. "
        "Short declarative sentences. No hedging. Build to one sharp insight."
    ),
    "comedy": (
        "Sharp wit, not slapstick. Land one unexpected analogy or absurd comparison "
        "that makes the key point land harder. Short rhythm — long sentence, SHORT sentence. "
        "Build to a punchline in the last body line."
    ),
    "serious": (
        "Every sentence is a headline. Clipped, grave, no filler. "
        "Lead with the most alarming fact. Make the stakes feel immediate and personal. "
        "End with the consequence that keeps the viewer up at night."
    ),
    "storytelling": (
        "Drop the viewer INTO a moment using present tense and specific detail — "
        "name places, times, roles. Build tension through concrete specifics, not abstractions. "
        "The final sentence should feel like a door swinging open."
    ),
    "explainer": (
        "Teach one thing exceptionally well. Open with: here's what everyone assumes — "
        "then flip it with what's actually true. One sharp analogy. One clear so-what. "
        "No jargon, no hedging."
    ),
    "sarcastic": (
        "Lead with the absurdity. Find the one detail that makes this situation darkly funny. "
        "Maintain a dry, deadpan tone — never wink at the camera. "
        "The real insight lands harder because of the sardonic frame."
    ),
}


@dataclass
class GeneratedScript:
    video_id: str
    language: str
    styles: list[str]
    hooks: list[str]
    body: str
    cta: str
    full_script: str
    word_count: int
    script_path: Path


def _build_client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=env("OPENROUTER_API_KEY", required=True),
        default_headers={"HTTP-Referer": "https://github.com/shorts-bot"},
    )


def _style_instruction(styles: list[str]) -> str:
    parts = [_STYLE_PROMPTS.get(s, "") for s in styles if s in _STYLE_PROMPTS]
    if not parts:
        return _STYLE_PROMPTS["documentary"]
    if len(parts) == 1:
        return parts[0]
    return (
        "Blend these styles naturally — "
        + " AND ".join(f"[{s.upper()}: {p}]" for s, p in zip(styles, parts))
    )


def generate(
    video_id: str,
    telugu_transcript: str,
    language: str = "english",
    styles: list[str] | None = None,
) -> GeneratedScript:
    if styles is None:
        styles = ["documentary"]

    script_path = _SCRIPTS_DIR / f"{video_id}_draft.json"
    if script_path.exists():
        logger.info(f"Draft script already exists: {script_path}")
        data = json.loads(script_path.read_text(encoding="utf-8"))
        return GeneratedScript(**data, script_path=script_path)

    model = env("OPENROUTER_MODEL", default="google/gemini-flash-1.5")
    client = _build_client()
    style_instr = _style_instruction(styles)
    lang_name = "Hindi" if language == "hindi" else "English"

    logger.info(f"Generating script for {video_id} | lang={lang_name} | styles={styles} | model={model}")

    prompt = f"""You are a viral YouTube Shorts scriptwriter. Transform the Telugu transcript below into a {lang_name} Short that earns maximum watch-time and re-watches.

## Source Transcript (Telugu)
{telugu_transcript[:4000]}

## Style
{style_instr}

## HOOKS — write exactly 3, each using a DIFFERENT framework

Hook 1 — CURIOSITY GAP: Withhold one key fact. Force the viewer to keep watching to resolve the open question.
Hook 2 — COUNTERINTUITIVE: Flip the obvious assumption. Make the viewer think "wait, that can't be right."
Hook 3 — STAKES/CONSEQUENCE: Make the impact feel immediate. What just changed, or is about to?

Hook rules (apply to all 3):
- Maximum 10 words
- Strong active verb — no "is", "was", "are" as the main verb
- No clickbait phrases ("you won't believe", "shocking", "mind-blowing")
- Each hook must be genuinely different — not the same idea rephrased

## BODY — use this 5-part arc (65–95 words total)

1. SETUP (1–2 sentences): Establish the world. Who, where, what was assumed to be true.
2. RUPTURE (1–2 sentences): What broke that assumption. The event or revelation.
3. ESCALATION (1–2 sentences): Why this matters more than it first appears. Raise the stakes.
4. TWIST (1 sentence): The sharpest insight — the thing most people haven't connected yet.
5. CALLBACK (1 sentence): Echo the hook. This plants the re-watch impulse — the viewer wants to go back and hear the hook again knowing what they now know.

Body rules:
- Output language: {lang_name}
- ORIGINAL rewrite — do not translate directly, less than 30% word overlap with source
- Short sentences hit harder than long ones
- Specific details (names, places, numbers) beat vague generalisations
- No filler phrases ("it's important to note", "in conclusion", "as we can see")

## HARD LIMIT — WORD COUNT
The hook (≤10 words) + body (65–95 words) + CTA (8 words) must total UNDER 115 words.
Count every word before outputting. YouTube Shorts cuts off at 58 seconds — at 2.5 words/sec, 115 words = 46 seconds leaving 12 seconds for natural pauses and pacing.
If your draft exceeds 115 words, cut the least-essential sentence and try again.

## CTA
One sentence asking viewers to comment their opinion on what just happened. Make it feel like a genuine question, not a generic prompt. Tie it directly to the story — reference a specific person, place, or outcome from the body. Output language: {lang_name}.

## Output Format (JSON only, no other text)
{{
  "hooks": ["hook 1", "hook 2", "hook 3"],
  "body": "the full body text here",
  "cta": "Watch the full video — link in description."
}}"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=800,
    )

    raw = response.choices[0].message.content.strip()
    logger.debug(f"Raw LLM response: {raw[:200]}")

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON — attempting recovery")
        data = _recover_json(raw)

    hooks: list[str] = data.get("hooks", [])[:3]
    body: str = data.get("body", "").strip()
    cta: str = data.get("cta", "आपकी क्या राय है? नीचे कमेंट करें।")

    # Full script uses hook[0] by default; user picks in review UI
    full_script = f"{hooks[0]}\n\n{body}\n\n{cta}" if hooks else f"{body}\n\n{cta}"
    word_count = len(full_script.split())

    result_data = {
        "video_id": video_id,
        "language": language,
        "styles": styles,
        "hooks": hooks,
        "body": body,
        "cta": cta,
        "full_script": full_script,
        "word_count": word_count,
    }

    script_path.write_text(
        json.dumps(result_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info(f"Script saved: {script_path} ({word_count} words)")

    with get_conn() as conn:
        conn.execute(
            "UPDATE videos SET status='script_drafted', target_language=?, styles_json=?, "
            "script_word_count=?, updated_at=datetime('now') WHERE video_id=?",
            (language, json.dumps(styles), word_count, video_id),
        )
    log_event(video_id, "script", f"Script drafted ({word_count} words) via {model}")

    return GeneratedScript(**result_data, script_path=script_path)


def save_approved(video_id: str, hook: str, body: str, cta: str) -> Path:
    """Save the user-approved version after review UI edits."""
    approved_path = _SCRIPTS_DIR / f"{video_id}_approved.txt"
    approved_path.write_text(
        f"{hook}\n\n{body}\n\n{cta}",
        encoding="utf-8",
    )
    logger.info(f"Approved script saved: {approved_path}")
    return approved_path


def _recover_json(raw: str) -> dict:
    """Last-resort: try to extract JSON object from messy LLM output."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {"hooks": [], "body": raw, "cta": "Watch the full video — link in description."}
