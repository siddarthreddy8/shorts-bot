# Shorts Bot — Telugu → Hindi/English YouTube Shorts Automation

Personal automation tool that takes the latest video from 2 fixed Telugu YouTube channels (or any ad-hoc URL), rewrites it as a 30–60s short-form script in your chosen language and style(s), generates a Hoog-style faceless motion-graphics Short via Remotion, and uploads to your YouTube channel daily.

> Reference aesthetic: [Hoog](https://www.youtube.com/channel/UCii9ezsUa_mBiSdw0PtSOaw) — faceless 3D-animated documentary essays.

See `docs/` for full planning artifacts:
- `PRD.md` — product requirements
- `RISKS.md` — risks, assumptions, pre-mortem
- `METRICS.md` — north-star metric + growth loops
- `USER_STORIES.md` — INVEST-format stories
- `SPRINT_PLAN.md` — 4-week MVP plan

---

## Stack

| Layer | Tool |
|---|---|
| Orchestration / monitoring / transcription / translation / upload | **Python** 3.11+ |
| Transcription | **Whisper large-v3** (local, free) |
| Translation + script rewriting | **Anthropic Claude** API |
| TTS | **ElevenLabs** |
| Video generation | **Remotion** (Node.js / React) |
| Review UI | **Streamlit** |
| DB | **SQLite** (local) |
| Scheduler (MVP) | **Windows Task Scheduler** |

---

## Setup

### 1. Python environment

```bash
cd D:/siddarth/youtube/shorts-bot
python -m venv .venv
.venv\Scripts\activate     # Windows bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Config files

```bash
cp .env.example .env
cp config/config.example.yaml config/config.yaml
```

Edit `.env` with your API keys, and `config/config.yaml` with your 2 source channel IDs.

### 3. API keys you'll need

| Service | What it's for | Free tier? |
|---|---|---|
| **Google Cloud → YouTube Data API v3** | Read source channels + upload Shorts | Yes (10k units/day) |
| **Anthropic** | Translation + script rewriting | Paid (~$3/M tokens) |
| **ElevenLabs** | TTS voiceover | Free 10k chars/mo |

Step-by-step key acquisition is in `docs/SETUP.md` (TBD).

### 4. Initialize DB

```bash
python -m src.main init
```

### 5. Verify install

```bash
python -m src.main --help
```

---

## Usage (once Sprint 1+ is built)

```bash
# One-off run for a specific URL
python -m src.main run --url https://www.youtube.com/watch?v=...

# Daily scheduled run (cron / Task Scheduler invokes this)
python -m src.main run

# Launch the script review UI in browser
python -m src.main review-ui
```

---

## Project layout

```
shorts-bot/
├── docs/                  Planning docs (PRD, RISKS, METRICS, etc.)
├── config/                config.yaml + OAuth secrets (gitignored)
├── data/
│   ├── transcripts/       Whisper output
│   ├── scripts/           Generated + approved scripts
│   ├── videos/            Final rendered MP4s
│   └── pipeline.sqlite    Local state
├── logs/                  Rotating logs
├── remotion/              Node.js Remotion project (Sprint 3)
└── src/
    ├── main.py            CLI entry
    ├── db/                SQLite schema + helpers
    ├── monitor/           YouTube channel polling (Sprint 1)
    ├── transcribe/        Whisper wrapper (Sprint 1)
    ├── script/            Translate + rewrite (Sprint 2)
    ├── review/            Streamlit UI (Sprint 3)
    ├── video/             Remotion bridge (Sprint 3)
    ├── upload/            YouTube upload (Sprint 4)
    └── utils/             logger, config
```

---

## Status

🚧 **Sprint 0 — Pre-build validation in progress.** See `docs/SPRINT_PLAN.md`.
