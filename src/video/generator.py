from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from src.db.database import get_conn, log_event
from src.utils.config import project_root
from src.utils.logger import logger

_VIDEOS_DIR = project_root() / "data" / "videos"
_SCRIPTS_DIR = project_root() / "data" / "scripts"
_REMOTION_DIR = project_root() / "remotion"
_FPS = 30
_MAX_FRAMES = 180 * _FPS  # render cap (3 min); YouTube Shorts enforced at upload
_WARN_DURATION_SEC = 60.0  # warn if TTS exceeds YouTube Shorts limit


@dataclass
class RenderResult:
    video_id: str
    video_path: Path
    duration_sec: float


def render(video_id: str, composition: str | None = None, regenerate: bool = False) -> RenderResult:
    """Approved script → TTS audio → Remotion render → MP4.

    If a storyboard exists at data/storyboards/{video_id}.json, use HoogScene
    (with AI-generated B-roll). Otherwise fall back to HoogTypography (text-only).
    """
    _VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = _VIDEOS_DIR / f"{video_id}.mp4"

    # Use HoogScene only when storyboard visuals are fully generated (not just planned)
    storyboard_path = project_root() / "data" / "storyboards" / f"{video_id}.json"
    has_storyboard = False
    if storyboard_path.exists():
        import json as _json
        _sb = _json.loads(storyboard_path.read_text(encoding="utf-8"))
        has_storyboard = _sb.get("status") == "generated"
    if composition is None:
        composition = "HoogScene" if has_storyboard else "HoogTypography"

    if output_path.exists() and not regenerate:
        logger.info(f"Video already rendered: {output_path}")
        return RenderResult(video_id=video_id, video_path=output_path, duration_sec=0.0)

    approved_path = _SCRIPTS_DIR / f"{video_id}_approved.txt"
    if not approved_path.exists():
        raise FileNotFoundError(
            f"No approved script at {approved_path}. "
            "Approve in the review UI first."
        )

    script_text = approved_path.read_text(encoding="utf-8").strip()

    # First paragraph is the hook → used as the big title card
    parts = script_text.split("\n\n", 1)
    raw_title = parts[0].strip()
    # Strip markdown for display
    import re
    title = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", raw_title).strip()

    # Language from DB
    with get_conn() as conn:
        row = conn.execute(
            "SELECT target_language FROM videos WHERE video_id=?", (video_id,)
        ).fetchone()
    language = (row["target_language"] or "english") if row else "english"

    # ── Step 1: TTS ────────────────────────────────────────────────────────────
    from src.video.tts import generate_tts
    tts = generate_tts(video_id, script_text, language=language)

    # ── Step 2: Build Remotion props ───────────────────────────────────────────
    if tts.duration_sec > _WARN_DURATION_SEC:
        logger.warning(
            f"Audio is {tts.duration_sec:.1f}s — exceeds YouTube Shorts 60s limit. "
            "Video will render fully but won't qualify as a Short."
        )
    duration_frames = min(int(tts.duration_sec * _FPS) + 30, _MAX_FRAMES)
    audio_src = f"audio/{video_id}.mp3"  # relative to remotion/public/

    props: dict = {
        "title": title,
        "captions": tts.captions,
        "audioSrc": audio_src,
    }
    if composition == "HoogMap":
        props["focusRegion"] = "world"
    elif composition == "HoogScene":
        storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
        props["scenes"] = storyboard["scenes"]
        logger.info(f"Using storyboard with {len(storyboard['scenes'])} scenes")

    props_path = _VIDEOS_DIR / f"{video_id}_props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Props written: {props_path}")

    # ── Step 3: Remotion render ────────────────────────────────────────────────
    logger.info(f"Rendering {composition} — {duration_frames} frames @ {_FPS}fps ({tts.duration_sec:.1f}s)")
    _remotion_render(composition, props_path, output_path, duration_frames)

    # ── Step 4: Update DB ──────────────────────────────────────────────────────
    with get_conn() as conn:
        conn.execute(
            "UPDATE videos SET status='video_rendered', rendered_video_path=?, "
            "updated_at=datetime('now') WHERE video_id=?",
            (str(output_path), video_id),
        )
    log_event(video_id, "render", f"Rendered {output_path.name} ({tts.duration_sec:.1f}s)")

    logger.info(f"Video ready: {output_path}")
    return RenderResult(video_id=video_id, video_path=output_path, duration_sec=tts.duration_sec)


def _remotion_render(
    composition: str,
    props_path: Path,
    output_path: Path,
    duration_frames: int,
) -> None:
    """Invoke the Remotion CLI render command (Windows + Unix compatible)."""
    args = [
        "render",
        composition,
        str(output_path),
        f"--props={props_path}",
        f"--frames=0-{duration_frames - 1}",
        "--concurrency=4",
        "--log=verbose",
    ]

    if sys.platform == "win32":
        remotion_cmd = _REMOTION_DIR / "node_modules" / ".bin" / "remotion.cmd"
        cmd = ["cmd", "/c", str(remotion_cmd)] + args
    else:
        remotion_cmd = _REMOTION_DIR / "node_modules" / ".bin" / "remotion"
        cmd = [str(remotion_cmd)] + args

    logger.info(f"Remotion: {' '.join(str(c) for c in cmd[:4])} ...")
    result = subprocess.run(
        cmd,
        cwd=str(_REMOTION_DIR),
        timeout=1800,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Remotion render failed (exit {result.returncode}). "
            "Check the output above for details."
        )
