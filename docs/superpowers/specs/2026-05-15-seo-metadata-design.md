# SEO Metadata Generation — Design Spec
**Date:** 2026-05-15
**Status:** Approved
**Feature:** Script-aware SEO metadata generation for every published Short

---

## 1. Overview

For every video in the pipeline, after the script draft is ready, a dedicated SEO module analyzes the script and generates high-performing upload metadata: a keyword-rich title, an SEO-optimized description, platform-tuned hashtags, and thumbnail phrase options.

Generation is a two-step hybrid: Claude performs deep script analysis and generates candidate metadata, then a lightweight trending enrichment step queries real-time signals (Google Trends via `pytrends`, YouTube autocomplete) to rerank hashtags and surface additional high-interest keywords before the output reaches the review UI. No paid API keys required for either signal source.

The user reviews and edits all metadata in the same Streamlit session as the script, then a Remotion thumbnail is rendered alongside the video.

---

## 2. Goals

- Every published Short has a title, description, and hashtags that reflect its specific topic, audience intent, and viral hook — not generic config-file defaults.
- Metadata is independently regenerable without re-running script generation.
- The Remotion pipeline produces both a video MP4 and a thumbnail PNG per run.
- The upload module uses approved SEO metadata from the DB; config template is a null-fallback only.

---

## 3. Architecture

### 3.1 New Module: `src/seo/`

```
src/
  seo/
    __init__.py
    analyzer.py      # Claude call: script → raw SeoMetadata
    trends.py        # real-time enrichment: Google Trends + YouTube autocomplete
    models.py        # SeoMetadata dataclass
```

### 3.2 Updated Pipeline Sequence

```
[Script draft ready]
        ↓
[seo.analyzer.generate(script, topic, style, lang)]
  → Claude deep-analyzes script → raw SeoMetadata (title, desc, hashtags, phrases, niche)
        ↓
[seo.trends.enrich(raw_metadata, topic_hint, language)]
  → Google Trends scores candidate keywords (~2–4 s)
  → YouTube autocomplete fetches related search terms (~1 s)
  → Reranks hashtags by interest score, injects top autocomplete terms
        ↓
[Review UI: script panel + SEO panel, both editable]
        ↓
[User edits → Approve & Render]
        ↓
[asyncio.gather: render video MP4 + render thumbnail PNG]
        ↓
[Upload: title / description / hashtags read from DB row]
```

### 3.3 Pipeline State Machine

```
discovered → transcribed → script_drafted → script_approved
  → seo_generated → video_rendered → uploaded
```

`seo_generated` is inserted between `script_approved` and `video_rendered`. The Claude SEO call fires immediately after the script draft is produced — before the user has reviewed anything — so both panels are populated by the time the review UI loads. The DB status is only written to `seo_generated` when the user clicks "Approve & Render", not at call time.

---

## 4. Data Model

### 4.1 SeoMetadata Dataclass (`src/seo/models.py`)

```python
@dataclass
class SeoMetadata:
    title: str                       # ≤60 chars, strongest keyword first
    description: str                 # 150–200 words, human-readable
    hashtags: list[str]              # 15–20 tags (no spaces)
    thumbnail_phrases: list[str]     # 3 short options (≤6 words each)
    niche: str                       # e.g. "history", "crime", "tech" — drives thumbnail variant
    thumbnail_phrase: str | None = None  # set when user picks one at review
```

### 4.2 DB Schema — New Columns on `videos`

```sql
ALTER TABLE videos ADD COLUMN seo_title                    TEXT;
ALTER TABLE videos ADD COLUMN seo_description              TEXT;
ALTER TABLE videos ADD COLUMN seo_hashtags_json            TEXT;  -- JSON array
ALTER TABLE videos ADD COLUMN seo_thumbnail_phrases_json   TEXT;  -- JSON array, 3 options
ALTER TABLE videos ADD COLUMN seo_thumbnail_phrase         TEXT;  -- user-selected phrase
ALTER TABLE videos ADD COLUMN thumbnail_path               TEXT;  -- rendered PNG path
```

