from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential

from src.db.database import get_conn, log_event
from src.utils.config import env, load_config
from src.utils.logger import logger

_SHORTS_MAX_SEC = 180  # YouTube Shorts extended to 3 min in 2024


@dataclass
class VideoMeta:
    video_id: str
    channel_id: str
    channel_name: str
    title: str
    published_at: str
    url: str
    duration_sec: int | None = None


def _build_client():
    api_key = env("YOUTUBE_API_KEY", required=True)
    return build("youtube", "v3", developerKey=api_key)


def _iso_duration_to_sec(iso: str) -> int:
    """PT1M30S → 90, PT58S → 58, PT0S → 0."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    h, mn, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mn * 60 + s


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=10))
def _resolve_handle_to_id(client, handle: str) -> str | None:
    """Resolve @handle to a channel ID via the YouTube API."""
    try:
        resp = client.channels().list(part="id", forHandle=handle).execute()
        items = resp.get("items", [])
        if items:
            return items[0]["id"]
    except HttpError as e:
        logger.warning(f"Could not resolve handle @{handle}: {e}")
    return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=2, max=10))
def _fetch_recent_videos(client, channel_id: str, max_results: int = 10) -> list[VideoMeta]:
    """Return the N most recently published videos for a channel."""
    resp = (
        client.search()
        .list(
            part="snippet",
            channelId=channel_id,
            order="date",
            type="video",
            maxResults=max_results,
        )
        .execute()
    )

    items = resp.get("items", [])
    if not items:
        return []

    video_ids = [item["id"]["videoId"] for item in items]

    # Fetch durations in one batch call
    details_resp = (
        client.videos()
        .list(part="contentDetails,snippet", id=",".join(video_ids))
        .execute()
    )

    results = []
    for detail in details_resp.get("items", []):
        vid = detail["id"]
        snippet = detail["snippet"]
        duration_iso = detail["contentDetails"].get("duration", "PT0S")
        duration_sec = _iso_duration_to_sec(duration_iso)
        results.append(VideoMeta(
            video_id=vid,
            channel_id=channel_id,
            channel_name=snippet.get("channelTitle", ""),
            title=snippet.get("title", ""),
            published_at=snippet.get("publishedAt", ""),
            url=f"https://www.youtube.com/shorts/{vid}",
            duration_sec=duration_sec,
        ))

    return results


def _is_already_processed(video_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT video_id FROM videos WHERE video_id = ?", (video_id,)
        ).fetchone()
    return row is not None


def _get_last_seen(channel_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_seen_video_id FROM channel_state WHERE channel_id = ?",
            (channel_id,),
        ).fetchone()
    return row["last_seen_video_id"] if row else None


def _fetch_channel_name(client, channel_id: str) -> str | None:
    try:
        resp = client.channels().list(part="snippet", id=channel_id).execute()
        items = resp.get("items", [])
        if items:
            return items[0]["snippet"]["title"]
    except Exception:
        pass
    return None


def _update_last_seen(channel_id: str, video_id: str, channel_name: str = "") -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO channel_state (channel_id, last_seen_video_id, last_polled_at, name)
               VALUES (?, ?, datetime('now'), ?)
               ON CONFLICT(channel_id) DO UPDATE SET
                 last_seen_video_id = excluded.last_seen_video_id,
                 last_polled_at = excluded.last_polled_at,
                 name = COALESCE(NULLIF(excluded.name, ''), channel_state.name)""",
            (channel_id, video_id, channel_name),
        )


def _is_channel_disabled(channel_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT enabled FROM channel_state WHERE channel_id=?", (channel_id,)
        ).fetchone()
    return row is not None and not row["enabled"]


