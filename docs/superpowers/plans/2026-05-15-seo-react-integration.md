# SEO Metadata — React Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the SEO metadata review panel from Streamlit into the existing React + FastAPI dashboard so users approve script and SEO in one place.

**Architecture:** Two new FastAPI endpoints expose SEO data (`GET`) and trigger Claude generation (`POST`). `SeoPanel.tsx` is a standalone component wired into the existing `ScriptReview.tsx` — it auto-fetches (or auto-generates) SEO when the script review expands, and passes the edited values to the updated `approveScript` call. The Streamlit file is deleted.

**Tech Stack:** Python 3.13 / FastAPI / SQLite / React 18 / TypeScript / Vite

---

## File Map

**Modified — backend:**
- `src/api/main.py` — add `GET /api/videos/{id}/seo`, `POST /api/videos/{id}/seo/generate`, extend `ApproveBody` with SEO fields

**Created — backend tests:**
- `tests/api/__init__.py` — empty, makes package
- `tests/api/test_seo_endpoints.py` — FastAPI TestClient tests for the two new endpoints

**Modified — frontend types + API:**
- `src/ui/src/lib/types.ts` — add `SeoMetadata`, add `seo_generated` to `PipelineStatus`
- `src/ui/src/lib/api.ts` — add `fetchSeo`, `generateSeo`, update `approveScript` signature

**Created — frontend component:**
- `src/ui/src/components/SeoPanel.tsx` — title / description / hashtags / thumbnail-phrase picker

**Modified — frontend wiring:**
- `src/ui/src/components/ScriptReview.tsx` — embed `SeoPanel`, auto-fetch/generate SEO on mount, pass SEO to approve

**Deleted — Streamlit:**
- `src/review/app.py`
- `src/review/__init__.py`

---

## Task 1: FastAPI SEO Endpoints

**Files:**
- Modify: `src/api/main.py`
- Create: `tests/api/__init__.py`
- Create: `tests/api/test_seo_endpoints.py`

### Background

`src/api/main.py` already has a `get_conn` import from `src.db.database` and a module-level `_SCRIPTS_DIR = project_root() / "data" / "scripts"`. The `get_conn()` function is a `@contextmanager` used as `with get_conn() as conn:`. Draft scripts are JSON files: `{hooks: [...], body: "...", cta: "..."}`. The `generate_and_enrich` function is at `src.seo.generate_and_enrich`.

- [ ] **Step 1: Create test package**

```bash
touch tests/api/__init__.py
```

- [ ] **Step 2: Write failing tests**

`tests/api/test_seo_endpoints.py`:

