from __future__ import annotations

import time
from pathlib import Path

import httpx

from src.utils.config import env
from src.utils.logger import logger

_FAL_BASE = "https://fal.run"
_FAL_QUEUE_BASE = "https://queue.fal.run"


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
        "image_size": "portrait_16_9",
        "num_inference_steps": 28,
        "guidance_scale": 3.5,
        "num_images": 1,
        "enable_safety_checker": False,
    }
    headers = {"Authorization": f"Key {api_key}"}

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            logger.info(f"FAL image: {prompt[:80]}…")
            r = httpx.post(url, headers=headers, json=payload, timeout=180)
            r.raise_for_status()
            image_url = r.json()["images"][0]["url"]
            img = httpx.get(image_url, timeout=60)
            img.raise_for_status()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(img.content)
            logger.info(f"Saved: {output_path.name} ({len(img.content) // 1024} KB)")
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


def submit_video_job(prompt: str, duration_sec: int = 5) -> tuple[str, str]:
    """Submit a video generation job to the FAL queue.

    Returns (model_id, request_id). Call poll_video_jobs() to wait for results.
    Kling v2.1 only supports 5 or 10 second durations.
    """
    api_key = env("FAL_API_KEY", required=True)
    model_id = env("FAL_VIDEO_MODEL", default="fal-ai/kling-video/v2.1/standard/text-to-video")

    clip_duration = "10" if duration_sec > 6 else "5"
    payload = {
        "prompt": prompt,
        "duration": clip_duration,
        "aspect_ratio": "9:16",
    }
    headers = {"Authorization": f"Key {api_key}"}

    url = f"{_FAL_QUEUE_BASE}/{model_id}"
    logger.info(f"FAL video submit ({clip_duration}s): {prompt[:80]}…")
    r = httpx.post(url, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    request_id = r.json()["request_id"]
    logger.info(f"  → {request_id}")
    return model_id, request_id


def poll_video_jobs(
    jobs: list[tuple[str, str]],
    *,
    timeout: int = 600,
) -> dict[str, dict | None]:
    """Poll a batch of FAL video jobs until all complete or timeout.

    Args:
        jobs: List of (model_id, request_id) from submit_video_job().
        timeout: Max seconds to wait across all jobs.

    Returns:
        {request_id: result_dict} for completed jobs,
        {request_id: None} for failed or timed-out jobs.
    """
    api_key = env("FAL_API_KEY", required=True)
    headers = {"Authorization": f"Key {api_key}"}

    pending: dict[str, str] = {rid: model_id for model_id, rid in jobs}
    results: dict[str, dict | None] = {}
    deadline = time.time() + timeout

    while pending and time.time() < deadline:
        for rid, model_id in list(pending.items()):
            try:
                status_url = f"{_FAL_QUEUE_BASE}/{model_id}/requests/{rid}/status"
                r = httpx.get(status_url, headers=headers, timeout=30)
                r.raise_for_status()
                status = r.json().get("status")

                if status == "COMPLETED":
                    result_url = f"{_FAL_QUEUE_BASE}/{model_id}/requests/{rid}"
                    rr = httpx.get(result_url, headers=headers, timeout=30)
                    rr.raise_for_status()
                    results[rid] = rr.json()
                    del pending[rid]
                    logger.info(f"FAL {rid}: COMPLETED")
                elif status in ("FAILED", "CANCELLED"):
                    results[rid] = None
                    del pending[rid]
                    logger.warning(f"FAL {rid}: {status}")
            except Exception as e:
                logger.warning(f"FAL poll error for {rid}: {e}")

        if pending:
            logger.info(f"FAL: {len(pending)} job(s) still running…")
            time.sleep(8)

    for rid in pending:
        results[rid] = None
        logger.warning(f"FAL {rid}: timed out after {timeout}s")

    return results


def download_video(result: dict, output_path: Path) -> Path:
    """Download a video from a completed FAL job result dict."""
    video_url = result["video"]["url"]
    logger.info(f"Downloading: {output_path.name}")
    vid = httpx.get(video_url, timeout=120)
    vid.raise_for_status()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(vid.content)
    logger.info(f"Saved: {output_path.name} ({len(vid.content) // 1024} KB)")
    return output_path
