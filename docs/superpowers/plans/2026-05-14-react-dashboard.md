# React Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Streamlit review UI with a React + FastAPI dashboard where script approval auto-fires the full pipeline (storyboard → render → upload) and shows live step-by-step progress.

**Architecture:** FastAPI backend wraps existing Python pipeline functions. React/Vite frontend polls `/api` endpoints. Background tasks tracked in an in-memory dict per video_id. In production, FastAPI serves the built React bundle.

**Tech Stack:** Python 3.x, FastAPI, uvicorn, React 18, TypeScript, Vite

---

## Files Created/Modified

| File | Action | Purpose |
|------|--------|---------|
| `src/api/__init__.py` | Create | Package marker |
| `src/api/pipeline.py` | Create | In-memory progress tracking + background orchestrator |
| `src/api/main.py` | Create | All FastAPI endpoints |
| `requirements.txt` | Modify | Add fastapi, uvicorn[standard] |
| `src/ui/package.json` | Create | React app deps |
| `src/ui/vite.config.ts` | Create | Proxy /api → :8000 |
| `src/ui/tsconfig.json` | Create | TypeScript config |
| `src/ui/index.html` | Create | HTML entry |
| `src/ui/src/lib/types.ts` | Create | Shared TypeScript types |
| `src/ui/src/lib/api.ts` | Create | Typed fetch wrappers |
| `src/ui/src/hooks/useVideos.ts` | Create | Queue polling hook |
| `src/ui/src/hooks/useVideoStatus.ts` | Create | Per-video status polling hook |
| `src/ui/src/components/StatusBadge.tsx` | Create | Colored status pill |
| `src/ui/src/components/StepTracker.tsx` | Create | Storyboard→Render→Upload pill chain |
| `src/ui/src/components/ScriptReview.tsx` | Create | Inline hook picker + body/CTA editor + approve |
| `src/ui/src/components/VideoCard.tsx` | Create | Single queue item, all three states |
| `src/ui/src/components/VideoQueue.tsx` | Create | Sorted list of VideoCards |
| `src/ui/src/App.tsx` | Create | Root with header + queue |
| `src/ui/src/main.tsx` | Create | React DOM entry |
| `src/ui/src/index.css` | Create | All styles (dark theme, design tokens) |
| `start_ui.sh` | Create | Launch both servers |
| `start_ui.bat` | Create | Windows launcher |

---

### Task 1: FastAPI backend

**Files:**
- Create: `src/api/__init__.py`
- Create: `src/api/pipeline.py`
- Create: `src/api/main.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add FastAPI deps to requirements.txt**

Append to `requirements.txt`:
```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
```

- [ ] **Step 2: Create `src/api/__init__.py`**

Empty file — just a package marker.

- [ ] **Step 3: Create `src/api/pipeline.py`**

```python
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Literal

from src.utils.logger import logger

StepState = Literal["pending", "running", "done", "failed"]

@dataclass
class StepStatus:
    name: str
    state: StepState = "pending"
    error: str | None = None

@dataclass
class VideoProgress:
    steps: list[StepStatus] = field(default_factory=lambda: [
        StepStatus("Storyboard"),
        StepStatus("Render"),
        StepStatus("Upload"),
    ])

_progress: dict[str, VideoProgress] = {}
_lock = threading.Lock()


def get_progress(video_id: str) -> VideoProgress | None:
    with _lock:
        return _progress.get(video_id)


def run_pipeline(video_id: str) -> None:
    """Storyboard → render → upload. Updates in-memory progress each step."""
    prog = VideoProgress()
    with _lock:
        _progress[video_id] = prog

    _run_step(prog, 0, "Storyboard", _do_storyboard, video_id)
    if prog.steps[0].state == "failed":
        return

    _run_step(prog, 1, "Render", _do_render, video_id)
    if prog.steps[1].state == "failed":
        return

    _run_step(prog, 2, "Upload", _do_upload, video_id)


