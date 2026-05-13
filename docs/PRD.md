# Product Requirements Document (PRD)
## Telugu → Hindi/English YouTube Shorts Automation Bot

**Version:** 0.1 (MVP)
**Date:** 2026-05-11
**Owner:** sidr3d@gmail.com
**Status:** Draft
**Use case:** Personal tool (not SaaS, single operator, no multi-user concerns)

> ## ⚠️ Non-Negotiable: Videos must be watchable
> Quality of the output Short is the hard constraint. If a tooling or cadence choice cannot meet a "watchable" bar (smooth animations, natural TTS, visuals match script, professional polish), **drop the cadence** — do not ship lower quality. A manual visual-review gate sits before upload; the operator can reject any render.

---

## 1. Overview & Problem Statement

### Problem
High-quality Telugu YouTube content has limited reach because it isn't easily discoverable by Hindi/English speakers. Manually translating, re-scripting, and reproducing videos in another language is slow and expensive. Existing reupload tools only translate — they don't restyle content (e.g., make it comedic or documentary-style) and they don't repackage long-form videos into short-form (Shorts) optimized for discovery.

### Solution
An automated daily pipeline that:
1. Monitors 2 fixed Telugu YouTube channels (plus optional ad-hoc URL input)
2. Detects the latest video
3. Transcribes the Telugu audio
4. Rewrites it as a short-form script in **Hindi or English**, in one or more user-selected styles (comedy, documentary, serious, etc.) — plagiarism-safe
5. Lets the user review & edit the script
6. Generates a **Hoog-style faceless 3D-motion-graphics Short** using Remotion templates (TTS voiceover + animated maps/scenes/text + captions)
7. Uploads to the user's destination YouTube channel with a link back to the original long-form video in the description

