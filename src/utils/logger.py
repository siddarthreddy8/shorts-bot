from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
_LOG_DIR.mkdir(exist_ok=True)

logger.remove()
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
)
logger.add(
    _LOG_DIR / "pipeline.log",
    level="DEBUG",
    rotation="10 MB",
    retention="14 days",
    enqueue=True,
)
logger.add(
    _LOG_DIR / "error.log",
    level="ERROR",
    rotation="5 MB",
    retention="30 days",
    enqueue=True,
)

__all__ = ["logger"]
