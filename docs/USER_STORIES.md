# User Stories
## Telugu → Hindi/English Shorts Bot (Personal Use)

**Date:** 2026-05-11
**Framework:** `user-stories` (INVEST-compliant) + `test-scenarios`
**User:** Channel Operator (you) — the only user

---

## Epic 1: Daily Content Sourcing

### US-1.1 — Auto-detect latest video
**As** the operator, **I want** the bot to check 2 fixed Telugu channels daily and find any new video, **so that** I never miss content to repurpose.

**Acceptance Criteria:**
- Bot polls both channels via YouTube Data API at scheduled time
- Detects videos published since last successful run
- Skips videos already processed (dedup by `video_id`)
- Logs each check with timestamp + result
- Stores last-processed video ID per channel in local SQLite

**Test Scenarios:**
- Happy: Both channels have new videos → both queued
- Edge: Neither channel has new content → log "nothing to do", exit gracefully
- Edge: One channel returns API error → process the other, alert me about the failure
- Edge: Source channel deleted/private → log error, mark channel as inactive

---

### US-1.2 — Ad-hoc URL processing
**As** the operator, **I want** to process a specific YouTube URL on demand, **so that** I can experiment with one-off videos outside my 2 fixed channels.

**Acceptance Criteria:**
- CLI: `python main.py --url <youtube_video_url>`
- Bypasses channel monitoring, jumps straight to transcription
- Same downstream flow as scheduled videos

**Test Scenarios:**
- Happy: Valid URL → processes
- Edge: Invalid URL → clear error, no crash
- Edge: Private/age-restricted video → graceful failure with explanation

---

## Epic 2: Transcription

### US-2.1 — Telugu audio transcription
**As** the operator, **I want** the bot to transcribe the Telugu audio of a source video accurately, **so that** the downstream rewrite has good source material.

**Acceptance Criteria:**
- Audio downloaded via `yt-dlp` (audio-only, mp3)
- Transcribed using Whisper large-v3
- Output saved as `data/transcripts/{video_id}.txt` (plain text) and `.json` (with timestamps)
- Logs transcription duration and word count

**Test Scenarios:**
- Happy: Clean audio → accurate Telugu transcript
- Edge: Music-heavy video → log warning about poor transcription quality
- Edge: 30-min video → completes within reasonable time on local GPU
- Edge: No GPU available → falls back to medium model, log the downgrade

---

## Epic 3: Script Generation

### US-3.1 — Choose language and styles
**As** the operator, **I want** to pick the output language (Hindi or English) and one or more styles per video, **so that** each Short matches the topic and my mood.

**Acceptance Criteria:**
- Review UI shows language toggle + style multi-select (comedy, serious, documentary, storytelling, explainer, sarcastic)
- Multiple styles can combine (e.g. "documentary + comedy")
- Default styles can be set in `config.yaml`

---

### US-3.2 — Generate plagiarism-safe Shorts script
**As** the operator, **I want** the bot to rewrite the Telugu transcript into a 30–60 second Shorts script in my chosen language and style(s), **so that** the output is original and avoids copyright issues.

**Acceptance Criteria:**
- Output script targets 90–180 words (matches ~30–60s TTS)
- 2–3 alternative hooks provided
- Includes a clear CTA at the end: "Watch the full video — link in description"
- Plagiarism check: rewrite shares < 30% n-gram overlap with raw translated transcript

**Test Scenarios:**
- Happy: Tech topic in English+Documentary style → coherent, structured script
- Happy: Same source, comedy style → distinctly different tone
- Edge: Source has technical jargon → bot defines terms in the script
- Edge: Multiple styles combined → output blends them gracefully (not jumbled)

---

## Epic 4: Human Review

### US-4.1 — Review and edit the script
**As** the operator, **I want** a local UI where I can read and edit the generated script before video creation, **so that** I never publish embarrassing or wrong content.

**Acceptance Criteria:**
- Streamlit UI shows: source video metadata, generated script, hook options
- Editable text area; changes save on click of "Approve"
- "Regenerate" button creates a fresh draft
- "Reject" button discards and logs reason

**Test Scenarios:**
- Happy: I tweak 2 lines → save → proceed to video gen
- Edge: I reject 3 times → bot suggests I check style settings
- Edge: I close the browser without approving → script stays in "pending review" state

---

## Epic 5: Video Generation

### US-5.1 — Generate Hoog-style Short
**As** the operator, **I want** a vertical 1080×1920 motion-graphics video generated from my approved script, **so that** it's ready to upload without manual editing.

**Acceptance Criteria:**
- TTS voiceover generated (ElevenLabs, Hindi or English voice)
- Remotion picks a template matching the topic (map/isometric/abstract/etc.)
- Word-level captions burned in
- Channel intro + outro applied
- Output: `data/videos/{video_id}_{timestamp}.mp4` ≤ 60s, 9:16, 1080×1920

**Test Scenarios:**
- Happy: 45s script → 45s video produced
- Edge: Script too long for 60s → bot trims or alerts before render
- Edge: Template render fails → fall back to stock B-roll template, log it

---

## Epic 6: Upload

### US-6.1 — Auto-upload to my YouTube channel
**As** the operator, **I want** the generated Short uploaded directly to my channel with proper metadata, **so that** I don't manually upload daily.

**Acceptance Criteria:**
- Uploaded via YouTube Data API v3 (OAuth-authenticated)
- Title: ≤ 60 chars, hook-based
- Description: 1-line summary + credit to source channel + UTM-tagged link to original long-form + my channel link
- Tags: topic-based (extracted from script keywords)
- Visibility: configurable; default Public for daily runs

**Test Scenarios:**
- Happy: Upload succeeds → log video ID + URL
- Edge: API quota exceeded → defer, alert me
- Edge: Upload fails after retry → mark video as "ready to upload", show in next run

---

## Epic 7: Scheduling & Operations

### US-7.1 — Daily automated run
**As** the operator, **I want** the bot to run automatically every morning, **so that** my channel keeps shipping without manual triggering.

**Acceptance Criteria:**
- Configurable run time (default 09:00 local)
- Windows Task Scheduler entry on initial setup
- After scheduled run completes through transcription + script gen, send me a desktop notification: "Script ready for review"
- After my approval, video gen + upload run automatically

---

### US-7.2 — Failure notifications
**As** the operator, **I want** to be notified when anything fails, **so that** I can intervene before missing a day.

**Acceptance Criteria:**
- On error in any pipeline stage: log to `logs/error.log` with stacktrace
- Send desktop notification + optional email
- Pipeline halts at failure — never publishes broken content
- Includes a single-command retry option: `python main.py --resume {video_id}`

---

### US-7.3 — Track metrics
**As** the operator, **I want** per-Short metrics logged locally, **so that** I can see what's working over time (see METRICS.md).

**Acceptance Criteria:**
- SQLite DB tracks: video_id, source_channel, language, styles[], script_length, edit_distance, render_time, upload_time, youtube_id
- Weekly export script generates a CSV for analysis
- Optionally pulls YouTube Analytics data via API for views/retention