```python
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app, raise_server_exceptions=False)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE videos (
            video_id TEXT PRIMARY KEY,
            source_title TEXT,
            source_channel_name TEXT,
            status TEXT DEFAULT 'discovered',
            target_language TEXT,
            styles_json TEXT,
            script_word_count INTEGER,
            transcript_path TEXT,
            youtube_url TEXT,
            failure_reason TEXT,
            updated_at TEXT DEFAULT (datetime('now')),
            seo_title TEXT,
            seo_description TEXT,
            seo_hashtags_json TEXT,
            seo_thumbnail_phrases_json TEXT,
            seo_thumbnail_phrase TEXT,
            thumbnail_path TEXT
        )
    """)
    conn.execute("""
        INSERT INTO videos
            (video_id, source_title, target_language, styles_json, status)
        VALUES ('v1', 'Test Source', 'english', '["documentary"]', 'script_drafted')
    """)
    conn.commit()
    yield conn
    conn.close()


@contextmanager
def _conn_cm(conn):
    """Wrap a bare sqlite3 connection as a context manager for get_conn patching."""
    yield conn
    conn.commit()


def _patch_conn(db):
    return patch("src.api.main.get_conn", side_effect=lambda: _conn_cm(db))


# ── GET /api/videos/{video_id}/seo ───────────────────────────────────────────

def test_get_seo_returns_404_when_no_data(db):
    with _patch_conn(db):
        r = client.get("/api/videos/v1/seo")
    assert r.status_code == 404


def test_get_seo_returns_data_when_populated(db):
    db.execute("""
        UPDATE videos SET
            seo_title='Great Title',
            seo_description='A nice desc',
            seo_hashtags_json='["#one","#two"]',
            seo_thumbnail_phrases_json='["Phrase A","Phrase B","Phrase C"]',
            seo_thumbnail_phrase='Phrase A'
        WHERE video_id='v1'
    """)
    db.commit()

    with _patch_conn(db):
        r = client.get("/api/videos/v1/seo")

    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Great Title"
    assert body["hashtags"] == ["#one", "#two"]
    assert body["thumbnail_phrases"] == ["Phrase A", "Phrase B", "Phrase C"]
    assert body["thumbnail_phrase"] == "Phrase A"


# ── POST /api/videos/{video_id}/seo/generate ─────────────────────────────────

def test_generate_seo_returns_metadata(db, tmp_path):
    draft = {"hooks": ["Hook one"], "body": "Body text.", "cta": "Subscribe!"}
    (tmp_path / "v1_draft.json").write_text(json.dumps(draft), encoding="utf-8")

    from src.seo.models import SeoMetadata
    fake_meta = SeoMetadata(
        title="Generated Title",
        description="Generated description.",
        hashtags=["#foo", "#bar"],
        thumbnail_phrases=["Phrase 1", "Phrase 2", "Phrase 3"],
        niche="history",
    )

    with (
        patch("src.api.main._SCRIPTS_DIR", tmp_path),
        patch("src.seo.generate_and_enrich", return_value=fake_meta),
        _patch_conn(db),
    ):
        r = client.post("/api/videos/v1/seo/generate")

    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Generated Title"
    assert body["hashtags"] == ["#foo", "#bar"]
    assert body["thumbnail_phrase"] is None


def test_generate_seo_saves_to_db(db, tmp_path):
    draft = {"hooks": ["Hook"], "body": "Body.", "cta": "CTA."}
    (tmp_path / "v1_draft.json").write_text(json.dumps(draft), encoding="utf-8")

    from src.seo.models import SeoMetadata
    fake_meta = SeoMetadata(
        title="Saved Title",
        description="Saved desc.",
        hashtags=["#saved"],
        thumbnail_phrases=["Saved Phrase"],
        niche="tech",
    )

    with (
        patch("src.api.main._SCRIPTS_DIR", tmp_path),
        patch("src.seo.generate_and_enrich", return_value=fake_meta),
        _patch_conn(db),
    ):
        client.post("/api/videos/v1/seo/generate")

    row = db.execute(
        "SELECT seo_title, seo_hashtags_json FROM videos WHERE video_id='v1'"
    ).fetchone()
    assert row["seo_title"] == "Saved Title"
    assert json.loads(row["seo_hashtags_json"]) == ["#saved"]
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
python -m pytest tests/api/test_seo_endpoints.py -v
```

