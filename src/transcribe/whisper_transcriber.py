from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.db.database import get_conn, log_event
from src.utils.config import env, project_root
from src.utils.logger import logger

_TRANSCRIPT_DIR = project_root() / "data" / "transcripts"
_TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Transcript:
    video_id: str
    text: str
    language: str
    segments: list[dict]
    source: str          # "captions" | "whisper"
    transcript_path: Path


def run(video_id: str, url: str) -> Transcript:
    """Fetch transcript — tries YouTube captions first, falls back to Whisper."""
    # Return cached result if already done
    transcript_json = _TRANSCRIPT_DIR / f"{video_id}.json"
    if transcript_json.exists():
        logger.info(f"Transcript already exists: {transcript_json}")
        data = json.loads(transcript_json.read_text(encoding="utf-8"))
        return Transcript(
            video_id=video_id,
            text=data["text"],
            language=data["language"],
            segments=data.get("segments", []),
            source=data.get("source", "captions"),
            transcript_path=_TRANSCRIPT_DIR / f"{video_id}.txt",
        )

    # --- Primary: YouTube captions (instant, free, no GPU) ---
    try:
        return _fetch_captions(video_id, url)
    except Exception as e:
        logger.warning(f"Captions not available for {video_id}: {e} — falling back to Whisper")

    # --- Fallback: local Whisper ---
    return _transcribe_whisper(video_id, url)


def _fetch_captions(video_id: str, url: str) -> Transcript:
    """Pull Telugu captions directly from YouTube. No audio download needed."""
    from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound

    logger.info(f"Fetching YouTube captions for {video_id} ...")
    api = YouTubeTranscriptApi()

    # Try Telugu first, then any available language
    try:
        snippets = api.fetch(video_id, languages=["te"])
        lang = "te"
    except NoTranscriptFound:
        # Try auto-translated Telugu if manual not available
        transcript_list = api.list(video_id)
        snippet_obj = transcript_list.find_generated_transcript(["te"])
        snippets = snippet_obj.fetch()
        lang = "te"

    # Build plain text and timed segments
    segments = [
        {"start": s.start, "duration": s.duration, "text": s.text}
        for s in snippets
    ]
    text = " ".join(s.text.strip() for s in snippets if s.text.strip())

    logger.info(f"Captions fetched: {len(text.split())} words, lang={lang}")
    return _save_transcript(video_id, text, lang, segments, source="captions")


def _transcribe_whisper(video_id: str, url: str) -> Transcript:
    """Download audio and transcribe with Whisper (fallback only)."""
    import yt_dlp
    import whisper

    _AUDIO_DIR = project_root() / "data" / "audio"
    _AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    # Check if audio already downloaded
    audio_path = None
    for ext in ("m4a", "webm", "mp3", "opus"):
        existing = _AUDIO_DIR / f"{video_id}.{ext}"
        if existing.exists():
            audio_path = existing
            break

    if not audio_path:
        logger.info(f"Downloading audio for {video_id} ...")
        ydl_opts = {
            "format": "140/bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio",
            "outtmpl": str(_AUDIO_DIR / f"{video_id}.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            ext = info.get("ext", "m4a")
        audio_path = _AUDIO_DIR / f"{video_id}.{ext}"

    model_name = env("WHISPER_MODEL", default="medium")
    logger.info(f"Transcribing with Whisper ({model_name}) ...")
    model = whisper.load_model(model_name)
    result = model.transcribe(
        str(audio_path),
        language="te",
        task="transcribe",
        word_timestamps=True,
        verbose=False,
    )

    text: str = result["text"].strip()
    lang: str = result.get("language", "te")
    segments: list[dict] = result.get("segments", [])

    logger.info(f"Whisper transcription: {len(text.split())} words")
    return _save_transcript(video_id, text, lang, segments, source="whisper")


def _save_transcript(
    video_id: str, text: str, language: str, segments: list[dict], source: str
) -> Transcript:
    transcript_json = _TRANSCRIPT_DIR / f"{video_id}.json"
    transcript_txt = _TRANSCRIPT_DIR / f"{video_id}.txt"

    transcript_json.write_text(
        json.dumps(
            {"video_id": video_id, "text": text, "language": language,
             "segments": segments, "source": source},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    transcript_txt.write_text(text, encoding="utf-8")

    with get_conn() as conn:
        conn.execute(
            "UPDATE videos SET status='transcribed', transcript_path=?, "
            "transcript_lang=?, updated_at=datetime('now') WHERE video_id=?",
            (str(transcript_txt), language, video_id),
        )

    log_event(video_id, "transcribe", f"Transcribed {len(text.split())} words via {source}")

    return Transcript(
        video_id=video_id, text=text, language=language,
        segments=segments, source=source, transcript_path=transcript_txt,
    )
