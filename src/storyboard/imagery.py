from __future__ import annotations

from pathlib import Path

import httpx

from src.utils.config import env
from src.utils.logger import logger

# FAL synchronous endpoint — single API key, single request, returns when done.
_FAL_BASE = "https://fal.run"


def generate_image(prompt: str, output_path: Path, *, retries: int = 2) -> Path:
    """Generate a 9:16 image via FAL.ai FLUX-dev and save to disk."""
    if output_path.exists():
        logger.info(f"Image cached: {output_path.name}")
        return output_path

    api_key = env("FAL_API_KEY", required=True)
    model_id = env("FAL_MODEL", default="fal-ai/flux/dev")

    url = f"{_FAL_BASE}/{model_id}"
    payload = {
        "prompt": prompt,
        "image_size": "portrait_16_9",   # FAL preset — 9:16 portrait (1080x1920-ish)
        "num_inference_steps": 28,
        "guidance_scale": 3.5,
        "num_images": 1,
        "enable_safety_checker": False,
    }
    headers = {"Authorization": f"Key {api_key}"}

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            logger.info(f"FAL generating: {prompt[:80]}…")
            r = httpx.post(url, headers=headers, json=payload, timeout=180)
            r.raise_for_status()
            data = r.json()
            image_url = data["images"][0]["url"]

            # Download the generated image
            img_response = httpx.get(image_url, timeout=60)
            img_response.raise_for_status()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(img_response.content)
            logger.info(f"Saved: {output_path.name} ({len(img_response.content) // 1024} KB)")
            return output_path

        except httpx.HTTPStatusError as e:
            last_err = e
            logger.warning(
                f"FAL HTTP {e.response.status_code} (attempt {attempt + 1}/{retries + 1}): "
                f"{e.response.text[:200]}"
            )
        except Exception as e:
            last_err = e
            logger.warning(f"FAL error (attempt {attempt + 1}/{retries + 1}): {e}")

    raise RuntimeError(f"FAL image generation failed after {retries + 1} attempts: {last_err}")
