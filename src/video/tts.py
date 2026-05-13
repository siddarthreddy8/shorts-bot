from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path

from src.utils.config import env, project_root
from src.utils.logger import logger

_AUDIO_DIR = project_root() / "remotion" / "public" / "audio"


@dataclass
class TTSResult:
    audio_path: Path
    captions: list[dict]   # [{word, startMs, endMs}, ...]
    duration_sec: float


def generate_tts(video_id: str, script_text: str, language: str = "english") -> TTSResult:
    """ElevenLabs TTS → MP3 + word-level caption timestamps."""
    _AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    audio_path = _AUDIO_DIR / f"{video_id}.mp3"
    captions_path = _AUDIO_DIR / f"{video_id}_captions.json"

    if audio_path.exists() and captions_path.exists():
        logger.info(f"TTS cached: {audio_path}")
        data = json.loads(captions_path.read_text(encoding="utf-8"))
        return TTSResult(
            audio_path=audio_path,
            captions=data["captions"],
            duration_sec=data["duration_sec"],
        )

    from elevenlabs.client import ElevenLabs

    api_key = env("ELEVENLABS_API_KEY", required=True)
    voice_env = "ELEVENLABS_VOICE_ID_HI" if language == "hindi" else "ELEVENLABS_VOICE_ID_EN"
    voice_id = env(voice_env, required=True)

    client = ElevenLabs(api_key=api_key)

    clean_text = _strip_markdown(script_text)
    logger.info(f"Generating TTS for {video_id} (lang={language}, voice={voice_id[:8]}…, {len(clean_text.split())} words)")

    response = client.text_to_speech.convert_with_timestamps(
        voice_id=voice_id,
        text=clean_text,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )

    # SDK 1.x returns a plain dict
    audio_bytes = base64.b64decode(response["audio_base64"])
    audio_path.write_bytes(audio_bytes)
    logger.info(f"Audio saved: {audio_path} ({len(audio_bytes) // 1024} KB)")

    alignment = response["alignment"]
    captions = _build_word_captions(
        alignment["characters"],
        alignment["character_start_times_seconds"],
        alignment["character_end_times_seconds"],
    )
    duration_sec = captions[-1]["endMs"] / 1000 if captions else 0.0

    captions_path.write_text(
        json.dumps({"captions": captions, "duration_sec": duration_sec}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info(f"TTS done: {len(captions)} words, {duration_sec:.1f}s")
    return TTSResult(audio_path=audio_path, captions=captions, duration_sec=duration_sec)


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting before sending to TTS."""
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)  # bold/italic
    text = re.sub(r"_{1,3}(.+?)_{1,3}", r"\1", text)     # underscore variants
    return text.strip()


def _build_word_captions(
    chars: list[str],
    starts: list[float],
    ends: list[float],
) -> list[dict]:
    """Group character-level ElevenLabs timestamps into word-level captions."""
    captions: list[dict] = []
    word_chars: list[str] = []
    word_start: float | None = None
    word_end: float = 0.0

    for ch, s, e in zip(chars, starts, ends):
        if ch in (" ", "\n", "\r", "\t"):
            if word_chars:
                word = re.sub(r"[^\w''\-]", "", "".join(word_chars))
                if word:
                    captions.append({
                        "word": word,
                        "startMs": round(word_start * 1000),
                        "endMs": round(word_end * 1000),
                    })
                word_chars = []
                word_start = None
        else:
            word_chars.append(ch)
            if word_start is None:
                word_start = s
            word_end = e

    # flush last word
    if word_chars:
        word = re.sub(r"[^\w''\-]", "", "".join(word_chars))
        if word:
            captions.append({
                "word": word,
                "startMs": round(word_start * 1000),
                "endMs": round(word_end * 1000),
            })

    return captions
