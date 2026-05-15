from __future__ import annotations

import json
import subprocess
import sys

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.api.pipeline import get_progress, run_pipeline, run_upload
from src.db.database import get_conn
from src.script.rewriter import save_approved
from src.utils.config import project_root

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_SCRIPTS_DIR = project_root() / "data" / "scripts"
_VIDEOS_DIR = project_root() / "data" / "videos"
_AUDIO_DIR = project_root() / "remotion" / "public" / "audio"
_UI_DIST = project_root() / "src" / "ui" / "dist"


# ── Videos ───────────────────────────────────────────────────────────────────

@app.get("/api/videos")
def list_videos():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT video_id, source_title, source_channel_name, status,
                      updated_at, youtube_url, target_language, styles_json,
                      failure_reason
               FROM videos ORDER BY updated_at DESC LIMIT 50"""
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/videos/{video_id}/script")
def get_script(video_id: str):
    p = _SCRIPTS_DIR / f"{video_id}_draft.json"
    if not p.exists():
        raise HTTPException(404, "No draft script")
    return json.loads(p.read_text(encoding="utf-8"))


class ApproveBody(BaseModel):
    hook: str
    body: str
    cta: str
    seo_title: str | None = None
    seo_description: str | None = None
    seo_hashtags: list[str] | None = None
    seo_thumbnail_phrases: list[str] | None = None
    seo_thumbnail_phrase: str | None = None


@app.post("/api/videos/{video_id}/approve", status_code=202)
def approve(video_id: str, body: ApproveBody, background_tasks: BackgroundTasks):
    save_approved(video_id, body.hook, body.body, body.cta)
    wc = len(f"{body.hook}\n\n{body.body}\n\n{body.cta}".split())
    with get_conn() as conn:
        conn.execute(
            """UPDATE videos SET
               status='script_approved', script_word_count=?,
               seo_title=?, seo_description=?,
               seo_hashtags_json=?, seo_thumbnail_phrases_json=?,
               seo_thumbnail_phrase=?,
               updated_at=datetime('now')
               WHERE video_id=?""",
            (
                wc,
                body.seo_title,
                body.seo_description,
                json.dumps(body.seo_hashtags) if body.seo_hashtags is not None else None,
                json.dumps(body.seo_thumbnail_phrases) if body.seo_thumbnail_phrases is not None else None,
                body.seo_thumbnail_phrase,
                video_id,
            ),
        )
    background_tasks.add_task(run_pipeline, video_id)
    return {"status": "accepted"}


@app.get("/api/videos/{video_id}/seo")
def get_seo(video_id: str):
    with get_conn() as conn:
        row = conn.execute(
            """SELECT seo_title, seo_description, seo_hashtags_json,
                      seo_thumbnail_phrases_json, seo_thumbnail_phrase
               FROM videos WHERE video_id=?""",
            (video_id,),
        ).fetchone()
    if not row or not row["seo_title"]:
        raise HTTPException(404, "No SEO data")
    return {
        "title": row["seo_title"],
        "description": row["seo_description"],
        "hashtags": json.loads(row["seo_hashtags_json"] or "[]"),
        "thumbnail_phrases": json.loads(row["seo_thumbnail_phrases_json"] or "[]"),
        "thumbnail_phrase": row["seo_thumbnail_phrase"],
    }


@app.post("/api/videos/{video_id}/seo/generate")
def generate_seo(video_id: str):
    p = _SCRIPTS_DIR / f"{video_id}_draft.json"
    if not p.exists():
        raise HTTPException(404, "No draft script")
    draft = json.loads(p.read_text(encoding="utf-8"))
    script_text = (
        " ".join(draft.get("hooks", []))
        + "\n\n"
        + draft.get("body", "")
        + "\n\n"
        + draft.get("cta", "")
    )

    with get_conn() as conn:
        row = conn.execute(
            "SELECT source_title, target_language, styles_json FROM videos WHERE video_id=?",
            (video_id,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Video not found")

    topic_hint = row["source_title"] or ""
    language = row["target_language"] or "english"
    styles = json.loads(row["styles_json"] or '["documentary"]')

    from src.seo import generate_and_enrich
    metadata = generate_and_enrich(script_text, topic_hint, styles, language)

    with get_conn() as conn:
        conn.execute(
            """UPDATE videos SET
               seo_title=?, seo_description=?,
               seo_hashtags_json=?, seo_thumbnail_phrases_json=?,
               updated_at=datetime('now')
               WHERE video_id=?""",
            (
                metadata.title,
                metadata.description,
                json.dumps(metadata.hashtags),
                json.dumps(metadata.thumbnail_phrases),
                video_id,
            ),
        )

    return {
        "title": metadata.title,
        "description": metadata.description,
        "hashtags": metadata.hashtags,
        "thumbnail_phrases": metadata.thumbnail_phrases,
        "thumbnail_phrase": None,
    }


@app.get("/api/videos/{video_id}/status")
def get_status(video_id: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM videos WHERE video_id=?", (video_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Video not found")

    db_status = row["status"]
    progress = get_progress(video_id)

    if progress:
        steps = [{"name": s.name, "state": s.state, "error": s.error} for s in progress.steps]
    else:
        steps = _steps_from_db(db_status)

    return {"status": db_status, "steps": steps}


@app.get("/api/videos/{video_id}/preview")
def preview(video_id: str):
    p = _VIDEOS_DIR / f"{video_id}.mp4"
    if not p.exists():
        raise HTTPException(404, "Video not rendered yet")
    return FileResponse(str(p), media_type="video/mp4")


@app.post("/api/videos/{video_id}/publish", status_code=202)
def publish(video_id: str, background_tasks: BackgroundTasks):
    with get_conn() as conn:
        row = conn.execute("SELECT status FROM videos WHERE video_id=?", (video_id,)).fetchone()
    if not row or row["status"] != "video_rendered":
        raise HTTPException(400, "Video must be in video_rendered state to publish")
    background_tasks.add_task(run_upload, video_id)
    return {"status": "accepted"}


@app.post("/api/videos/{video_id}/retry", status_code=202)
def retry_video(video_id: str, background_tasks: BackgroundTasks):
    with get_conn() as conn:
        conn.execute(
            "UPDATE videos SET status='script_approved', failure_reason=NULL, updated_at=datetime('now') WHERE video_id=?",
            (video_id,),
        )
    background_tasks.add_task(run_pipeline, video_id)
    return {"status": "accepted"}


@app.post("/api/videos/{video_id}/dismiss", status_code=200)
def dismiss_video(video_id: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE videos SET status='skipped', updated_at=datetime('now') WHERE video_id=?",
            (video_id,),
        )
    return {"status": "ok"}


@app.get("/api/videos/{video_id}/transcript")
def get_transcript(video_id: str):
    import pathlib
    with get_conn() as conn:
        row = conn.execute(
            "SELECT transcript_path FROM videos WHERE video_id=?", (video_id,)
        ).fetchone()
    if not row or not row["transcript_path"]:
        raise HTTPException(404, "No transcript")
    p = pathlib.Path(row["transcript_path"])
    if not p.is_absolute():
        p = project_root() / p
    if not p.exists():
        raise HTTPException(404, "Transcript file not found")
    return {"text": p.read_text(encoding="utf-8")}


@app.post("/api/videos/{video_id}/reject-render", status_code=200)
def reject_render(video_id: str):
    p = _VIDEOS_DIR / f"{video_id}.mp4"
    if p.exists():
        p.unlink()
    with get_conn() as conn:
        conn.execute(
            "UPDATE videos SET status='script_approved', updated_at=datetime('now') WHERE video_id=?",
            (video_id,),
        )
    return {"status": "ok"}


class GenerateScriptBody(BaseModel):
    language: str = "english"
    styles: list[str] = ["documentary"]


@app.post("/api/videos/{video_id}/generate-script", status_code=202)
def api_generate_script(video_id: str, body: GenerateScriptBody, background_tasks: BackgroundTasks):
    with get_conn() as conn:
        conn.execute(
            "UPDATE videos SET target_language=?, styles_json=?, updated_at=datetime('now') WHERE video_id=?",
            (body.language, json.dumps(body.styles), video_id),
        )
    background_tasks.add_task(
        _subprocess_cmd, "generate-script", video_id,
        "--lang", body.language, "--styles", ",".join(body.styles),
    )
    return {"status": "accepted"}


@app.post("/api/videos/{video_id}/regenerate-script", status_code=202)
def regenerate_script(video_id: str, background_tasks: BackgroundTasks):
    p = _SCRIPTS_DIR / f"{video_id}_draft.json"
    if p.exists():
        p.unlink()
    with get_conn() as conn:
        conn.execute(
            "UPDATE videos SET status='transcribed', updated_at=datetime('now') WHERE video_id=?",
            (video_id,),
        )
    background_tasks.add_task(_subprocess_cmd, "generate-script", video_id)
    return {"status": "accepted"}


# ── Dashboard stats ───────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM videos GROUP BY status"
        ).fetchall()
    by_stage = {r["status"]: r["cnt"] for r in rows}
    return {
        "total": sum(by_stage.values()),
        "needs_review": by_stage.get("script_drafted", 0),
        "running": by_stage.get("script_approved", 0),
        "ready_to_publish": by_stage.get("video_rendered", 0),
        "uploaded": by_stage.get("uploaded", 0),
        "failed": by_stage.get("failed", 0),
        "by_stage": by_stage,
    }


@app.get("/api/channels")
def get_channels():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM channel_state ORDER BY last_polled_at DESC").fetchall()
    return [dict(r) for r in rows]


@app.get("/api/events")
def get_events(limit: int = Query(default=20, le=50)):
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT e.*, v.source_title FROM events e
               LEFT JOIN videos v ON e.video_id = v.video_id
               ORDER BY e.created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/costs")
def get_costs():
    with get_conn() as conn:
        scripts_generated = conn.execute(
            """SELECT COUNT(*) FROM videos
               WHERE status IN ('script_drafted','script_approved','video_rendered','uploaded')"""
        ).fetchone()[0]
    openrouter_cost = scripts_generated * 0.00016
    tts_chars = 0
    for p in _AUDIO_DIR.glob("*_captions.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            tts_chars += sum(len(c["word"]) + 1 for c in data.get("captions", []))
        except Exception:
            pass
    elevenlabs_cost = tts_chars / 1000 * 0.30
    return {
        "openrouter": openrouter_cost,
        "elevenlabs": elevenlabs_cost,
        "total": openrouter_cost + elevenlabs_cost,
        "tts_chars": tts_chars,
        "scripts": scripts_generated,
    }


# ── Global actions ────────────────────────────────────────────────────────────

@app.post("/api/actions/monitor", status_code=202)
def action_monitor(background_tasks: BackgroundTasks):
    background_tasks.add_task(_subprocess_cmd, "run")
    return {"status": "accepted"}


@app.post("/api/actions/run", status_code=202)
def action_run(background_tasks: BackgroundTasks):
    background_tasks.add_task(_subprocess_cmd, "run")
    return {"status": "accepted"}


class IngestBody(BaseModel):
    url: str
    language: str = "english"
    styles: list[str] = ["documentary"]


@app.post("/api/actions/ingest", status_code=202)
def action_ingest(body: IngestBody, background_tasks: BackgroundTasks):
    background_tasks.add_task(_subprocess_cmd, "run", "--url", body.url)
    return {"status": "accepted"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _steps_from_db(status: str) -> list[dict]:
    done = {"state": "done", "error": None}
    pending = {"state": "pending", "error": None}
    failed = {"state": "failed", "error": "Pipeline failed"}
    if status == "uploaded":
        return [{"name": n, **done} for n in ("Storyboard", "Render", "Upload")]
    if status == "video_rendered":
        return [{"name": "Storyboard", **done}, {"name": "Render", **done}, {"name": "Upload", **pending}]
    if status == "failed":
        return [{"name": "Storyboard", **failed}, {"name": "Render", **pending}, {"name": "Upload", **pending}]
    return [{"name": n, **pending} for n in ("Storyboard", "Render", "Upload")]


def _subprocess_cmd(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "src.main"] + list(args),
        cwd=str(project_root()),
        capture_output=True,
        timeout=600,
    )


# ── Serve built React bundle in production ────────────────────────────────────

if _UI_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_UI_DIST), html=True), name="ui")
