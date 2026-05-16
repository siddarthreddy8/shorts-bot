from __future__ import annotations

# Lightweight imports only at module level (safe for test collection).
# Heavy modules (torch/whisper, remotion subprocess, google oauth) are
# imported lazily inside _process_video so test imports don't pull in GPU libs.
from src.db.database import init_db, log_event
from src.monitor.youtube_monitor import poll_channels
from src.pipeline.auto_approve import auto_approve
from src.pipeline.shutdown import stop_self
from src.utils.logger import logger

_LANGUAGE = "hindi"
_STYLES = ["storytelling"]


def run() -> None:
    """Full automated pipeline: monitor -> transcribe -> script -> approve -> render -> upload -> shutdown.

    Always calls stop_self() at the end -- even if no videos found or a video fails.
    Individual video failures are logged and skipped; the next video is still processed.
    """
    init_db()
    try:
        videos = poll_channels()
        if not videos:
            logger.info("No new videos found.")
            return

        logger.info(f"Processing {len(videos)} video(s)...")
        for video in videos:
            try:
                _process_video(video)
            except Exception as exc:
                logger.error(f"[{video.video_id}] pipeline failed: {exc}")
                log_event(video.video_id, "error", str(exc))
    finally:
        stop_self()


def _process_video(video) -> None:
    """Run all pipeline steps for a single video.

    Heavy imports are lazy here to avoid pulling torch/whisper into
    module-level imports (which would break test collection).
    """
    from src.script.rewriter import generate
    from src.transcribe.whisper_transcriber import run as transcribe
    from src.upload.uploader import upload
    from src.video.generator import render as video_render

    vid = video.video_id

    logger.info(f"[{vid}] step 1/5 -- transcribing...")
    transcript = transcribe(vid, video.url)

    logger.info(f"[{vid}] step 2/5 -- generating script ({_LANGUAGE}/{_STYLES[0]})...")
    generate(vid, transcript.text, language=_LANGUAGE, styles=_STYLES)

    logger.info(f"[{vid}] step 3/5 -- auto-approving...")
    auto_approve(vid)

    logger.info(f"[{vid}] step 4/5 -- rendering...")
    video_render(vid)

    logger.info(f"[{vid}] step 5/5 -- uploading...")
    upload(vid)

    logger.info(f"[{vid}] done")
