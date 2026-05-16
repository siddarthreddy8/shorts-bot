from __future__ import annotations

import json
import pytest
from pathlib import Path
from unittest.mock import patch


def _make_draft(scripts_dir: Path, video_id: str) -> None:
    draft = {
        "video_id": video_id,
        "language": "hindi",
        "styles": ["storytelling"],
        "hooks": ["एक गाँव में एक किसान था", "वह दिन था जब सब बदल गया"],
        "body": "यह कहानी है उस किसान की जो...",
        "cta": "ऐसी और कहानियों के लिए फॉलो करें।",
        "full_script": "...",
        "word_count": 50,
    }
    (scripts_dir / f"{video_id}_draft.json").write_text(
        json.dumps(draft), encoding="utf-8"
    )


def test_auto_approve_writes_approved_txt(tmp_path):
    _make_draft(tmp_path, "test123")
    with patch("src.pipeline.auto_approve._SCRIPTS_DIR", tmp_path):
        from src.pipeline.auto_approve import auto_approve
        approved_path = auto_approve("test123")
    assert approved_path.exists()
    content = approved_path.read_text(encoding="utf-8")
    assert "एक गाँव में एक किसान था" in content
    assert "यह कहानी है उस किसान की जो" in content
    assert "फॉलो करें" in content


def test_auto_approve_uses_first_hook(tmp_path):
    _make_draft(tmp_path, "test456")
    with patch("src.pipeline.auto_approve._SCRIPTS_DIR", tmp_path):
        from src.pipeline.auto_approve import auto_approve
        approved_path = auto_approve("test456")
    content = approved_path.read_text(encoding="utf-8")
    assert "एक गाँव में एक किसान था" in content
    assert "वह दिन था जब सब बदल गया" not in content


def test_auto_approve_raises_when_no_draft(tmp_path):
    with patch("src.pipeline.auto_approve._SCRIPTS_DIR", tmp_path):
        from src.pipeline.auto_approve import auto_approve
        with pytest.raises(FileNotFoundError, match="test789"):
            auto_approve("test789")