Expected: `ERRORS` or `FAILED` (endpoints don't exist yet).

- [ ] **Step 4: Add endpoints to `src/api/main.py`**

Open `src/api/main.py`. After the existing `ApproveBody` class, add an updated version and a new `ApproveBody` that includes SEO fields. Then add the two new endpoints.

**Replace the existing `ApproveBody` class** (currently `class ApproveBody(BaseModel): hook: str; body: str; cta: str`) with:

```python
class ApproveBody(BaseModel):
    hook: str
    body: str
    cta: str
    seo_title: str | None = None
    seo_description: str | None = None
    seo_hashtags: list[str] | None = None
    seo_thumbnail_phrases: list[str] | None = None
    seo_thumbnail_phrase: str | None = None
```

**Replace the existing `approve` handler** with one that also persists SEO fields:

```python
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
```

**Add two new endpoints** after the `approve` handler:

```python
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
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
python -m pytest tests/api/test_seo_endpoints.py -v
```

Expected: `4 passed`.

- [ ] **Step 6: Run full test suite — verify no regressions**

```bash
python -m pytest tests/ -v
```

Expected: `27 passed` (23 prior + 4 new).

- [ ] **Step 7: Commit**

```bash
git add src/api/main.py tests/api/__init__.py tests/api/test_seo_endpoints.py
git commit -m "feat(api): add GET/POST seo endpoints, extend approve with SEO fields"
```

---

## Task 2: Frontend Types and API Client

**Files:**
- Modify: `src/ui/src/lib/types.ts`
- Modify: `src/ui/src/lib/api.ts`

### Background

`types.ts` exports `PipelineStatus` (a union type) and various interfaces. `api.ts` exports `approveScript(videoId, hook, body, cta)`. TypeScript compile (`tsc`) is the test for this task — run it from `src/ui/`.

- [ ] **Step 1: Update `src/ui/src/lib/types.ts`**

Add `seo_generated` to the `PipelineStatus` union (currently `'discovered' | 'transcribed' | 'script_drafted' | 'script_approved' | 'video_rendered' | 'uploaded' | 'failed' | 'skipped'`):

```typescript
export type PipelineStatus =
  | 'discovered' | 'transcribed' | 'script_drafted'
  | 'script_approved' | 'seo_generated' | 'video_rendered' | 'uploaded'
  | 'failed' | 'skipped'
```

Add a new `SeoMetadata` interface **after** the existing `DraftScript` interface:

```typescript
export interface SeoMetadata {
  title: string
  description: string
  hashtags: string[]
  thumbnail_phrases: string[]
  thumbnail_phrase: string | null
}
```

- [ ] **Step 2: Update `src/ui/src/lib/api.ts`**

Add the import of `SeoMetadata` at the top of the import block:

```typescript
import type { Channel, Costs, DraftScript, PipelineEvent, SeoMetadata, Stats, Video, VideoStatus } from './types'
```

Add two new fetch functions after `fetchTranscript`:

```typescript
export async function fetchSeo(videoId: string): Promise<SeoMetadata> {
  const r = await fetch(`${BASE}/videos/${videoId}/seo`)
  if (!r.ok) throw new Error('No SEO data')
  return r.json()
}

export async function generateSeo(videoId: string): Promise<SeoMetadata> {
  const r = await post(`/videos/${videoId}/seo/generate`)
  if (!r.ok) {
    const text = await r.text().catch(() => '')
    throw new Error(`SEO generation failed: ${text.slice(0, 120)}`)
  }
  return r.json()
}
```

Replace the existing `approveScript` function with a version that accepts optional SEO data:

```typescript
export async function approveScript(
  videoId: string,
  hook: string,
  body: string,
  cta: string,
  seo?: SeoMetadata,
): Promise<void> {
  const r = await post(`/videos/${videoId}/approve`, {
    hook,
    body,
    cta,
    ...(seo
      ? {
          seo_title: seo.title,
          seo_description: seo.description,
          seo_hashtags: seo.hashtags,
          seo_thumbnail_phrases: seo.thumbnail_phrases,
          seo_thumbnail_phrase: seo.thumbnail_phrase,
        }
      : {}),
  })
  if (!r.ok) throw new Error('Approve failed')
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd src/ui && npx tsc --noEmit
```

Expected: no errors. Fix any that appear before moving on.

- [ ] **Step 4: Commit**

```bash
git add src/ui/src/lib/types.ts src/ui/src/lib/api.ts
git commit -m "feat(ui): add SeoMetadata type, fetchSeo, generateSeo, update approveScript"
```

---

## Task 3: SeoPanel Component

**Files:**
- Create: `src/ui/src/components/SeoPanel.tsx`

### Background

Look at `ScriptReview.tsx` for the established inline-style patterns: `label` and `inputBase` style objects, `var(--c-*)` CSS variables (gold, border, surface, text, red, green, muted), `var(--font-mono)` / `var(--font-sans)`. Follow those patterns exactly — no Tailwind, no CSS modules.

The panel receives a `SeoMetadata` value plus callbacks. It owns no state of its own.

- [ ] **Step 1: Create `src/ui/src/components/SeoPanel.tsx`**

```tsx
import type { SeoMetadata } from '../lib/types'

const label: React.CSSProperties = {
  fontFamily: 'var(--font-mono)',
  fontSize: '0.6rem',
  color: 'var(--c-muted)',
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  display: 'block',
  marginBottom: 7,
}

const inputBase: React.CSSProperties = {
  width: '100%',
  background: 'var(--c-surface)',
  border: '1px solid var(--c-border)',
  borderRadius: 5,
  color: 'var(--c-text)',
  fontFamily: 'var(--font-sans)',
  fontSize: '0.85rem',
  lineHeight: 1.65,
  padding: '9px 12px',
  boxSizing: 'border-box',
}

export function SeoPanel({
  seo,
  onChange,
  onRegenerate,
  regenerating,
}: {
  seo: SeoMetadata
  onChange: (updated: SeoMetadata) => void
  onRegenerate: () => void
  regenerating: boolean
}) {
  const titleLen = seo.title.length
  const titleOk = titleLen <= 60

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>

      {/* Section header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--c-border-sub)', paddingTop: 14 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--c-muted)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>
          SEO Metadata
        </span>
        <button
          onClick={onRegenerate}
          disabled={regenerating}
          style={{
            background: 'none',
            border: '1px solid var(--c-border)',
            borderRadius: 4,
            color: 'var(--c-text2)',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.6rem',
            letterSpacing: '0.06em',
            padding: '4px 10px',
            cursor: regenerating ? 'not-allowed' : 'pointer',
            opacity: regenerating ? 0.6 : 1,
          }}
        >
          {regenerating ? '↺ Working…' : '↺ Regenerate'}
        </button>
      </div>

      {/* Title */}
      <div>
        <span style={label}>
          Title{' '}
          <span style={{ color: titleOk ? 'var(--c-green)' : 'var(--c-red)' }}>
            {titleLen}/60
          </span>
        </span>
        <input
          value={seo.title}
          onChange={(e) => onChange({ ...seo, title: e.target.value })}
          style={{ ...inputBase, borderColor: titleOk ? 'var(--c-border)' : 'var(--c-red)' }}
        />
      </div>

      {/* Description */}
      <div>
        <span style={label}>Description</span>
        <textarea
          value={seo.description}
          onChange={(e) => onChange({ ...seo, description: e.target.value })}
          rows={5}
          style={{ ...inputBase, resize: 'vertical' }}
        />
      </div>

      {/* Hashtags */}
      <div>
        <span style={label}>Hashtags — one per line</span>
        <textarea
          value={seo.hashtags.join('\n')}
          onChange={(e) =>
            onChange({
              ...seo,
              hashtags: e.target.value.split('\n').map((t) => t.trim()).filter(Boolean),
            })
          }
          rows={6}
          style={{
            ...inputBase,
            resize: 'vertical',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.75rem',
          }}
        />
      </div>

      {/* Thumbnail phrase */}
      {seo.thumbnail_phrases.length > 0 && (
        <div>
          <span style={label}>Thumbnail phrase</span>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {seo.thumbnail_phrases.map((phrase) => (
              <label
                key={phrase}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  cursor: 'pointer',
                  padding: '8px 10px',
                  borderRadius: 5,
                  background: seo.thumbnail_phrase === phrase ? 'var(--c-gold-bg)' : 'var(--c-surface)',
                  border: `1.5px solid ${seo.thumbnail_phrase === phrase ? 'var(--c-gold)' : 'var(--c-border)'}`,
                  transition: 'all 0.15s',
                }}
              >
                <input
                  type="radio"
                  name={`thumbnail_phrase_${seo.thumbnail_phrases.join('')}`}
                  value={phrase}
                  checked={seo.thumbnail_phrase === phrase}
                  onChange={() => onChange({ ...seo, thumbnail_phrase: phrase })}
                  style={{ accentColor: 'var(--c-gold)', flexShrink: 0 }}
                />
                <span style={{ fontFamily: 'var(--font-sans)', fontSize: '0.82rem', color: 'var(--c-text)' }}>
                  {phrase}
                </span>
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd src/ui && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add src/ui/src/components/SeoPanel.tsx
git commit -m "feat(ui): add SeoPanel component with title/desc/hashtags/thumbnail-phrase"
```

---

## Task 4: Wire SeoPanel into ScriptReview

**Files:**
- Modify: `src/ui/src/components/ScriptReview.tsx`

### Background

`ScriptReview.tsx` currently imports `approveScript`, `fetchScript`, `fetchTranscript`, `regenerateScript` from `../lib/api` and `DraftScript` from `../lib/types`. It manages state for the script fields and has a single `handleApprove` call. The SEO panel needs to sit between the CTA field and the approve/regenerate footer row.

**UX flow:**
1. Component mounts → fetches script AND tries to `fetchSeo`
2. If SEO exists in DB → populate panel immediately
3. If SEO 404 → call `generateSeo` and show spinner until it completes
4. If `generateSeo` also fails → show "Generate SEO" button (no spinner, no panel)
5. User edits script + SEO → clicks "APPROVE & RUN" → both are sent together

- [ ] **Step 1: Update imports at the top of `ScriptReview.tsx`**

Replace the existing import lines:

```tsx
import { useEffect, useState } from 'react'
import { approveScript, fetchScript, fetchTranscript, generateSeo, fetchSeo, regenerateScript } from '../lib/api'
import type { DraftScript, SeoMetadata } from '../lib/types'
import { SeoPanel } from './SeoPanel'
```

- [ ] **Step 2: Add SEO state variables after the existing state declarations**

After the line `const [transcriptLoading, setTranscriptLoading] = useState(false)`, add:

```tsx
const [seo, setSeo] = useState<SeoMetadata | null>(null)
const [seoLoading, setSeoLoading] = useState(false)
const [seoRegenerating, setSeoRegenerating] = useState(false)
const [seoFailed, setSeoFailed] = useState(false)
```

- [ ] **Step 3: Replace the existing `useEffect` with one that also loads SEO**

Replace the entire `useEffect` block (the one that calls `fetchScript`) with:

```tsx
useEffect(() => {
  setLoading(true)
  setSeo(null)
  setSeoLoading(true)
  setSeoFailed(false)

  fetchScript(videoId)
    .then((d) => {
      setDraft(d)
      setBody(d.body)
      setCta(d.cta)
      setLoading(false)
    })
    .catch(() => setLoading(false))

  fetchSeo(videoId)
    .then((data) => {
      setSeo(data)
      setSeoLoading(false)
    })
    .catch(() => {
      // No SEO stored yet — auto-generate
      generateSeo(videoId)
        .then((data) => {
          setSeo(data)
          setSeoLoading(false)
        })
        .catch(() => {
          setSeoLoading(false)
          setSeoFailed(true)
        })
    })
}, [videoId])
```

- [ ] **Step 4: Add `handleRegenerateSeo` handler after `handleToggleTranscript`**

```tsx
const handleRegenerateSeo = async () => {
  setSeoRegenerating(true)
  setSeoFailed(false)
  try {
    const data = await generateSeo(videoId)
    setSeo(data)
  } catch {
    setSeoFailed(true)
  } finally {
    setSeoRegenerating(false)
  }
}
```

- [ ] **Step 5: Update `handleApprove` to include SEO data**

Replace the existing `handleApprove`:

```tsx
const handleApprove = async () => {
  setSubmitting(true)
  try {
    await approveScript(videoId, draft.hooks[hookIdx], body, cta, seo ?? undefined)
    onApproved()
  } catch {
    setSubmitting(false)
  }
}
```

- [ ] **Step 6: Insert the SEO panel between the CTA div and the footer div**

After the closing `</div>` of the CTA section and **before** the footer `<div>` that contains the word-count span and buttons, insert:

```tsx
{/* SEO panel */}
{seoLoading && (
  <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'var(--c-muted)' }}>
    Generating SEO…
  </p>
)}
{seoFailed && !seoLoading && (
  <div style={{ borderTop: '1px solid var(--c-border-sub)', paddingTop: 14 }}>
    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--c-muted)', letterSpacing: '0.12em', textTransform: 'uppercase', display: 'block', marginBottom: 8 }}>
      SEO Metadata
    </span>
    <button
      onClick={handleRegenerateSeo}
      style={{
        background: 'none',
        border: '1px solid var(--c-border)',
        borderRadius: 4,
        color: 'var(--c-text2)',
        fontFamily: 'var(--font-mono)',
        fontSize: '0.6rem',
        letterSpacing: '0.06em',
        padding: '6px 12px',
        cursor: 'pointer',
      }}
    >
      Generate SEO
    </button>
  </div>
)}
{seo && !seoLoading && (
  <SeoPanel
    seo={seo}
    onChange={setSeo}
    onRegenerate={handleRegenerateSeo}
    regenerating={seoRegenerating}
  />
)}
```

- [ ] **Step 7: Verify TypeScript compiles**

```bash
cd src/ui && npx tsc --noEmit
```

Expected: no errors. Fix any that appear.

- [ ] **Step 8: Start the dev server and verify visually**

```bash
# Terminal 1 — FastAPI backend
python -m uvicorn src.api.main:app --reload --port 8000

# Terminal 2 — Vite dev server
cd src/ui && npm run dev
```

Open http://localhost:5173. Find a video in `script_drafted` status, expand it, and verify:
- Script panel loads (hooks, body, CTA)
- "Generating SEO…" appears while the Claude call runs
- SEO panel populates with title, description, hashtags, thumbnail phrases
- Title char counter turns red when >60 chars
- Approve & Run button sends both script and SEO data (check backend logs)

- [ ] **Step 9: Commit**

```bash
git add src/ui/src/components/ScriptReview.tsx
git commit -m "feat(ui): embed SeoPanel in ScriptReview with auto-generate on mount"
```

---

## Task 5: Remove Streamlit

**Files:**
- Delete: `src/review/app.py`
- Delete: `src/review/__init__.py`

### Background

`src/review/` was the Streamlit implementation built before the React dashboard existed. It is now fully superseded by `ScriptReview.tsx` + `SeoPanel.tsx`. The `src/review/__init__.py` is an empty package marker. No other file in the codebase imports from `src.review`.

- [ ] **Step 1: Confirm nothing imports from `src.review`**

```bash
grep -r "from src.review" src/ --include="*.py"
grep -r "import src.review" src/ --include="*.py"
```

Expected: no output (zero matches).

- [ ] **Step 2: Delete the files**

```bash
rm src/review/app.py src/review/__init__.py
```

- [ ] **Step 3: Run full test suite — verify no regressions**

```bash
python -m pytest tests/ -v
```

Expected: `27 passed`.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove Streamlit review app (replaced by React SeoPanel)"
```

---

## Self-Review

**Spec coverage:**
- ✅ SEO metadata editable in React (title, description, hashtags, thumbnail phrase)
- ✅ Title char counter (red >60)
- ✅ Independent Regenerate SEO button
- ✅ Auto-generates SEO when script review opens and no SEO exists
- ✅ Approve & Render writes SEO to DB alongside script approval
- ✅ GET /api/videos/{id}/seo endpoint
- ✅ POST /api/videos/{id}/seo/generate endpoint
- ✅ Streamlit deleted
- ✅ All FastAPI endpoint tests

**Placeholder scan:** None found.

**Type consistency:**
- `SeoMetadata` defined in `types.ts` — used in `api.ts`, `SeoPanel.tsx`, `ScriptReview.tsx` ✅
- `fetchSeo`/`generateSeo` return `Promise<SeoMetadata>` ✅
- `approveScript` 5th param is `seo?: SeoMetadata` ✅
- `SeoPanel` receives `seo: SeoMetadata` ✅
