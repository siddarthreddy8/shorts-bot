import sqlite3
from pathlib import Path


def _fresh_db(schema_sql: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(schema_sql)
    return conn


def test_new_columns_exist_in_fresh_db():
    schema = Path("src/db/schema.sql").read_text(encoding="utf-8")
    conn = _fresh_db(schema)
    cursor = conn.execute("PRAGMA table_info(videos)")
    columns = {row[1] for row in cursor.fetchall()}
    expected = {
        "seo_title", "seo_description", "seo_hashtags_json",
        "seo_thumbnail_phrases_json", "seo_thumbnail_phrase", "thumbnail_path",
    }
    assert expected.issubset(columns), f"Missing columns: {expected - columns}"


def test_migration_adds_columns_to_existing_db():
    from src.db.database import _apply_migrations

    # Simulate a DB created before the new columns existed.
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE videos (
            video_id TEXT PRIMARY KEY,
            source_channel_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'discovered'
        )
    """)
    conn.commit()

    _apply_migrations(conn)
    conn.commit()

    cursor = conn.execute("PRAGMA table_info(videos)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "seo_title" in columns
    assert "thumbnail_path" in columns