### Reference Aesthetic
**[Hoog](https://www.youtube.com/channel/UCii9ezsUa_mBiSdw0PtSOaw)** — Dutch creator known for faceless 3D-animated documentary essays (same family as Fern & Imperial). For MVP, we target ~60% visual fidelity to this style using programmatic motion graphics (Remotion) — daily cadence over perfect fidelity. Phase 2 may upgrade to Blender-rendered scenes.

### Strategic Goal
Build a Shorts-led growth funnel: viewers discover via Shorts → click through to the original long-form video → subscribe.

---

## 2. Goals & Success Metrics

### North-Star Metric
**% of Shorts viewers who click through to the linked long-form video** (referral rate).

### Supporting Metrics (Input)
- Daily Shorts published (target: 1–2/day)
- Average Short watch-time retention (target: > 65%)
- Subscriber growth on destination channel (week-over-week)
- Cost per Short (target: < $0.50 in MVP)

### Non-Goals
- Replacing the original creators
- Long-form video generation (out of scope for MVP)
- Real-time / live-stream content
- Multilingual output beyond Hindi/English in MVP

---

## 3. Target Users

### Primary User: Channel Operator (You)
- Indian content creator / aspiring channel owner
- Comfortable with light technical setup (running scripts, reviewing output)
- Wants automated daily content with minimal manual effort
- Reviews & edits scripts before publishing for quality control

### Secondary User: End Viewer
- Hindi or English speaker on YouTube Shorts
- Interested in topics covered by the Telugu source channels
- Discovers content via Shorts, may convert to subscriber

---

## 4. Functional Requirements

### F1. Source Monitoring
- F1.1 Poll 2 configured Telugu YouTube channel IDs daily
- F1.2 Accept optional ad-hoc YouTube video URL input
- F1.3 Detect the **latest unprocessed** video (dedup by video ID stored in local DB / JSON)
- F1.4 Skip videos that fail copyright/age restriction checks

### F2. Transcription
- F2.1 Download audio via `yt-dlp` (audio-only, lowest acceptable bitrate)
- F2.2 Transcribe Telugu using local **Whisper large-v3** model
- F2.3 Save raw Telugu transcript to `data/transcripts/`

### F3. Script Generation
- F3.1 User selects **output language**: Hindi or English
- F3.2 User selects **one or more styles**: Stand-up Comedy, Serious, Documentary, Storytelling, Explainer, Sarcastic (extensible list)
- F3.3 Translate Telugu transcript → target language using Claude API
- F3.4 Rewrite into a **30–60 second Shorts script** (plagiarism-safe, original phrasing) in the selected style(s)
- F3.5 Generate 2–3 hook variations and let user pick
- F3.6 Append a clear CTA at the end: "Watch the full video — link in description"

### F4. Human Review
- F4.1 Local web UI (Streamlit) displays:
  - Original transcript (collapsed)
  - Generated script with hook variations
  - Style tags and language
- F4.2 User can edit the script inline
- F4.3 User clicks **Approve** to proceed, or **Regenerate** for a new draft

### F5. Video Generation (Hoog-style Motion Graphics via Remotion)
- F5.1 Generate TTS voiceover from approved script (ElevenLabs, Hindi/English voice)
- F5.2 **Remotion (React-based) project** with a library of templates that emulate Hoog aesthetic:
  - Animated 3D-style maps & globe rotations (via `react-simple-maps` + GSAP/Framer Motion)
  - Isometric scene templates with smooth camera moves
  - Animated typography overlays (bold sans-serif, white-on-dark, Hoog-inspired)
  - Atmospheric color grading (deep blues, warm oranges) via CSS filters/LUTs
- F5.3 Pipeline picks the best-matching template based on script topic (map shot for geo content, isometric for tech, etc.)
- F5.4 Compose vertical 9:16 video (1080×1920) — Remotion CLI renders to MP4
- F5.5 Auto-generated captions synced to TTS word-level timing (use ElevenLabs alignment API or `whisper-timestamped` on the TTS output)
- F5.6 Intro/outro template: channel logo + subscribe nudge with Hoog-style transition
- F5.7 Output: `data/videos/{video_id}_{timestamp}.mp4`

### F5-alt. Stock B-roll Fallback (Phase 0 / fallback only)
If no matching motion-graphics template fits the script topic, fall back to Pexels/Pixabay stock footage + Ken Burns pans + captions. Marked clearly in logs so the user can review and improve template library.

### F6. Upload
- F6.1 Authenticate to user's YouTube channel via OAuth 2.0
- F6.2 Upload as Short (vertical, < 60s)
- F6.3 Auto-generate SEO title (≤ 60 chars), description (with link to original long-form), tags
- F6.4 Set visibility (default: Public; user can override to Private/Unlisted)
- F6.5 **Visual quality gate** — operator previews the rendered MP4 in the review UI and explicitly clicks "Publish". No video uploads without this manual approval. Reject button discards the render.

### F7. Scheduling
- F7.1 Daily run at a configurable time (default: 09:00 local)
- F7.2 Windows Task Scheduler (MVP) → APScheduler / cron when deployed to cloud
- F7.3 On failure: log error, send email/desktop notification, do not retry blindly
- F7.4 Manual trigger via CLI: `python main.py --run-now [--url <video_url>]`

---

## 5. User Flow (Happy Path)

```
[09:00 Daily Scheduler fires]
        ↓
[Monitor: poll 2 channels → find new video]
        ↓
[Transcribe Telugu audio → save transcript]
        ↓
[Notify user: "New video ready — pick styles & language"]
        ↓
[User opens local UI → selects English + Documentary+Comedy]
        ↓
[Translate + rewrite into Shorts script with 3 hook options]
        ↓
[User reviews → edits a line → picks hook #2 → Approve]
        ↓
[TTS voiceover + B-roll + captions → MP4 generated]
        ↓
[Upload to YouTube Shorts with description linking original]
        ↓
[Log success, store metadata for analytics]
```

---

## 6. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | End-to-end run ≤ 15 min per video (excluding human review) |
| **Cost** | < $0.50 per Short in MVP (Whisper local; Claude + ElevenLabs API) |
| **Reliability** | If any stage fails, halt pipeline and notify user — never publish broken content |
| **Privacy** | API keys in `.env` (gitignored). No PII stored. |
| **Portability** | Runs on Windows 11 locally; containerizable for cloud (Docker phase 2) |
| **Stack** | **Python** (orchestration, monitoring, transcription, translation, upload) + **Node.js/React** (Remotion video gen). Bridged via subprocess / file-based handoff. |
| **Compliance** | Description must credit original creator + link to source. Respect YouTube ToS on reuse. |

---

## 7. Out of Scope (MVP)

- Anaya avatar / HeyGen video generation (phase 2)
- **Full Blender 3D pipeline** (phase 2 — for matching Hoog at 80%+ fidelity)
- AI 3D video generators (Runway Gen-4, Sora) — phase 2 evaluation
- Long-form (>60s) video output
- Multi-channel destination (only 1 output channel)
- **SaaS / multi-user version** — this is a personal tool, no public productization
- Mobile app
- Languages beyond Hindi & English
- Public dashboard / sharing of analytics
- Privacy policy, ToS, user authentication beyond what YouTube/API keys require

---

## 8. Open Questions & Risks (preview — full list in `RISKS.md`)

- **Copyright:** YouTube ToS on transformative reuse — need a clear "credit + link" pattern and possibly explicit creator permission
- **Translation quality:** Telugu idioms may not translate cleanly — need glossary / human override
- **Whisper accuracy on Telugu:** large-v3 supports Telugu but accuracy varies by accent/audio quality
- **API costs:** ElevenLabs + Claude usage at scale needs monitoring
- **YouTube upload quotas:** Data API v3 has 10,000 unit/day quota — each upload costs ~1,600 units

---

## 9. Release Plan

| Phase | Scope | Target |
|---|---|---|
| **MVP (Local)** | Remotion motion-graphics pipeline at ~60% Hoog fidelity, daily Shorts, local Windows | Week 4 |
| **Phase 2** | Blender 3D pipeline (~80% Hoog fidelity), cloud server deployment for unattended daily runs | Week 8 |
| **Phase 3** | A/B test styles automatically, personal metrics tracking, expand to more source channels | Week 12 |
