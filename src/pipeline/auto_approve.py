from __future__ import annotations

from pathlib import Path

from src.utils.config import project_root
from src.utils.logger import logger

_SCRIPTS_DIR = project_root() / "data" / "scripts"


def auto_approve(video_id: str) -> Path:
    """Write an approved script for video_id using Hindi + storytelling defaults.

    Reads the draft JSON written by generate-script, picks the first hook,
    assembles hook + body + cta, and writes {video_id}_approved.txt.

    Returns the path to the approved script file.
    Raises FileNotFoundError if no draft exists.
    """
    import json

    draft_path = _SCRIPTS_DIR / f"{video_id}_draft.json"
    if not draft_path.exists():
        raise FileNotFoundError(
            f"No draft script at {draft_path}. "
            f"Run `generate-script {video_id}` first."
        )

    data = json.loads(draft_path.read_text(encoding="utf-8"))
    hook = data["hooks"][0] if data["hooks"] else ""
    body = data["body"]
    cta = data["cta"]
    full_script = f"{hook}\n\n{body}\n\n{cta}".strip()

    approved_path = _SCRIPTS_DIR / f"{video_id}_approved.txt"
    approved_path.write_text(full_script, encoding="utf-8")
    logger.info(f"Auto-approved [{video_id}] → {approved_path.name}")
    return approved_path
