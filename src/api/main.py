from __future__ import annotations

import json

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.api.pipeline import get_progress, run_pipeline
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
_UI_DIST = project_root() / "src" / "ui" / "dist"


# ── API routes ────────────────────────────────────────────────────────────────

@app.get("/api/videos")
def list_videos():
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT video_id, source_title, source_channel_name, status,
                      updated_at, youtube_url
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


@app.post("/api/videos/{video_id}/approve", status_code=202)
def approve(video_id: str, body: ApproveBody, background_tasks: BackgroundTasks):
    save_approved(video_id, body.hook, body.body, body.cta)
    wc = len(f"{body.hook}\n\n{body.body}\n\n{body.cta}".split())
    with get_conn() as conn:
        conn.execute(
            "UPDATE videos SET status='script_approved', script_word_count=?, "
            "updated_at=datetime('now') WHERE video_id=?",
            (wc, video_id),
        )
    background_tasks.add_task(run_pipeline, video_id)
    return {"status": "accepted"}


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
        steps = [
            {"name": s.name, "state": s.state, "error": s.error}
            for s in progress.steps
        ]
    else:
        steps = _steps_from_db(db_status)

    return {"status": db_status, "steps": steps}


@app.get("/api/videos/{video_id}/preview")
def preview(video_id: str):
    p = _VIDEOS_DIR / f"{video_id}.mp4"
    if not p.exists():
        raise HTTPException(404, "Video not rendered yet")
    return FileResponse(str(p), media_type="video/mp4")


def _steps_from_db(status: str) -> list[dict]:
    done    = {"state": "done",    "error": None}
    pending = {"state": "pending", "error": None}
    failed  = {"state": "failed",  "error": "Pipeline failed"}
    if status == "uploaded":
        return [{"name": n, **done} for n in ("Storyboard", "Render", "Upload")]
    if status == "video_rendered":
        return [{"name": "Storyboard", **done}, {"name": "Render", **done}, {"name": "Upload", **pending}]
    if status == "failed":
        return [{"name": "Storyboard", **failed}, {"name": "Render", **pending}, {"name": "Upload", **pending}]
    return [{"name": n, **pending} for n in ("Storyboard", "Render", "Upload")]


# ── Serve built React bundle in production ────────────────────────────────────

if _UI_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_UI_DIST), html=True), name="ui")
