-- Pipeline state per source video.
CREATE TABLE IF NOT EXISTS videos (
    video_id              TEXT PRIMARY KEY,           -- YouTube video ID of the source
    source_channel_id     TEXT NOT NULL,
    source_channel_name   TEXT,
    source_url            TEXT,
    source_title          TEXT,
    source_published_at   TEXT,                       -- ISO 8601
    discovered_at         TEXT NOT NULL DEFAULT (datetime('now')),
    status                TEXT NOT NULL DEFAULT 'discovered',
        -- discovered | transcribed | script_drafted | script_approved
        -- | video_rendered | uploaded | failed | skipped
    failure_reason        TEXT,
    transcript_path       TEXT,
    transcript_lang       TEXT DEFAULT 'te',
    target_language       TEXT,                       -- english | hindi
    styles_json           TEXT,                       -- JSON array of selected styles
    final_script_path     TEXT,
    rendered_video_path   TEXT,
    youtube_upload_id     TEXT,                       -- ID of the uploaded Short
    youtube_url           TEXT,
    -- metrics
    script_word_count     INTEGER,
    script_edit_distance  REAL,                       -- % difference between draft and approved
    pipeline_duration_sec INTEGER,
    cost_usd              REAL,
    -- SEO metadata
    seo_title                    TEXT,
    seo_description              TEXT,
    seo_hashtags_json            TEXT,           -- JSON array
    seo_thumbnail_phrases_json   TEXT,           -- JSON array, 3 options
    seo_thumbnail_phrase         TEXT,           -- user-selected phrase
    thumbnail_path               TEXT,           -- rendered PNG path
    updated_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(source_channel_id);

-- Per-stage event log.
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id    TEXT,
    stage       TEXT NOT NULL,                        -- monitor | transcribe | script | review | render | upload
    level       TEXT NOT NULL DEFAULT 'info',         -- info | warn | error
    message     TEXT,
    payload_json TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (video_id) REFERENCES videos(video_id)
);

CREATE INDEX IF NOT EXISTS idx_events_video ON events(video_id);
CREATE INDEX IF NOT EXISTS idx_events_stage ON events(stage);

-- Per-channel high-water mark to dedup polling.
CREATE TABLE IF NOT EXISTS channel_state (
    channel_id            TEXT PRIMARY KEY,
    last_seen_video_id    TEXT,
    last_polled_at        TEXT
);
