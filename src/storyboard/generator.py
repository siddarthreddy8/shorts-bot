from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.db.database import get_conn, log_event
from src.storyboard.imagery import (
    download_video,
    generate_image,
    poll_video_jobs,
    submit_video_job,
)
from src.storyboard.person_image import fetch_person_image
from src.storyboard.planner import plan_scenes
from src.utils.config import project_root
from src.utils.logger import logger

_STORYBOARDS_DIR = project_root() / "data" / "storyboards"
_SCRIPTS_DIR = project_root() / "data" / "scripts"
_SCENES_DIR = project_root() / "remotion" / "public" / "scenes"
_AUDIO_DIR = project_root() / "remotion" / "public" / "audio"

STATUS_PLANNED = "planned"
STATUS_GENERATED = "generated"

# Appended to every prompt for visual consistency across scenes
_STYLE_SUFFIX = (
    " — Cinematic documentary photography, 9:16 vertical portrait, "
    "Hoog channel aesthetic, dramatic lighting, moody color grading, "
    "high detail, 8k quality"
)


@dataclass
class Storyboard:
    video_id: str
    scenes: list[dict]
    storyboard_path: Path
    status: str = STATUS_PLANNED
    duration_ms: int = field(default=0)


def plan_only(video_id: str, *, regenerate: bool = False) -> Storyboard:
    """LLM scene planning only — no asset generation.

    Saves a plan JSON with status='planned' so the review UI can show and edit
    prompts before the expensive video/image generation step.
    """
    _STORYBOARDS_DIR.mkdir(parents=True, exist_ok=True)
    storyboard_path = _STORYBOARDS_DIR / f"{video_id}.json"

    if storyboard_path.exists() and not regenerate:
        data = json.loads(storyboard_path.read_text(encoding="utf-8"))
        logger.info(f"Storyboard plan cached: {storyboard_path} (status={data.get('status')})")
        return Storyboard(
            video_id=video_id,
            scenes=data["scenes"],
            storyboard_path=storyboard_path,
            status=data.get("status", STATUS_PLANNED),
            duration_ms=data.get("duration_ms", 0),
        )

    approved_path = _SCRIPTS_DIR / f"{video_id}_approved.txt"
    if not approved_path.exists():
        raise FileNotFoundError(
            f"No approved script: {approved_path}. Approve in review UI first."
        )
    script_text = approved_path.read_text(encoding="utf-8").strip()
    duration_sec = _get_duration(video_id, script_text)

    scenes = plan_scenes(script_text, duration_sec)
    if not scenes:
        raise RuntimeError("LLM planner returned zero scenes")

    payload = {
        "video_id": video_id,
        "duration_ms": int(duration_sec * 1000),
        "status": STATUS_PLANNED,
        "scenes": scenes,
    }
    storyboard_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Plan saved: {storyboard_path} ({len(scenes)} scenes)")

    with get_conn() as conn:
        conn.execute("UPDATE videos SET updated_at=datetime('now') WHERE video_id=?", (video_id,))
    log_event(video_id, "storyboard", f"Planned {len(scenes)} scenes")

    return Storyboard(
        video_id=video_id,
        scenes=scenes,
        storyboard_path=storyboard_path,
        status=STATUS_PLANNED,
        duration_ms=int(duration_sec * 1000),
    )


