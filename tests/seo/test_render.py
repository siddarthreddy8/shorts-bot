from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.video.render import render_thumbnail


@pytest.mark.asyncio
async def test_render_thumbnail_returns_path_on_success():
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))

    with patch("src.video.render.asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("src.video.render.project_root", return_value=Path("/fake")):
        result = await render_thumbnail(
            video_id="abc123",
            phrase="You Won't Believe This",
            style="documentary",
            niche="history",
        )

    assert result == Path("/fake/data/videos/abc123_thumbnail.png")


@pytest.mark.asyncio
async def test_render_thumbnail_raises_on_nonzero_exit():
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(return_value=(b"", b"Render error"))

    with patch("src.video.render.asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("src.video.render.project_root", return_value=Path("/fake")):
        with pytest.raises(RuntimeError, match="Thumbnail render failed"):
            await render_thumbnail("vid1", "phrase", "style", "niche")


@pytest.mark.asyncio
async def test_render_thumbnail_passes_correct_props():
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))
    captured_args = []

    async def capture(*args, **kwargs):
        captured_args.extend(args)
        return mock_proc

    with patch("src.video.render.asyncio.create_subprocess_exec", side_effect=capture), \
         patch("src.video.render.project_root", return_value=Path("/fake")):
        await render_thumbnail("vid1", "Shocking Truth", "documentary", "history")

    props_arg = next(a for a in captured_args if "--props=" in str(a))
    assert "Shocking Truth" in props_arg
    assert "history" in props_arg
