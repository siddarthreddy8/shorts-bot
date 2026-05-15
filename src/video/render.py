from __future__ import annotations

import asyncio
import json
from pathlib import Path

from src.utils.config import project_root


async def render_thumbnail(
    video_id: str,
    phrase: str,
    style: str,
    niche: str,
) -> Path:
    out_path = project_root() / "data" / "videos" / f"{video_id}_thumbnail.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    remotion_dir = project_root() / "remotion"
    props = json.dumps({"phrase": phrase, "style": style, "niche": niche})
    proc = await asyncio.create_subprocess_exec(
        "npx", "remotion", "still", "Thumbnail", str(out_path),
        f"--props={props}",
        cwd=str(remotion_dir),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Thumbnail render failed: {stderr.decode()}")
    return out_path
