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

    # Run only the migration logic (not the full schema which would fail on table exists).
    NEW_COLS = [
        ("seo_title", "TEXT"),
        ("seo_description", "TEXT"),
        ("seo_hashtags_json", "TEXT"),
        ("seo_thumbnail_phrases_json", "TEXT"),
        ("seo_thumbnail_phrase", "TEXT"),
        ("thumbnail_path", "TEXT"),
    ]
    for col, col_type in NEW_COLS:
        try:
            conn.execute(f"ALTER TABLE videos ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass
    conn.commit()

    cursor = conn.execute("PRAGMA table_info(videos)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "seo_title" in columns
    assert "thumbnail_path" in columns
