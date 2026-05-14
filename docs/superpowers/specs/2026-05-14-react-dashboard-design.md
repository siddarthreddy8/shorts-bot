# Shorts-Bot React Dashboard — Design Spec
_2026-05-14_

## Overview

Replace the Streamlit review UI with a React + FastAPI dashboard. Script approval is the single human gate; everything after (storyboard → render → upload) fires automatically in the background. The UI shows live step-by-step progress.

---

## Architecture

- **Frontend:** React 18 + Vite, port 5173 in dev. Built bundle served by FastAPI in production.
- **Backend:** FastAPI (Python), port 8000. Thin wrapper over existing pipeline functions.
- **Background tasks:** FastAPI `BackgroundTasks` — approve fires storyboard → render → upload sequentially in a background thread.
- **Live updates:** React polls `GET /api/videos/{id}/status` every 2s for in-progress cards, every 5s for the full queue refresh.
- **Startup:** Single `start_ui.sh` / `start_ui.bat` script launching both processes. Production: `uvicorn` only (serves built frontend).

---

## Backend — API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/videos` | All videos newest-first. `{id, title, channel, status, updated_at, youtube_url}` |
| GET | `/api/videos/{id}/script` | Draft JSON for inline review. `{hooks, body, cta, word_count, language, styles}` |
| POST | `/api/videos/{id}/approve` | Body: `{hook, body, cta}`. Saves approved.txt, fires background pipeline. Returns 202. |
| GET | `/api/videos/{id}/status` | `{status, steps: [{name, state, error}]}`. Steps: Storyboard / Render / Upload. States: pending / running / done / failed |
| GET | `/api/videos/{id}/preview` | Serves rendered MP4 (only when status = video_rendered or uploaded) |

Background pipeline order: `build_storyboard()` → `render()` → `upload()`. Errors are caught per-step; failed step sets state=failed and stops the chain.

---

## Frontend — Components

### Layout
Single-page app. Fixed header, scrollable queue below.

### Header
- App name: `SHORTS BOT`
- Right side: count of videos needing review today

### VideoCard (three states)

**State 1 — Needs Review** (`status = script_drafted`)
- Red status badge
- Click anywhere on card → inline expansion
- Expansion shows:
  - Hook selector: 3 cards side by side, radio selection, selected card has gold border + glow
  - Body textarea (editable)
  - CTA text input (editable)
  - Live word count with green ✓ / red ✗ (target 90–180)
  - Full-width gold `APPROVE & RUN` button
- Approve fires `POST /api/videos/{id}/approve` → card transitions to State 2

**State 2 — In Pipeline** (`status = script_approved | video_rendered`)
- Blue status badge showing current stage name
- Step tracker: `Storyboard ✓ → Render ⟳ → Upload ○`
  - Done: solid gold pill
  - Running: gold pill with pulse animation
  - Pending: dim grey pill
- Polls status every 2s; transitions to State 3 on upload complete

**State 3 — Done** (`status = uploaded | failed`)
- Green badge (or red for failed)
- YouTube link (uploaded)
- Inline `<video>` preview player (calls `/api/videos/{id}/preview`)
- Failed: error message from the step that failed

---

## Visual Design

- **Background:** `#080c18`
- **Card background:** `#0f1420`, border `1px solid #1e2a45`
- **Accent:** `#ffd93d` (gold — matches video caption color)
- **Status colors:** gold = needs review, `#3b82f6` = running, `#22c55e` = uploaded, `#ef4444` = failed
- **Fonts:** JetBrains Mono (status/IDs/timestamps), Inter (body text)
- **Hook cards:** 3-column grid, selected lifts with gold border + box shadow
- **Approve button:** full-width, `#ffd93d` background, `#000` text, no border radius
- **Step tracker:** horizontal pill chain
- **Motion:** card expand/collapse spring animation; step tracker pulse on running state; approve button press scale

---

## File Structure

```
src/
  api/
    main.py          ← FastAPI app, all endpoints
    pipeline.py      ← background task orchestrator
  ui/
    package.json
    vite.config.ts
    index.html
    src/
      main.tsx
      App.tsx
      components/
        VideoQueue.tsx
        VideoCard.tsx
        ScriptReview.tsx
        StepTracker.tsx
        StatusBadge.tsx
      hooks/
        useVideos.ts
        useVideoStatus.ts
      lib/
        api.ts         ← typed fetch wrappers
        types.ts
start_ui.sh
start_ui.bat
```

---

## Out of Scope

- Authentication (personal tool)
- Pagination (queue is small)
- The old Streamlit pages (kept on disk, not deleted)
- Manual storyboard prompt editing (removed — pipeline is fully automatic post-approval)
