from __future__ import annotations

import io
import sys

# Force UTF-8 output on Windows so Telugu titles don't crash the terminal
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import click

from src.db.database import init_db
from src.utils.logger import logger


@click.group()
def cli() -> None:
    """Shorts Bot - Telugu to Hindi/English YouTube Shorts pipeline."""


@cli.command("init")
def cmd_init() -> None:
    """Initialize local SQLite DB and verify config."""
    init_db()
    logger.info("Initialization complete.")


@cli.command("run")
@click.option("--url", default=None, help="Process a specific YouTube URL (skips channel poll).")
def cmd_run(url: str | None) -> None:
    """Run the full pipeline end-to-end."""
    from src.monitor.youtube_monitor import fetch_from_url, poll_channels
    from src.transcribe.whisper_transcriber import run as transcribe_run

    init_db()

    if url:
        videos = []
        meta = fetch_from_url(url)
        if meta:
            videos = [meta]
    else:
        videos = poll_channels()

    if not videos:
        logger.info("No new videos to process.")
        return

    for video in videos:
        logger.info(f"Processing: [{video.video_id}] {video.title}")
        try:
            transcript = transcribe_run(video.video_id, video.url)
            logger.info(
                f"Transcript ready: {len(transcript.text.split())} words — "
                f"open review UI to continue."
            )
        except Exception as e:
            logger.error(f"Failed to process {video.video_id}: {e}")


@cli.command("run-pipeline")
def cmd_run_pipeline() -> None:
    """Run full automated pipeline end-to-end, then stop the EC2 instance.

    Intended for cloud use: EventBridge starts the instance, this command
    runs on boot via systemd, and stops the instance when done.
    Locally it behaves the same but skips the shutdown step.
    """
    from src.pipeline.runner import run
    run()


@cli.command("monitor")
def cmd_monitor() -> None:
    """Poll source channels for new videos and save to DB."""
    from src.monitor.youtube_monitor import poll_channels
    init_db()
    videos = poll_channels()
    if videos:
        for v in videos:
            click.echo(f"  New: [{v.video_id}] {v.title} — {v.url}")
    else:
        click.echo("No new videos found.")


@cli.command("transcribe")
@click.argument("video_id")
@click.argument("url")
def cmd_transcribe(video_id: str, url: str) -> None:
    """Transcribe a specific video by ID and URL."""
    from src.transcribe.whisper_transcriber import run as transcribe_run
    init_db()
    transcript = transcribe_run(video_id, url)
    click.echo(f"Done. Transcript saved to: {transcript.transcript_path}")


@cli.command("generate-script")
@click.argument("video_id")
@click.option("--lang", default="english", type=click.Choice(["english", "hindi"]), help="Output language.")
@click.option("--styles", default="documentary", help="Comma-separated styles e.g. documentary,comedy")
def cmd_generate_script(video_id: str, lang: str, styles: str) -> None:
    """Generate a Shorts script from an already-transcribed video."""
    from src.script.rewriter import generate
    from src.db.database import get_conn
    import json

    with get_conn() as conn:
        row = conn.execute(
            "SELECT transcript_path FROM videos WHERE video_id=?", (video_id,)
        ).fetchone()

    if not row or not row["transcript_path"]:
        click.echo(f"No transcript found for {video_id}. Run: python -m src.main transcribe {video_id} <url>")
        return

    transcript = open(row["transcript_path"], encoding="utf-8").read()
    style_list = [s.strip() for s in styles.split(",") if s.strip()]

    result = generate(video_id, transcript, language=lang, styles=style_list)

    click.echo(f"\n{'='*60}")
    click.echo(f"SCRIPT ({result.word_count} words | {lang} | {', '.join(style_list)})")
    click.echo(f"{'='*60}")
    click.echo("\n--- HOOKS (pick one in review UI) ---")
    for i, hook in enumerate(result.hooks, 1):
        click.echo(f"  [{i}] {hook}")
    click.echo("\n--- BODY ---")
    click.echo(result.body)
    click.echo("\n--- CTA ---")
    click.echo(result.cta)
    click.echo(f"\nSaved to: {result.script_path}")


@cli.command("storyboard")
@click.argument("video_id")
@click.option("--regenerate", is_flag=True, help="Force regenerate even if cached.")
def cmd_storyboard(video_id: str, regenerate: bool) -> None:
    """Plan visual scenes + generate AI imagery for an approved script."""
    from src.storyboard.generator import build as build_storyboard
    init_db()
    sb = build_storyboard(video_id, regenerate=regenerate)
    click.echo(f"Done. {len(sb.scenes)} scenes → {sb.storyboard_path}")


@cli.command("render")
@click.argument("video_id")
@click.option(
    "--composition",
    default=None,
    type=click.Choice(["HoogTypography", "HoogMap", "HoogScene"]),
    help="Remotion composition to use (auto-detected if omitted).",
)
@click.option("--regenerate", is_flag=True, help="Force re-render even if video already exists.")
def cmd_render(video_id: str, composition: str | None, regenerate: bool) -> None:
    """Generate TTS audio + render Remotion video for an approved script."""
    from src.video.generator import render as video_render
    init_db()
    result = video_render(video_id, composition=composition, regenerate=regenerate)
    click.echo(f"Done. Video: {result.video_path}")


@cli.command("upload")
@click.argument("video_id")
def cmd_upload(video_id: str) -> None:
    """Upload a rendered Short to YouTube."""
    from src.upload.uploader import upload
    init_db()
    result = upload(video_id)
    click.echo(f"Uploaded: {result.youtube_url}")


@cli.command("review-ui")
def cmd_review_ui() -> None:
    """Launch the Streamlit script review UI."""
    import subprocess
    from pathlib import Path
    app_path = Path(__file__).parent / "review" / "app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_path)], check=True)


if __name__ == "__main__":
    cli()