Migration: add columns via `ALTER TABLE` in `db/schema.sql` using `IF NOT EXISTS`-safe pattern (SQLite does not support `ADD COLUMN IF NOT EXISTS` — wrap in try/except on init).

---

## 5. SEO Analyzer (`src/seo/analyzer.py`)

### 5.1 Function Signature

```python
def generate(
    script: str,
    topic_hint: str,      # source_title from DB
    styles: list[str],
    language: str,        # "english" | "hindi"
) -> SeoMetadata:
```

### 5.2 Claude Prompt

**System:**
> You are an expert YouTube/TikTok/Reels SEO strategist. You deeply analyze short-form video scripts and generate high-performing metadata that real users actively search for. Never use generic tags. Every keyword must be directly traceable to the script's specific topic, emotion, or hook.

**User:**
```
## Script
{script}

## Context
- Language: {language}
- Style: {styles}
- Target platform: YouTube Shorts (also optimized for TikTok/Reels)
- Source topic: {topic_hint}

## Task
Step 1 — Analyze the script:
  • Main topic and sub-topics
  • Key named entities (people, places, events, brands)
  • Dominant emotion and audience intent
  • Viral hook pattern used
  • Niche (news, history, tech, crime, etc.)

Step 2 — Generate metadata:
  • title: attention-grabbing, ≤60 chars, strongest keyword first
  • description: 150–200 words, natural language, secondary and
    long-tail keywords woven in, ends with CTA linking to original video
  • hashtags: list of 15–20 — broad (3), niche (10), trending-adjacent (5–7);
    no spaces in tags
  • thumbnail_phrases: 3 short options ≤6 words each,
    high shock/curiosity value, searchable

Return ONLY valid JSON:
{
  "title": "...",
  "description": "...",
  "hashtags": ["...", ...],
  "thumbnail_phrases": ["...", "...", "..."],
  "niche": "..."
}
```

### 5.3 Error Handling

- If Claude returns malformed JSON: retry once with an explicit "return only JSON" reminder appended.
- If retry fails: surface error in review UI with a manual "Regenerate SEO" button; do not block the script review.
- Log the raw Claude response to `events` table (stage=`seo`, level=`error`) on failure.

---

## 6. Trending Enrichment (`src/seo/trends.py`)

### 6.1 Purpose

After Claude produces raw metadata, the enrichment step adds real-time signal without a second Claude call. It does two things:

1. **Google Trends scoring** — scores Claude's candidate keywords against the last 7 days of search interest. High-interest keywords are promoted to the front of the hashtag list; zero-interest ones are moved to the end.
2. **YouTube autocomplete injection** — queries YouTube's suggest endpoint for the script's topic and appends any returned terms not already in the hashtag list (up to 5 additions).

### 6.2 Function Signature

```python
def enrich(metadata: SeoMetadata, topic_hint: str, language: str) -> SeoMetadata:
    """
    Returns a new SeoMetadata with hashtags reranked and autocomplete terms
    injected. All other fields (title, description, niche, thumbnail_phrases)
    are passed through unchanged.
    """
```

### 6.3 Google Trends (`pytrends`)

```python
from pytrends.request import TrendReq

def _score_keywords(keywords: list[str]) -> dict[str, int]:
    pt = TrendReq(hl="en-US", tz=330)      # tz=330 → IST
    pt.build_payload(keywords[:5], timeframe="now 7-d")  # pytrends max 5 per call
    df = pt.interest_over_time()
    return {kw: int(df[kw].mean()) for kw in keywords[:5] if kw in df.columns}
```

- Candidate keywords extracted from: title tokens + top 10 hashtags (stripped of `#`).
- Batched into groups of 5 (pytrends limit). Only one batch needed for typical output.
- Result: dict of `keyword → interest_score (0–100)`.
- Hashtags are reordered: score ≥ 40 → front, score 1–39 → middle, score 0 / not found → end.

### 6.4 YouTube Autocomplete

```python
import httpx

def _youtube_autocomplete(query: str, language: str) -> list[str]:
    lang_code = "hi" if language == "hindi" else "en"
    url = "https://suggestqueries.google.com/complete/search"
    r = httpx.get(url, params={"client": "youtube", "q": query, "hl": lang_code},
                  timeout=5)
    suggestions = r.json()[1]           # index 1 is the suggestion array
    return [s[0] for s in suggestions]  # each suggestion is [term, metadata]
```

