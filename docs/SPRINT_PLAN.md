# Sprint Plan
## Telugu → Hindi/English Shorts Bot — 4-Week MVP

**Date:** 2026-05-11
**Framework:** `sprint-plan`
**Cadence:** 4 weekly sprints, capacity = solo dev, evenings/weekends (~15 hrs/week)
**MVP target:** Week 4 — daily Shorts publishing locally

---

## Sprint 0 — Pre-Build Validation (1–2 days, BEFORE sprint 1)

**Goal:** De-risk top 5 assumptions from RISKS.md before writing meaningful code.

| # | Task | Owner | Output |
|---|---|---|---|
| 0.1 | Get permission from 2 source channel creators (email/comment) | You | Written reply (screenshot) |
| 0.2 | Run Whisper large-v3 on 1 sample Telugu video | Claude+You | Transcript quality assessment |
| 0.3 | Generate 1 ElevenLabs Hindi voiceover sample (30s) | You | MP3 file, listen test |
| 0.4 | Build 1 Remotion template POC (Hoog-style animated map) | Claude+You | Sample MP4 rendered |
| 0.5 | Run 1 Claude rewrite + check for plagiarism | Claude+You | Sample script + Copyscape report |

**Gate:** If 3+ of these fail, revise plan before Sprint 1.

---

## Sprint 1 — Foundation (Week 1)

**Goal:** Project scaffolded, channel monitoring + transcription working end-to-end on CLI.

| Story | Tasks | Hours |
|---|---|---|
| Project setup | Repo, virtualenv, `.env`, requirements.txt, logging, SQLite schema | 3 |
| US-1.1 — Channel monitor | YouTube Data API auth, channel poll, dedup logic, SQLite store | 4 |
| US-1.2 — Ad-hoc URL | CLI flag, URL validator, route to transcription | 1 |
| US-2.1 — Transcription | yt-dlp audio download, Whisper large-v3 wrapper, save transcript JSON | 5 |
| **Demo** | `python main.py --url <telugu_video>` → produces transcript file | — |

**Definition of Done:**
- Can run pipeline through transcription on any Telugu URL
- Logs are clean, errors handled
- Code committed to local git

---

## Sprint 2 — Script Generation (Week 2)

**Goal:** Transcripts → polished Hindi/English Shorts scripts with style selection.

| Story | Tasks | Hours |
|---|---|---|
| US-3.1 — Lang + style picker | Config schema, CLI flags, defaults | 1 |
| US-3.2 — Generate script | Claude API integration, prompt engineering for style+plagiarism-safety, 3 hook variations, CTA injection | 6 |
| Plagiarism guard | n-gram overlap check vs source transcript, regenerate if > 30% | 2 |
| Style library | YAML file with style prompts (comedy/documentary/etc.) | 2 |
| **Demo** | CLI produces a polished 45s script with 3 hooks in chosen style | — |

**Definition of Done:**
- 5 sample scripts pass plagiarism check
- Style differences are clearly distinguishable
- Edit-distance tracking implemented

---

## Sprint 3 — Review UI + Video Generation (Week 3)

**Goal:** Streamlit review UI working, Remotion produces a Hoog-style Short end-to-end.

| Story | Tasks | Hours |
|---|---|---|
| US-4.1 — Review UI | Streamlit app: list pending scripts, edit, approve/reject/regenerate | 4 |
| TTS integration | ElevenLabs API wrapper, voice config per language | 2 |
| US-5.1 — Remotion templates | 3 starter templates (map shot, isometric scene, abstract typography), word-level caption sync | 6 |
| Python↔Remotion bridge | Subprocess call to Remotion CLI, JSON payload | 2 |
| **Demo** | Approve a script → final MP4 lands in `data/videos/` | — |

**Definition of Done:**
- Full pipeline from URL → reviewable script → final Short MP4
- Visual quality acceptable (you'd post it)
- One full manual end-to-end run completed

---

## Sprint 4 — Upload + Schedule + Polish (Week 4)

**Goal:** Daily automated runs uploading to YouTube.

| Story | Tasks | Hours |
|---|---|---|
| US-6.1 — Upload module | YouTube OAuth, upload API, title/description templating, UTM links | 4 |
| US-7.1 — Scheduler | Windows Task Scheduler entry, daily 09:00 run | 1 |
| US-7.2 — Notifications | Desktop notifications (win10toast), email on critical errors | 2 |
| US-7.3 — Metrics logging | SQLite metrics schema, weekly CSV export | 2 |
| Retry / resume | `--resume {video_id}` CLI flag, state machine for pipeline stages | 2 |
| README + setup guide | Step-by-step setup with API key instructions | 2 |
| **First real publish** | Run end-to-end on a real Telugu video, publish first Short | 2 |

**Definition of Done:**
- One real Short published to your YouTube channel
- Daily scheduler verified by waiting one full day
- README is complete enough that you could re-set-up the project on another machine

---

## Post-MVP (Week 5+) — Iterate Based on Data

| Week | Focus |
|---|---|
| 5 | Watch retention data, tune hook quality, add 2 more Remotion templates |
| 6 | A/B test styles (cohort-analysis skill); kill underperformers |
| 7 | Optimize for review-time < 5 min (US-U1 from RISKS.md) |
| 8 | Decide: cloud deployment (Phase 2) or more polish on local? |

---

## Capacity / Risk Buffer

- Each sprint above is sized at ~15 hours
- **20% buffer** assumed for unknowns; tasks slip → push to next sprint, do NOT compress quality
- If a sprint slips by > 50%, reassess scope (drop a style? simpler templates?)
