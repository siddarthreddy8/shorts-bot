from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from src.utils.config import project_root
from src.utils.logger import logger

_DB_PATH = project_root() / "data" / "pipeline.sqlite"
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

_NEW_COLUMNS: list[tuple[str, str]] = [
    ("seo_title", "TEXT"),
    ("seo_description", "TEXT"),
    ("seo_hashtags_json", "TEXT"),
    ("seo_thumbnail_phrases_json", "TEXT"),
    ("seo_thumbnail_phrase", "TEXT"),
    ("thumbnail_path", "TEXT"),
]


def _apply_migrations(conn: sqlite3.Connection) -> None:
    for col, col_type in _NEW_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE videos ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass  # column already exists


def init_db() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    with sqlite3.connect(_DB_PATH) as conn:
        conn.executescript(schema)
        _apply_migrations(conn)
    logger.info(f"DB initialized at {_DB_PATH}")


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_event(
    video_id: str | None,
    stage: str,
    message: str,
    level: str = "info",
    payload_json: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO events (video_id, stage, level, message, payload_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (video_id, stage, level, message, payload_json),
        )
