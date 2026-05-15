from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def db():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE videos (
            video_id TEXT PRIMARY KEY,
            source_title TEXT,
            source_channel_name TEXT,
            status TEXT DEFAULT 'discovered',
            target_language TEXT,
            styles_json TEXT,
            script_word_count INTEGER,
            transcript_path TEXT,
            youtube_url TEXT,
            failure_reason TEXT,
            updated_at TEXT DEFAULT (datetime('now')),
            seo_title TEXT,
            seo_description TEXT,
            seo_hashtags_json TEXT,
            seo_thumbnail_phrases_json TEXT,
            seo_thumbnail_phrase TEXT,
            thumbnail_path TEXT
        )
    """)
    conn.execute("""
        INSERT INTO videos
            (video_id, source_title, target_language, styles_json, status)
        VALUES ('v1', 'Test Source', 'english', '["documentary"]', 'script_drafted')
    """)
    conn.commit()
    yield conn
    conn.close()


@contextmanager
def _conn_cm(conn):
    yield conn
    conn.commit()


def _patch_conn(db):
    return patch("src.api.main.get_conn", side_effect=lambda: _conn_cm(db))


def test_get_seo_returns_404_when_no_data(db):
    with _patch_conn(db):
        r = client.get("/api/videos/v1/seo")
    assert r.status_code == 404


def test_get_seo_returns_data_when_populated(db):
    db.execute("""
        UPDATE videos SET
            seo_title='Great Title',
            seo_description='A nice desc',
            seo_hashtags_json='["#one","#two"]',
            seo_thumbnail_phrases_json='["Phrase A","Phrase B","Phrase C"]',
            seo_thumbnail_phrase='Phrase A'
        WHERE video_id='v1'
    """)
    db.commit()

    with _patch_conn(db):
        r = client.get("/api/videos/v1/seo")

    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Great Title"
    assert body["hashtags"] == ["#one", "#two"]
    assert body["thumbnail_phrases"] == ["Phrase A", "Phrase B", "Phrase C"]
    assert body["thumbnail_phrase"] == "Phrase A"


def test_generate_seo_returns_metadata(db, tmp_path):
    draft = {"hooks": ["Hook one"], "body": "Body text.", "cta": "Subscribe!"}
    (tmp_path / "v1_draft.json").write_text(json.dumps(draft), encoding="utf-8")

    from src.seo.models import SeoMetadata
    fake_meta = SeoMetadata(
        title="Generated Title",
        description="Generated description.",
        hashtags=["#foo", "#bar"],
        thumbnail_phrases=["Phrase 1", "Phrase 2", "Phrase 3"],
        niche="history",
    )

    with (
        patch("src.api.main._SCRIPTS_DIR", tmp_path),
        patch("src.seo.generate_and_enrich", return_value=fake_meta),
        _patch_conn(db),
    ):
        r = client.post("/api/videos/v1/seo/generate")

    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Generated Title"
    assert body["hashtags"] == ["#foo", "#bar"]
    assert body["thumbnail_phrase"] is None


def test_generate_seo_saves_to_db(db, tmp_path):
    draft = {"hooks": ["Hook"], "body": "Body.", "cta": "CTA."}
    (tmp_path / "v1_draft.json").write_text(json.dumps(draft), encoding="utf-8")

    from src.seo.models import SeoMetadata
    fake_meta = SeoMetadata(
        title="Saved Title",
        description="Saved desc.",
        hashtags=["#saved"],
        thumbnail_phrases=["Saved Phrase"],
        niche="tech",
    )

    with (
        patch("src.api.main._SCRIPTS_DIR", tmp_path),
        patch("src.seo.generate_and_enrich", return_value=fake_meta),
        _patch_conn(db),
    ):
        client.post("/api/videos/v1/seo/generate")

    row = db.execute(
        "SELECT seo_title, seo_hashtags_json FROM videos WHERE video_id='v1'"
    ).fetchone()
    assert row["seo_title"] == "Saved Title"
    assert json.loads(row["seo_hashtags_json"]) == ["#saved"]