def _run_step(prog: VideoProgress, idx: int, name: str, fn, video_id: str) -> None:
    with _lock:
        prog.steps[idx].state = "running"
    try:
        fn(video_id)
        with _lock:
            prog.steps[idx].state = "done"
    except Exception as e:
        logger.error(f"Pipeline step {name} failed for {video_id}: {e}")
        with _lock:
            prog.steps[idx].state = "failed"
            prog.steps[idx].error = str(e)


def _do_storyboard(video_id: str) -> None:
    from src.storyboard.generator import build
    build(video_id)


def _do_render(video_id: str) -> None:
    from src.video.generator import render
    render(video_id)


def _do_upload(video_id: str) -> None:
    from src.upload.uploader import upload
    upload(video_id)
```

- [ ] **Step 4: Create `src/api/main.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

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


# ── Serve built React bundle in production ────────────────────────────────────

if _UI_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_UI_DIST), html=True), name="ui")
```

- [ ] **Step 5: Install FastAPI deps**

```bash
cd /d/siddarth/youtube/shorts-bot
pip install fastapi "uvicorn[standard]"
```

---

### Task 2: React app scaffold

**Files:**
- Create: `src/ui/package.json`
- Create: `src/ui/vite.config.ts`
- Create: `src/ui/tsconfig.json`
- Create: `src/ui/index.html`

- [ ] **Step 1: Create `src/ui/package.json`**

```json
{
  "name": "shorts-bot-ui",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.11",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.6.2",
    "vite": "^5.4.0"
  }
}
```

- [ ] **Step 2: Create `src/ui/vite.config.ts`**

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

- [ ] **Step 3: Create `src/ui/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create `src/ui/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Shorts Bot</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Install npm deps**

```bash
cd /d/siddarth/youtube/shorts-bot/src/ui
npm install
```

---

### Task 3: Types + API client

**Files:**
- Create: `src/ui/src/lib/types.ts`
- Create: `src/ui/src/lib/api.ts`

- [ ] **Step 1: Create `src/ui/src/lib/types.ts`**

```ts
export type PipelineStatus =
  | 'discovered' | 'transcribed' | 'script_drafted'
  | 'script_approved' | 'video_rendered' | 'uploaded'
  | 'failed' | 'skipped'

export type StepState = 'pending' | 'running' | 'done' | 'failed'

export interface Step {
  name: string
  state: StepState
  error: string | null
}

export interface Video {
  video_id: string
  source_title: string | null
  source_channel_name: string | null
  status: PipelineStatus
  updated_at: string
  youtube_url: string | null
}

export interface VideoStatus {
  status: PipelineStatus
  steps: Step[]
}

export interface DraftScript {
  hooks: string[]
  body: string
  cta: string
  word_count: number
  language: string
  styles: string[]
}
```

- [ ] **Step 2: Create `src/ui/src/lib/api.ts`**

```ts
import type { DraftScript, Video, VideoStatus } from './types'

const BASE = '/api'

export async function fetchVideos(): Promise<Video[]> {
  const r = await fetch(`${BASE}/videos`)
  if (!r.ok) throw new Error('Failed to fetch videos')
  return r.json()
}

export async function fetchScript(videoId: string): Promise<DraftScript> {
  const r = await fetch(`${BASE}/videos/${videoId}/script`)
  if (!r.ok) throw new Error('No draft script')
  return r.json()
}

