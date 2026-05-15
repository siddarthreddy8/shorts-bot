from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Literal

from src.utils.logger import logger

StepState = Literal["pending", "running", "done", "failed"]


@dataclass
class StepStatus:
    name: str
    state: StepState = "pending"
    error: str | None = None


@dataclass
class VideoProgress:
    steps: list[StepStatus] = field(default_factory=lambda: [
        StepStatus("Storyboard"),
        StepStatus("Render"),
        StepStatus("Upload"),
    ])


_progress: dict[str, VideoProgress] = {}
_lock = threading.Lock()


def get_progress(video_id: str) -> VideoProgress | None:
    with _lock:
        return _progress.get(video_id)


def run_pipeline(video_id: str) -> None:
    """Storyboard → render. Upload is a separate user-triggered step (quality gate)."""
    prog = VideoProgress()
    with _lock:
        _progress[video_id] = prog

    _run_step(prog, 0, "Storyboard", _do_storyboard, video_id)
    if prog.steps[0].state == "failed":
        return

    _run_step(prog, 1, "Render", _do_render, video_id)


def run_upload(video_id: str) -> None:
    """Upload only — called after the user approves the render via the quality gate."""
    prog = VideoProgress()
    prog.steps[0].state = "done"
    prog.steps[1].state = "done"
    with _lock:
        _progress[video_id] = prog

    _run_step(prog, 2, "Upload", _do_upload, video_id)


def _run_step(prog: VideoProgress, idx: int, name: str, fn, video_id: str) -> None:
    with _lock:
        prog.steps[idx].state = "running"
    try:
        fn(video_id)
        with _lock:
            prog.steps[idx].state = "done"
    except Exception as e:
        logger.error(f"Pipeline step {name} failed for {video_id}: {e}")
        with _lock:
            prog.steps[idx].state = "failed"
            prog.steps[idx].error = str(e)


def _do_storyboard(video_id: str) -> None:
    from src.storyboard.generator import build
    build(video_id)


def _do_render(video_id: str) -> None:
    from src.video.generator import render
    render(video_id)


def _do_upload(video_id: str) -> None:
    from src.upload.uploader import upload
    upload(video_id)
