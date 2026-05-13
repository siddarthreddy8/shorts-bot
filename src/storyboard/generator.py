from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.db.database import get_conn, log_event
from src.storyboard.imagery import generate_image
from src.storyboard.planner import plan_scenes
from src.utils.config import project_root
from src.utils.logger import logger

_STORYBOARDS_DIR = project_root() / "data" / "storyboards"
_SCRIPTS_DIR = project_root() / "data" / "scripts"
_SCENES_DIR = project_root() / "remotion" / "public" / "scenes"
_AUDIO_DIR = project_root() / "remotion" / "public" / "audio"


@dataclass
class Storyboard:
    video_id: str
    scenes: list[dict]
    storyboard_path: Path


def build(video_id: str, *, regenerate: bool = False) -> Storyboard:
    """Approved script → LLM scene plan → FAL imagery → storyboard JSON."""
    _STORYBOARDS_DIR.mkdir(parents=True, exist_ok=True)
    storyboard_path = _STORYBOARDS_DIR / f"{video_id}.json"

    if storyboard_path.exists() and not regenerate:
        logger.info(f"Storyboard cached: {storyboard_path}")
        data = json.loads(storyboard_path.read_text(encoding="utf-8"))
        return Storyboard(video_id=video_id, scenes=data["scenes"], storyboard_path=storyboard_path)

    # Load approved script
    approved_path = _SCRIPTS_DIR / f"{video_id}_approved.txt"
    if not approved_path.exists():
        raise FileNotFoundError(f"No approved script: {approved_path}. Approve in review UI first.")
    script_text = approved_path.read_text(encoding="utf-8").strip()

    # Load TTS caption file to get accurate audio duration — generate TTS if not cached yet
    captions_path = _AUDIO_DIR / f"{video_id}_captions.json"
    if not captions_path.exists():
        logger.info("TTS not yet generated — running TTS now to get duration for scene planning...")
        from src.db.database import get_conn as _get_conn
        with _get_conn() as conn:
            row = conn.execute("SELECT target_language FROM videos WHERE video_id=?", (video_id,)).fetchone()
        language = (row["target_language"] or "english") if row else "english"
        from src.video.tts import generate_tts
        tts = generate_tts(video_id, script_text, language=language)
        duration_sec = tts.duration_sec
    else:
        captions_data = json.loads(captions_path.read_text(encoding="utf-8"))
        duration_sec = captions_data["duration_sec"]

    # 1. Plan scenes via LLM
    scenes = plan_scenes(script_text, duration_sec)
    if not scenes:
        raise RuntimeError("LLM planner returned zero scenes")

    # 2. Generate images via FAL
    scenes_dir = _SCENES_DIR / video_id
    scenes_dir.mkdir(parents=True, exist_ok=True)

    for i, scene in enumerate(scenes):
        img_filename = f"{i:02d}.png"
        img_path = scenes_dir / img_filename
        # Append style anchor to every prompt for consistency across scenes
        full_prompt = (
            scene["prompt"]
            + " — Cinematic documentary photography, 9:16 vertical portrait, "
              "Hoog channel aesthetic, dramatic lighting, moody color grading, "
              "high detail, 8k quality"
        )
        try:
            generate_image(full_prompt, img_path)
        except Exception as e:
            logger.error(f"Failed to generate scene {i}: {e}")
            # Continue — Remotion will use a black fallback for missing images
        # Store path relative to remotion/public/ for staticFile()
        scene["image_path"] = f"scenes/{video_id}/{img_filename}"

    # 3. Save storyboard JSON
    payload = {
        "video_id": video_id,
        "duration_ms": int(duration_sec * 1000),
        "scenes": scenes,
    }
    storyboard_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Storyboard saved: {storyboard_path} ({len(scenes)} scenes)")

    # 4. Update DB
    with get_conn() as conn:
        conn.execute(
            "UPDATE videos SET updated_at=datetime('now') WHERE video_id=?",
            (video_id,),
        )
    log_event(video_id, "storyboard", f"Generated {len(scenes)} scenes")

    return Storyboard(video_id=video_id, scenes=scenes, storyboard_path=storyboard_path)