export async function approveScript(
  videoId: string,
  hook: string,
  body: string,
  cta: string,
): Promise<void> {
  const r = await fetch(`${BASE}/videos/${videoId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ hook, body, cta }),
  })
  if (!r.ok) throw new Error('Approve failed')
}

export async function fetchStatus(videoId: string): Promise<VideoStatus> {
  const r = await fetch(`${BASE}/videos/${videoId}/status`)
  if (!r.ok) throw new Error('Status fetch failed')
  return r.json()
}

export function previewUrl(videoId: string): string {
  return `${BASE}/videos/${videoId}/preview`
}
```

---

### Task 4: Hooks

**Files:**
- Create: `src/ui/src/hooks/useVideos.ts`
- Create: `src/ui/src/hooks/useVideoStatus.ts`

- [ ] **Step 1: Create `src/ui/src/hooks/useVideos.ts`**

```ts
import { useEffect, useState } from 'react'
import { fetchVideos } from '../lib/api'
import type { Video } from '../lib/types'

export function useVideos(intervalMs = 5000) {
  const [videos, setVideos] = useState<Video[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const data = await fetchVideos()
        if (active) setVideos(data)
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    const id = setInterval(load, intervalMs)
    return () => {
      active = false
      clearInterval(id)
    }
  }, [intervalMs])

  return { videos, loading }
}
```

- [ ] **Step 2: Create `src/ui/src/hooks/useVideoStatus.ts`**

```ts
import { useEffect, useState } from 'react'
import { fetchStatus } from '../lib/api'
import type { PipelineStatus, VideoStatus } from '../lib/types'

const IN_PROGRESS: PipelineStatus[] = ['script_approved']

export function useVideoStatus(videoId: string, status: PipelineStatus) {
  const [videoStatus, setVideoStatus] = useState<VideoStatus | null>(null)

  useEffect(() => {
    if (!IN_PROGRESS.includes(status)) {
      setVideoStatus(null)
      return
    }
    let active = true
    const poll = async () => {
      try {
        const data = await fetchStatus(videoId)
        if (active) setVideoStatus(data)
      } catch { /* swallow — retry next interval */ }
    }
    poll()
    const id = setInterval(poll, 2000)
    return () => {
      active = false
      clearInterval(id)
    }
  }, [videoId, status])

  return videoStatus
}
```

---

### Task 5: Components

**Files:**
- Create: `src/ui/src/components/StatusBadge.tsx`
- Create: `src/ui/src/components/StepTracker.tsx`
- Create: `src/ui/src/components/ScriptReview.tsx`
- Create: `src/ui/src/components/VideoCard.tsx`
- Create: `src/ui/src/components/VideoQueue.tsx`

- [ ] **Step 1: Create `src/ui/src/components/StatusBadge.tsx`**

```tsx
import type { PipelineStatus } from '../lib/types'

const CONFIG: Record<string, { label: string; color: string }> = {
  discovered:      { label: 'DISCOVERED',  color: 'var(--c-dim)' },
  transcribed:     { label: 'TRANSCRIBED', color: 'var(--c-dim)' },
  script_drafted:  { label: 'NEEDS REVIEW',color: 'var(--c-gold)' },
  script_approved: { label: 'RUNNING',     color: 'var(--c-blue)' },
  video_rendered:  { label: 'RENDERING',   color: 'var(--c-blue)' },
  uploaded:        { label: 'UPLOADED',    color: 'var(--c-green)' },
  failed:          { label: 'FAILED',      color: 'var(--c-red)' },
  skipped:         { label: 'SKIPPED',     color: 'var(--c-dim)' },
}

export function StatusBadge({ status }: { status: PipelineStatus }) {
  const { label, color } = CONFIG[status] ?? { label: status.toUpperCase(), color: 'var(--c-dim)' }
  return (
    <span style={{
      fontFamily: 'var(--font-mono)',
      fontSize: '0.65rem',
      fontWeight: 500,
      letterSpacing: '0.08em',
      color,
      border: `1px solid ${color}`,
      borderRadius: 2,
      padding: '2px 7px',
    }}>
      {label}
    </span>
  )
}
```

- [ ] **Step 2: Create `src/ui/src/components/StepTracker.tsx`**

```tsx
import type { Step } from '../lib/types'

export function StepTracker({ steps }: { steps: Step[] }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginTop: 12 }}>
      {steps.map((step, i) => (
        <div key={step.name} style={{ display: 'flex', alignItems: 'center' }}>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.7rem',
              fontWeight: 500,
              letterSpacing: '0.06em',
              padding: '3px 12px',
              borderRadius: 20,
              background: step.state === 'done'    ? 'var(--c-gold)'
                        : step.state === 'running' ? 'transparent'
                        : step.state === 'failed'  ? 'var(--c-red)'
                        : 'transparent',
              color: step.state === 'done'    ? '#000'
                   : step.state === 'running' ? 'var(--c-gold)'
                   : step.state === 'failed'  ? '#fff'
                   : 'var(--c-muted)',
              border: step.state === 'running' ? '1px solid var(--c-gold)'
                    : step.state === 'failed'  ? '1px solid var(--c-red)'
                    : '1px solid transparent',
              animation: step.state === 'running' ? 'pulse 1.5s ease-in-out infinite' : 'none',
            }}
          >
            {step.state === 'done' ? '✓ ' : ''}{step.name}
          </span>
          {i < steps.length - 1 && (
            <span style={{ color: 'var(--c-muted)', padding: '0 4px', fontSize: '0.7rem' }}>→</span>
          )}
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Create `src/ui/src/components/ScriptReview.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { approveScript, fetchScript } from '../lib/api'
import type { DraftScript } from '../lib/types'

export function ScriptReview({
  videoId,
  onApproved,
}: {
  videoId: string
  onApproved: () => void
}) {
  const [draft, setDraft] = useState<DraftScript | null>(null)
  const [hookIdx, setHookIdx] = useState(0)
  const [body, setBody] = useState('')
  const [cta, setCta] = useState('')
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    fetchScript(videoId).then((d) => {
      setDraft(d)
      setBody(d.body)
      setCta(d.cta)
      setLoading(false)
    })
  }, [videoId])

  if (loading || !draft) return <p style={{ color: 'var(--c-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>Loading draft…</p>

  const wc = `${draft.hooks[hookIdx]} ${body} ${cta}`.split(/\s+/).filter(Boolean).length
  const wcOk = wc >= 90 && wc <= 180

  const handleApprove = async () => {
    setSubmitting(true)
    try {
      await approveScript(videoId, draft.hooks[hookIdx], body, cta)
      onApproved()
    } catch {
      setSubmitting(false)
    }
  }

  return (
    <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Hook selector */}
      <div>
        <label style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'var(--c-muted)', letterSpacing: '0.08em' }}>HOOK</label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 8 }}>
          {draft.hooks.map((h, i) => (
            <button
              key={i}
              onClick={() => setHookIdx(i)}
              style={{
                background: i === hookIdx ? 'rgba(255,217,61,0.08)' : 'var(--c-surface)',
                border: i === hookIdx ? '1px solid var(--c-gold)' : '1px solid var(--c-border)',
                borderRadius: 4,
                padding: '10px 12px',
                color: i === hookIdx ? 'var(--c-gold)' : 'var(--c-text)',
                fontSize: '0.82rem',
                textAlign: 'left',
                cursor: 'pointer',
                lineHeight: 1.4,
                boxShadow: i === hookIdx ? '0 0 12px rgba(255,217,61,0.15)' : 'none',
                transition: 'all 0.15s',
              }}
            >
              {h}
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div>
        <label style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'var(--c-muted)', letterSpacing: '0.08em' }}>BODY</label>
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={5}
          style={{
            width: '100%',
            marginTop: 8,
            background: 'var(--c-surface)',
            border: '1px solid var(--c-border)',
            borderRadius: 4,
            color: 'var(--c-text)',
            fontFamily: 'var(--font-sans)',
            fontSize: '0.88rem',
            lineHeight: 1.6,
            padding: '10px 12px',
            resize: 'vertical',
            boxSizing: 'border-box',
          }}
        />
      </div>

      {/* CTA */}
      <div>
        <label style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'var(--c-muted)', letterSpacing: '0.08em' }}>CTA</label>
        <input
          value={cta}
          onChange={(e) => setCta(e.target.value)}
          style={{
            width: '100%',
            marginTop: 8,
            background: 'var(--c-surface)',
            border: '1px solid var(--c-border)',
            borderRadius: 4,
            color: 'var(--c-text)',
            fontFamily: 'var(--font-sans)',
            fontSize: '0.88rem',
            padding: '10px 12px',
            boxSizing: 'border-box',
          }}
        />
      </div>

      {/* Word count + approve */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.75rem',
          color: wcOk ? 'var(--c-green)' : 'var(--c-red)',
        }}>
          {wc} words {wcOk ? '✓' : `(target 90–180)`}
        </span>
        <button
          onClick={handleApprove}
          disabled={submitting}
          style={{
            flex: 1,
            background: submitting ? 'var(--c-border)' : 'var(--c-gold)',
            color: '#000',
            border: 'none',
            padding: '12px',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.8rem',
            fontWeight: 600,
            letterSpacing: '0.1em',
            cursor: submitting ? 'not-allowed' : 'pointer',
            borderRadius: 2,
            transition: 'opacity 0.15s',
          }}
        >
          {submitting ? 'STARTING PIPELINE…' : 'APPROVE & RUN'}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Create `src/ui/src/components/VideoCard.tsx`**