- `query` is `topic_hint` (source video title).
- Returns up to ~10 suggestions. Filter to those not already in hashtags, take top 5, prepend `#` and inject into the hashtag list after the high-interest group.

### 6.5 Failure Handling

Both lookups are best-effort. If either raises (rate limit, network timeout, parse error):
- Log a warning to `events` table (stage=`seo`, level=`warn`, message includes the exception).
- Return the metadata unchanged (no enrichment) — do not raise, do not block.
- The review UI shows the unenriched output; user sees no error, just slightly less ranked tags.

---

## 7. Review UI Changes (Streamlit)

The existing script review screen gains a second panel. Both panels load in the same page render; the SEO panel shows a spinner for ~3–5 s while the Claude call completes.

### 7.1 Layout

```
┌──────────────────────────────────────────┐
│  SCRIPT                     [Regenerate] │
│  ┌────────────────────────────────────┐  │
│  │ [editable script text area]        │  │
│  └────────────────────────────────────┘  │
│                                          │
│  SEO METADATA               [Regenerate] │
│  Title:  [editable input, char counter]  │
│  Desc:   [editable textarea]             │
│  Tags:   [pill chips, individually       │
│            removable, + add field]       │
│  Thumbnail:                              │
│    (●) phrase option 1                   │
│    ( ) phrase option 2                   │
│    ( ) phrase option 3                   │
│                                          │
│  [Reject]          [Approve & Render]    │
└──────────────────────────────────────────┘
```

### 7.2 Behavior

- **Regenerate (SEO):** calls `seo.analyzer.generate()` with the current script text (including any user edits). Does not re-run script generation.
- **Approve & Render:** writes all edits to DB, sets status → `seo_generated`, triggers both renders.
- Title field shows character count and turns red at >60 chars.
- Hashtag pills: click × to remove; text input to add custom tags.

---

## 8. Remotion Thumbnail Template

### 8.1 New Template: `remotion/src/templates/Thumbnail.tsx`

Props:
```ts
type ThumbnailProps = {
  phrase: string;    // chosen thumbnail_phrase
  style: string;     // drives accent color palette
  niche: string;     // extracted from SEO context; used for background variant
}
```

Renders at **1280×720** (YouTube standard thumbnail). Visual treatment: Hoog-style atmospheric dark background (deep blue/warm orange gradient matching the video template), bold white sans-serif phrase centered with a drop shadow, channel logo bottom-right corner.

### 8.2 Render Command

```bash
npx remotion still Thumbnail out/thumbnail.png \
  --props='{"phrase":"...","style":"...","niche":"..."}'
```

### 8.3 Python Bridge

```python
# In the render stage — both jobs dispatched concurrently
async def render_all(video_id, script_data, seo_data):
    await asyncio.gather(
        render_video(video_id, script_data),
        render_thumbnail(
            video_id,
            phrase=seo_data.thumbnail_phrase,
            style=script_data.style,
            niche=seo_data.niche,
        ),
    )
```

Output saved to `data/videos/{video_id}_thumbnail.png`. Path written to `videos.thumbnail_path`.

### 8.4 Upload Integration

YouTube Data API v3 accepts a separate thumbnail upload call (`thumbnails.set`). The upload module calls this after the video upload completes, using `thumbnail_path` from the DB row.

---

## 9. Upload Module Changes

The upload module currently reads title/description/tags from `config.yaml` templates. After this feature:

1. Read `seo_title`, `seo_description`, `seo_hashtags_json` from the DB row.
2. If any are null (SEO module was skipped or failed), fall back to the config template.
3. After video upload, call `thumbnails.set` with `thumbnail_path` if present.

---

## 10. Out of Scope

- Automatic A/B testing of titles across uploads.
- SEO performance analytics (click-through rate correlation) — Phase 3.
- Multi-language hashtag generation (Hindi hashtags for English-language output).
- Paid keyword research APIs (RapidAPI, Ahrefs, etc.).

---

## 11. Open Questions

- None. All design decisions are resolved.
