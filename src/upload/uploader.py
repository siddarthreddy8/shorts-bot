from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from src.db.database import get_conn, log_event
from src.utils.config import env, load_config, project_root
from src.utils.logger import logger

_SCRIPTS_DIR = project_root() / "data" / "scripts"
_VIDEOS_DIR = project_root() / "data" / "videos"

# YouTube Data API scopes needed for upload
_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# YouTube category ID for News & Politics
_CATEGORY_NEWS = "25"


@dataclass
class UploadResult:
    video_id: str          # source video ID (our pipeline ID)
    youtube_id: str        # uploaded video ID on YouTube
    youtube_url: str
    title: str


def upload(video_id: str) -> UploadResult:
    """Upload a rendered Short to YouTube and update the DB."""
    video_path = _VIDEOS_DIR / f"{video_id}.mp4"
    if not video_path.exists():
        raise FileNotFoundError(f"No rendered video at {video_path}. Run `render` first.")

    approved_path = _SCRIPTS_DIR / f"{video_id}_approved.txt"
    if not approved_path.exists():
        raise FileNotFoundError(f"No approved script at {approved_path}.")

    script_text = approved_path.read_text(encoding="utf-8").strip()

    # First paragraph = hook → video title
    hook = script_text.split("\n\n", 1)[0].strip()
    hook = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", hook).strip()

    cfg = load_config()
    title = _truncate(hook + " #Shorts", cfg.upload.title_max_len)
    description = _build_description(script_text, video_id)
    tags = _build_tags(script_text, cfg)

    # Language from DB
    with get_conn() as conn:
        row = conn.execute(
            "SELECT target_language, source_url FROM videos WHERE video_id=?", (video_id,)
        ).fetchone()
    language = (row["target_language"] or "en") if row else "en"
    # Map to BCP-47
    lang_code = "hi" if language == "hindi" else "en"

    youtube = _build_youtube_client()

    logger.info(f"Uploading {video_id} → '{title}'")
    yt_id = _upload_video(youtube, video_path, title, description, tags, lang_code, cfg.output.visibility)

    yt_url = f"https://www.youtube.com/shorts/{yt_id}"
    logger.info(f"Uploaded: {yt_url}")

    # Update DB
    with get_conn() as conn:
        conn.execute(
            "UPDATE videos SET status='uploaded', youtube_upload_id=?, youtube_url=?, "
            "updated_at=datetime('now') WHERE video_id=?",
            (yt_id, yt_url, video_id),
        )
    log_event(video_id, "upload", f"Uploaded as {yt_url}")

    return UploadResult(video_id=video_id, youtube_id=yt_id, youtube_url=yt_url, title=title)


def _build_youtube_client():
    """Return an authenticated YouTube client, running OAuth flow if needed."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    token_path = Path(env("YOUTUBE_TOKEN_CACHE", default="./config/youtube_token.json"))
    client_secrets = Path(env("YOUTUBE_OAUTH_CLIENT_SECRETS", default="./config/youtube_client_secret.json"))

    creds: Credentials | None = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            logger.info("OAuth token refreshed.")
        else:
            logger.info("Starting OAuth flow — a browser window will open.")
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), _SCOPES)
            creds = flow.run_local_server(port=0)
            logger.info("OAuth flow complete.")

        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


def _upload_video(
    youtube,
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    language: str,
    visibility: str,
) -> str:
    """Upload video via resumable upload; return the new YouTube video ID."""
    from googleapiclient.http import MediaFileUpload

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": _CATEGORY_NEWS,
            "defaultLanguage": language,
            "defaultAudioLanguage": language,
        },
        "status": {
            "privacyStatus": visibility,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=4 * 1024 * 1024,  # 4 MB chunks
    )

    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            logger.info(f"Upload progress: {pct}%")

    return response["id"]


def _build_description(script_text: str, video_id: str) -> str:
    """Build upload description from script + source attribution."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT source_url, source_channel_name FROM videos WHERE video_id=?", (video_id,)
        ).fetchone()

    source_url = row["source_url"] if row else ""
    source_channel = row["source_channel_name"] if row else "Raka Lokam"

    # Body paragraphs (skip hook line and CTA)
    parts = script_text.split("\n\n")
    body_lines = parts[1:-1] if len(parts) > 2 else parts[1:]
    body = "\n\n".join(body_lines).strip()

    return (
        f"{body}\n\n"
        f"📺 Original: {source_url}\n"
        f"🙏 Credit: {source_channel}\n\n"
        f"#Shorts #Hindi #News"
    )


def _build_tags(script_text: str, cfg) -> list[str]:
    """Generate tags from config defaults + keywords extracted from script."""
    tags = list(cfg.upload.default_tags)
    # Add language tag
    tags.append("hindi")
    tags.append("news")
    tags.append("india")
    # Cap at 500 chars total (YouTube limit)
    result, total = [], 0
    for tag in tags:
        if total + len(tag) + 1 > 490:
            break
        result.append(tag)
        total += len(tag) + 1
    return result


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"
