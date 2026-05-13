from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")


class SourceChannel(BaseModel):
    id: str
    name: str
    enabled: bool = True
    handle: str | None = None   # @handle without the @, for display/resolution
    shorts_only: bool = False   # if True, skip videos longer than 60s


class OutputConfig(BaseModel):
    language: str = "english"
    default_styles: list[str] = Field(default_factory=lambda: ["documentary"])
    visibility: str = "public"


class ScriptConfig(BaseModel):
    target_words_min: int = 90
    target_words_max: int = 180
    hook_variants: int = 3
    plagiarism_overlap_max: float = 0.30


class VideoConfig(BaseModel):
    width: int = 1080
    height: int = 1920
    fps: int = 30
    templates_dir: str = "./remotion/src/templates"
    output_dir: str = "./data/videos"


class UploadConfig(BaseModel):
    title_max_len: int = 60
    description_template: str = ""
    default_tags: list[str] = Field(default_factory=list)


class AppConfig(BaseModel):
    source_channels: list[SourceChannel]
    output: OutputConfig
    styles: list[str]
    script: ScriptConfig
    video: VideoConfig
    upload: UploadConfig


@lru_cache(maxsize=1)
def load_config() -> AppConfig:
    cfg_path = _ROOT / "config" / "config.yaml"
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"Missing config/config.yaml — copy config/config.example.yaml first."
        )
    with cfg_path.open("r", encoding="utf-8") as f:
        return AppConfig(**yaml.safe_load(f))


def env(key: str, default: str | None = None, required: bool = False) -> str | None:
    val = os.getenv(key, default)
    if required and not val:
        raise RuntimeError(f"Missing required env var: {key}")
    return val


def project_root() -> Path:
    return _ROOT