def _save_video(meta: VideoMeta) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO videos
               (video_id, source_channel_id, source_channel_name, source_url,
                source_title, source_published_at, status)
               VALUES (?, ?, ?, ?, ?, ?, 'discovered')""",
            (
                meta.video_id,
                meta.channel_id,
                meta.channel_name,
                meta.url,
                meta.title,
                meta.published_at,
            ),
        )
    log_event(meta.video_id, "monitor", f"Discovered: {meta.title} ({meta.duration_sec}s)")


def poll_channels() -> list[VideoMeta]:
    """Poll all enabled source channels and return newly discovered videos."""
    cfg = load_config()
    enabled = [ch for ch in cfg.source_channels if ch.enabled]

    if not enabled:
        logger.warning("No enabled source channels in config.yaml")
        return []

    client = _build_client()
    new_videos: list[VideoMeta] = []

    for channel in enabled:
        # Resolve handle → channel ID if needed
        channel_id = channel.id
        if channel.handle:
            resolved = _resolve_handle_to_id(client, channel.handle)
            if resolved and resolved != channel_id:
                logger.info(f"Handle @{channel.handle} resolved to {resolved} (config has {channel_id})")
                channel_id = resolved
            elif resolved:
                channel_id = resolved

        if _is_channel_disabled(channel_id):
            logger.info(f"Channel {channel_id} disabled in DB — skipping")
            continue

        # Resolve display name: config name → YouTube API fallback
        display_name = channel.name or _fetch_channel_name(client, channel_id) or channel_id

        logger.info(f"Polling channel: {display_name} ({channel_id})")
        try:
            videos = _fetch_recent_videos(client, channel_id)
        except HttpError as e:
            logger.error(f"YouTube API error for {channel_id}: {e}")
            log_event(None, "monitor", f"API error for {channel_id}: {e}", level="error")
            continue

        if not videos:
            logger.info(f"No videos found on {display_name}")
            continue

        # Record the newest video ID so future polls skip already-seen ones fast
        _update_last_seen(channel_id, videos[0].video_id, display_name)

        for meta in videos:
            if channel.shorts_only:
                dur = meta.duration_sec

                # duration=0 means premiere / live stream — skip, can't verify it's a Short
                if dur == 0:
                    logger.info(f"Skipping {meta.video_id} — duration unknown (premiere or live)")
                    continue

                # Skip anything longer than the Shorts limit
                if dur > _SHORTS_MAX_SEC:
                    logger.info(f"Skipping {meta.video_id} ({dur}s) — exceeds Shorts limit of {_SHORTS_MAX_SEC}s")
                    continue

            if _is_already_processed(meta.video_id):
                continue

            logger.info(f"New Short: [{meta.video_id}] {meta.title} ({meta.duration_sec}s)")
            _save_video(meta)
            new_videos.append(meta)

    logger.info(f"Poll complete — {len(new_videos)} new video(s) found")
    return new_videos


def fetch_from_url(url: str) -> VideoMeta | None:
    """Extract video metadata from an ad-hoc YouTube URL."""
    video_id = _extract_video_id(url)
    if not video_id:
        logger.error(f"Could not extract video ID from URL: {url}")
        return None

    client = _build_client()
    try:
        resp = (
            client.videos()
            .list(part="snippet,contentDetails", id=video_id)
            .execute()
        )
    except HttpError as e:
        logger.error(f"YouTube API error fetching {url}: {e}")
        return None

    items = resp.get("items", [])
    if not items:
        logger.error(f"Video not found or private: {video_id}")
        return None

    detail = items[0]
    snippet = detail["snippet"]
    duration_sec = _iso_duration_to_sec(detail["contentDetails"].get("duration", "PT0S"))

    meta = VideoMeta(
        video_id=video_id,
        channel_id=snippet.get("channelId", ""),

        
        channel_name=snippet.get("channelTitle", ""),
        title=snippet.get("title", ""),
        published_at=snippet.get("publishedAt", ""),
        url=f"https://www.youtube.com/shorts/{video_id}",
        duration_sec=duration_sec,
    )

    if _is_already_processed(video_id):
        logger.warning(f"Video {video_id} already processed — continuing anyway (ad-hoc mode)")

    _save_video(meta)
    return meta


def _extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})",
        r"^([A-Za-z0-9_-]{11})$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None