def generate_visuals(video_id: str, *, regenerate: bool = False) -> Storyboard:
    """Generate video clips (with image fallback) for a planned storyboard.

    Submits all FAL video jobs in parallel, polls until all complete, then
    downloads. Any job that fails falls back to a static FLUX image.
    """
    storyboard_path = _STORYBOARDS_DIR / f"{video_id}.json"
    if not storyboard_path.exists():
        raise FileNotFoundError(
            f"No storyboard plan for {video_id}. Run plan_only() first."
        )

    data = json.loads(storyboard_path.read_text(encoding="utf-8"))

    if data.get("status") == STATUS_GENERATED and not regenerate:
        logger.info(f"Visuals already generated for {video_id}")
        return Storyboard(
            video_id=video_id,
            scenes=data["scenes"],
            storyboard_path=storyboard_path,
            status=STATUS_GENERATED,
            duration_ms=data.get("duration_ms", 0),
        )

    scenes: list[dict] = data["scenes"]
    scenes_dir = _SCENES_DIR / video_id
    scenes_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1a: Fetch real person photos for portrait scenes ─────────────────
    for i, scene in enumerate(scenes):
        subject = scene.get("subject_name", "").strip()
        if scene.get("visual_type") == "portrait" and subject:
            img_path = scenes_dir / f"{i:02d}.png"
            if img_path.exists() and not regenerate:
                scene["image_path"] = f"scenes/{video_id}/{i:02d}.png"
                logger.info(f"Scene {i}: person photo cached for '{subject}'")
            elif fetch_person_image(subject, img_path):
                scene["image_path"] = f"scenes/{video_id}/{i:02d}.png"
                logger.info(f"Scene {i}: real photo used for '{subject}'")
            else:
                logger.info(f"Scene {i}: no real photo for '{subject}' — will AI-generate")

    # ── Step 1b: Check cache; submit video jobs for remaining scenes ───────────
    jobs: list[tuple[str, str]] = []  # (model_id, request_id)
    job_to_scene: dict[str, int] = {}  # request_id → scene index

    for i, scene in enumerate(scenes):
        if "image_path" in scene or "video_path" in scene:
            continue  # already satisfied by real photo or cached clip

        clip_path = scenes_dir / f"{i:02d}.mp4"
        img_path = scenes_dir / f"{i:02d}.png"

        if not regenerate:
            if clip_path.exists():
                scene["video_path"] = f"scenes/{video_id}/{i:02d}.mp4"
                logger.info(f"Scene {i}: clip cached")
                continue
            if img_path.exists():
                scene["image_path"] = f"scenes/{video_id}/{i:02d}.png"
                logger.info(f"Scene {i}: image cached")
                continue

        duration_sec = max(1, (scene["end_ms"] - scene["start_ms"]) // 1000)
        full_prompt = scene["prompt"] + _STYLE_SUFFIX
        try:
            model_id, request_id = submit_video_job(full_prompt, duration_sec)
            jobs.append((model_id, request_id))
            job_to_scene[request_id] = i
        except Exception as e:
            logger.error(f"Scene {i}: video submit failed — will use image fallback. {e}")

    # ── Step 2: Poll all pending jobs together ─────────────────────────────────
    if jobs:
        logger.info(f"Waiting for {len(jobs)} video job(s)…")
        results = poll_video_jobs(jobs, timeout=600)

        for model_id, request_id in jobs:
            scene_idx = job_to_scene[request_id]
            scene = scenes[scene_idx]
            result = results.get(request_id)

            if result is not None:
                try:
                    clip_path = scenes_dir / f"{scene_idx:02d}.mp4"
                    download_video(result, clip_path)
                    scene["video_path"] = f"scenes/{video_id}/{scene_idx:02d}.mp4"
                    continue
                except Exception as e:
                    logger.error(f"Scene {scene_idx}: download failed — falling back to image. {e}")
            else:
                logger.warning(f"Scene {scene_idx}: video job failed — falling back to image.")

    # ── Step 3: Image fallback for any scene still without an asset ────────────
    for i, scene in enumerate(scenes):
        if "video_path" not in scene and "image_path" not in scene:
            _generate_image_fallback(scene, i, video_id, scenes_dir)

    # ── Step 4: Save updated storyboard ───────────────────────────────────────
    data["status"] = STATUS_GENERATED
    data["scenes"] = scenes
    storyboard_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Storyboard complete: {storyboard_path} ({len(scenes)} scenes)")

    with get_conn() as conn:
        conn.execute("UPDATE videos SET updated_at=datetime('now') WHERE video_id=?", (video_id,))
    log_event(video_id, "storyboard", f"Generated visuals for {len(scenes)} scenes")

    return Storyboard(
        video_id=video_id,
        scenes=scenes,
        storyboard_path=storyboard_path,
        status=STATUS_GENERATED,
        duration_ms=data.get("duration_ms", 0),
    )


def build(video_id: str, *, regenerate: bool = False) -> Storyboard:
    """Full pipeline: plan scenes then generate all visuals."""
    plan_only(video_id, regenerate=regenerate)
    return generate_visuals(video_id, regenerate=regenerate)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_duration(video_id: str, script_text: str) -> float:
    """Return TTS audio duration in seconds, generating TTS if not yet cached."""
    captions_path = _AUDIO_DIR / f"{video_id}_captions.json"
    if captions_path.exists():
        return json.loads(captions_path.read_text(encoding="utf-8"))["duration_sec"]

    logger.info("TTS not yet generated — running now to get duration for scene planning…")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT target_language FROM videos WHERE video_id=?", (video_id,)
        ).fetchone()
    language = (row["target_language"] or "english") if row else "english"

    from src.video.tts import generate_tts
    tts = generate_tts(video_id, script_text, language=language)
    return tts.duration_sec


def _generate_image_fallback(
    scene: dict, scene_idx: int, video_id: str, scenes_dir: Path
) -> None:
    """Generate a static FLUX image for a scene that failed video generation."""
    img_path = scenes_dir / f"{scene_idx:02d}.png"
    full_prompt = scene["prompt"] + _STYLE_SUFFIX
    try:
        generate_image(full_prompt, img_path)
        scene["image_path"] = f"scenes/{video_id}/{scene_idx:02d}.png"
        logger.info(f"Scene {scene_idx}: image fallback saved")
    except Exception as e:
        logger.error(f"Scene {scene_idx}: image fallback also failed: {e}")
