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

    model = env("OPENROUTER_MODEL", default="anthropic/claude-3-5-haiku")
    client = _build_client()
    style_instr = _style_instruction(styles)
    lang_name = "Hindi" if language == "hindi" else "English"

    logger.info(f"Generating script for {video_id} | lang={lang_name} | styles={styles} | model={model}")

    prompt = f"""You are a documentary YouTube Shorts scriptwriter specialising in political short-form content. Transform the Telugu transcript below into a compelling {lang_name} 3-minute Short that earns maximum watch-time and re-watches.

## Source Transcript (Telugu)
{telugu_transcript[:4000]}

## Style
{style_instr}

## HOOKS — write exactly 3, each using a DIFFERENT framework

Hook 1 — CURIOSITY GAP: Withhold one key fact. Force the viewer to keep watching to resolve the open question.
Hook 2 — COUNTERINTUITIVE: Flip the obvious assumption. Make the viewer think "wait, that can't be right."
Hook 3 — STAKES/CONSEQUENCE: Make the impact feel immediate. What just changed, or is about to?

Hook rules (apply to all 3):
- Maximum 15 words
- Strong active verb — no "is", "was", "are" as the main verb
- No clickbait phrases ("you won't believe", "shocking", "mind-blowing")
- Each hook must be genuinely different — not the same idea rephrased

## BODY — use this 6-block structure (330–420 words total)

Each block covers roughly 25–35 seconds of spoken content (60–85 words at 2.5 words/sec). Write all blocks as one continuous narrative — no headers, no labels in the output.

1. CONTEXT (60–80 words): What is happening right now and why it matters. Establish the who, where, and the immediate stakes. Make it feel urgent and relevant today.
2. BACKGROUND (60–80 words): The hidden history or overlooked factor most people don't know. This reframes everything the viewer just heard. The "actually…" moment that changes the picture.
3. TURNING POINT (60–80 words): The key event, decision, or conflict that changed everything. Be specific — name dates, places, actors, decisions. This is the engine of the story.
4. IMPLICATION (60–80 words): What this means for India or the world. Connect the specific event to the larger consequence the viewer can feel. Make the weight land.
5. CLOSE (30–50 words): One strong takeaway or open loop. Either deliver the sharpest conclusion or leave a tension that makes the viewer think. Echo the hook phrase or image.

Body rules:
- Output language: {lang_name}
- ORIGINAL rewrite — do not translate directly, less than 30% word overlap with source
- Short declarative sentences. Vary rhythm — land a punchy short sentence after a longer one.
- Specific details (names, places, numbers, dates) beat vague generalisations
- No filler phrases ("it's important to note", "in conclusion", "as we can see")
- Flow naturally block to block — no transitions like "moving on" or "next"

## HARD LIMIT — WORD COUNT
Hook (≤15 words) + body (330–420 words) + CTA (≤15 words) must total 350–450 words.
At 2.5 words/sec: 350 words = 140 seconds, 450 words = 180 seconds (3 minutes).
Count every word before outputting. If draft exceeds 450 words, cut the least-essential sentences from Implication or Close. If under 350, expand Turning Point or Background with one more specific detail.

## CTA
Write ONE sentence that does three things in natural order:
1. Ask the viewer a specific opinion question tied to this story (reference a person, place, or outcome from the body — not generic)
2. Ask them to like and subscribe if they found it valuable
3. Tell them to comment their take below

Keep it conversational, not robotic. Output language: {lang_name}.
Example: "Do you think Sujit Bose's arrest signals real accountability or political revenge? Like and subscribe for more, and drop your take in the comments."

## Output Format (JSON only, no other text)
{{
  "hooks": ["hook 1", "hook 2", "hook 3"],
  "body": "the full body text — all 5 blocks run together as one narrative, no headers or labels",
  "cta": "your specific question here"
}}"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=1600,
    )

    raw = response.choices[0].message.content.strip()
    logger.debug(f"Raw LLM response: {raw[:200]}")

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
    # Escape literal newlines/control chars inside JSON string values so json.loads accepts them
    raw = _sanitize_json_strings(raw)

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


def _sanitize_json_strings(s: str) -> str:
    """Escape literal newlines/control chars inside JSON string values."""
    result: list[str] = []
    in_string = False
    escape_next = False
    for ch in s:
        if escape_next:
            result.append(ch)
            escape_next = False
        elif ch == "\\":
            result.append(ch)
            escape_next = True
        elif ch == '"':
            result.append(ch)
            in_string = not in_string
        elif in_string and ch == "\n":
            result.append("\\n")
        elif in_string and ch == "\r":
            result.append("\\r")
        elif in_string and ord(ch) < 0x20:
            pass  # drop other control chars inside strings
        else:
            result.append(ch)
    return "".join(result)


def _recover_json(raw: str) -> dict:
    """Last-resort: try to extract JSON object from messy LLM output."""
    # Try progressively larger JSON substrings (LLM may include preamble/postamble)
    for match in re.finditer(r"\{", raw):
        candidate = raw[match.start():]
        # Find the matching closing brace by counting depth
        depth, end = 0, -1
        for i, ch in enumerate(candidate):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end == -1:
            continue
        try:
            return json.loads(candidate[:end])
        except Exception:
            continue
    return {"hooks": [], "body": raw, "cta": "आपकी क्या राय है? नीचे कमेंट करें।"}