```tsx
import { useState } from 'react'
import type { Video } from '../lib/types'
import { previewUrl } from '../lib/api'
import { useVideoStatus } from '../hooks/useVideoStatus'
import { ScriptReview } from './ScriptReview'
import { StatusBadge } from './StatusBadge'
import { StepTracker } from './StepTracker'

function timeAgo(iso: string): string {
  const diff = (Date.now() - new Date(iso + 'Z').getTime()) / 1000
  if (diff < 60) return `${Math.round(diff)}s ago`
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`
  return `${Math.round(diff / 86400)}d ago`
}

export function VideoCard({ video, onRefresh }: { video: Video; onRefresh: () => void }) {
  const [expanded, setExpanded] = useState(false)
  const liveStatus = useVideoStatus(video.video_id, video.status)

  const canExpand = video.status === 'script_drafted'
  const isRunning = video.status === 'script_approved'
  const isDone = video.status === 'uploaded'
  const isFailed = video.status === 'failed'
  const hasPreview = video.status === 'video_rendered' || video.status === 'uploaded'

  const steps = liveStatus?.steps ?? (
    isRunning || isDone || isFailed ? [
      { name: 'Storyboard', state: 'pending' as const, error: null },
      { name: 'Render',     state: 'pending' as const, error: null },
      { name: 'Upload',     state: 'pending' as const, error: null },
    ] : null
  )

  return (
    <div
      onClick={canExpand ? () => setExpanded((v) => !v) : undefined}
      style={{
        background: 'var(--c-card)',
        border: `1px solid ${expanded ? 'var(--c-gold)' : 'var(--c-border)'}`,
        borderRadius: 6,
        padding: '16px 20px',
        cursor: canExpand ? 'pointer' : 'default',
        transition: 'border-color 0.15s',
      }}
    >
      {/* Card header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{
            margin: 0,
            fontSize: '0.95rem',
            fontWeight: 500,
            color: 'var(--c-text)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}>
            {video.source_title ?? video.video_id}
          </p>
          <p style={{ margin: '4px 0 0', fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--c-muted)' }}>
            {video.source_channel_name ?? '—'} · {timeAgo(video.updated_at)}
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <StatusBadge status={liveStatus?.status ?? video.status} />
          {canExpand && (
            <span style={{ color: 'var(--c-muted)', fontSize: '0.8rem' }}>{expanded ? '▲' : '▼'}</span>
          )}
        </div>
      </div>

      {/* Step tracker for running videos */}
      {steps && <StepTracker steps={steps} />}

      {/* YouTube link for uploaded videos */}
      {isDone && video.youtube_url && (
        <a
          href={video.youtube_url}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          style={{ display: 'block', marginTop: 10, fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--c-gold)' }}
        >
          ↗ {video.youtube_url}
        </a>
      )}

      {/* Inline video preview */}
      {hasPreview && (
        <video
          src={previewUrl(video.video_id)}
          controls
          onClick={(e) => e.stopPropagation()}
          style={{ marginTop: 12, width: '100%', maxHeight: 240, borderRadius: 4, background: '#000' }}
        />
      )}

      {/* Inline script review */}
      {expanded && canExpand && (
        <div onClick={(e) => e.stopPropagation()}>
          <ScriptReview
            videoId={video.video_id}
            onApproved={() => {
              setExpanded(false)
              onRefresh()
            }}
          />
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 5: Create `src/ui/src/components/VideoQueue.tsx`**

```tsx
import { useVideos } from '../hooks/useVideos'
import { VideoCard } from './VideoCard'

export function VideoQueue() {
  const { videos, loading } = useVideos()

  if (loading) {
    return <p style={{ color: 'var(--c-muted)', fontFamily: 'var(--font-mono)', textAlign: 'center', marginTop: 60 }}>Loading queue…</p>
  }

  if (videos.length === 0) {
    return <p style={{ color: 'var(--c-muted)', fontFamily: 'var(--font-mono)', textAlign: 'center', marginTop: 60 }}>No videos in pipeline yet.</p>
  }

  const pending = videos.filter((v) => v.status === 'script_drafted').length

  return (
    <div>
      {pending > 0 && (
        <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--c-gold)', marginBottom: 16, letterSpacing: '0.06em' }}>
          ● {pending} NEED{pending === 1 ? 'S' : ''} REVIEW
        </p>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {videos.map((v) => (
          <VideoCard key={v.video_id} video={v} onRefresh={() => {}} />
        ))}
      </div>
    </div>
  )
}
```

---

### Task 6: App shell + styles

**Files:**
- Create: `src/ui/src/main.tsx`
- Create: `src/ui/src/App.tsx`
- Create: `src/ui/src/index.css`

- [ ] **Step 1: Create `src/ui/src/main.tsx`**

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { App } from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 2: Create `src/ui/src/App.tsx`**

```tsx
import { VideoQueue } from './components/VideoQueue'

export function App() {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--c-bg)' }}>
      <header style={{
        position: 'sticky',
        top: 0,
        zIndex: 10,
        background: 'rgba(8,12,24,0.92)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--c-border)',
        padding: '0 32px',
        height: 52,
        display: 'flex',
        alignItems: 'center',
      }}>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontWeight: 500,
          fontSize: '0.85rem',
          letterSpacing: '0.15em',
          color: 'var(--c-gold)',
        }}>
          SHORTS BOT
        </span>
      </header>
      <main style={{ maxWidth: 820, margin: '0 auto', padding: '32px 24px' }}>
        <VideoQueue />
      </main>
    </div>
  )
}
```

- [ ] **Step 3: Create `src/ui/src/index.css`**

```css
:root {
  --c-bg:      #080c18;
  --c-card:    #0f1420;
  --c-surface: #141928;
  --c-border:  #1e2a45;
  --c-text:    #e8eaf0;
  --c-muted:   #4a5578;
  --c-gold:    #ffd93d;
  --c-blue:    #3b82f6;
  --c-green:   #22c55e;
  --c-red:     #ef4444;
  --c-dim:     #4a5578;

  --font-sans: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
}

*, *::before, *::after { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--c-bg);
  color: var(--c-text);
  font-family: var(--font-sans);
  -webkit-font-smoothing: antialiased;
}

textarea, input, button { outline: none; }

textarea:focus, input:focus {
  border-color: var(--c-gold) !important;
  box-shadow: 0 0 0 2px rgba(255, 217, 61, 0.1);
}

button:hover:not(:disabled) { opacity: 0.88; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.45; }
}

::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--c-bg); }
::-webkit-scrollbar-thumb { background: var(--c-border); border-radius: 3px; }
```

---

### Task 7: Startup scripts

**Files:**
- Create: `start_ui.sh`
- Create: `start_ui.bat`

- [ ] **Step 1: Create `start_ui.sh`**

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "Starting FastAPI backend..."
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

echo "Starting React frontend..."
cd src/ui
npm run dev &
FRONTEND_PID=$!

echo ""
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop both."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
```

- [ ] **Step 2: Create `start_ui.bat`**

```bat
@echo off
cd /d "%~dp0"

echo Starting FastAPI backend...
start "FastAPI" cmd /c "uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload"

echo Starting React frontend...
cd src\ui
start "React" cmd /c "npm run dev"

echo.
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo.
echo Close the two opened windows to stop.
```
