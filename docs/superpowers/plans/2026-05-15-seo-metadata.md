# SEO Metadata Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For every Short in the pipeline, automatically generate a keyword-rich title, SEO-optimized description, reranked hashtags (backed by real-time Google Trends + YouTube autocomplete), and a Remotion-rendered thumbnail — all reviewable and editable in the Streamlit UI before upload.

**Architecture:** A new `src/seo/` module chains two steps: Claude analyzes the script and returns structured metadata JSON, then `trends.py` reranks hashtags by Google Trends interest score and injects YouTube autocomplete suggestions. The approved metadata is stored in six new DB columns and consumed by the upload module; a new `Thumbnail.tsx` Remotion composition renders a 1280×720 PNG alongside the video.

**Tech Stack:** Python 3.12, OpenAI SDK (OpenRouter gateway to Claude), `pytrends`, `requests`, SQLite, Streamlit, React/TypeScript (Remotion v4), Zod.

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `requirements.txt` | Add `pytrends>=4.9.2` |
| Create | `tests/__init__.py` | Pytest package root |
| Create | `tests/seo/__init__.py` | Pytest package for SEO tests |
| Modify | `src/db/schema.sql` | Add 6 new columns to `videos` CREATE TABLE |
| Modify | `src/db/database.py` | Add `_apply_migrations()` for safe ALTER TABLE on existing DBs |
| Create | `src/seo/__init__.py` | Public API: `generate_and_enrich()` |
| Create | `src/seo/models.py` | `SeoMetadata` dataclass |
| Create | `src/seo/analyzer.py` | Claude call via OpenAI SDK → raw `SeoMetadata` |
| Create | `src/seo/trends.py` | Google Trends reranking + YouTube autocomplete injection |
| Create | `tests/seo/test_db_migration.py` | Tests for safe DB migration logic |
| Create | `tests/seo/test_models.py` | Unit tests for `SeoMetadata` |
| Create | `tests/seo/test_analyzer.py` | Unit tests for `analyzer.generate()` |
| Create | `tests/seo/test_trends.py` | Unit tests for `trends.enrich()` and helpers |
| Create | `remotion/src/compositions/Thumbnail.tsx` | Static 1280×720 thumbnail composition |
| Modify | `remotion/src/Root.tsx` | Register `Thumbnail` composition |
| Create | `src/video/render.py` | `render_thumbnail()` async helper — subprocess call to `remotion still` |
| Create | `tests/seo/test_render.py` | Unit tests for `render_thumbnail()` |
| Create | `src/review/app.py` | Streamlit review UI: script panel + SEO panel |
| Create | `src/review/__init__.py` | Package marker |

---

## Task 1: Add pytrends + test infrastructure

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py`
- Create: `tests/seo/__init__.py`

- [ ] **Step 1: Add pytrends to requirements.txt**

Open `requirements.txt`. After the `requests==2.32.3` line, add:

```
pytrends>=4.9.2
```

- [ ] **Step 2: Install the new dependency**

```bash
cd D:/siddarth/youtube/shorts-bot
.venv/Scripts/pip install pytrends>=4.9.2
```

Expected: `Successfully installed pytrends-...`

- [ ] **Step 3: Create test package files**

Create `tests/__init__.py` (empty file) and `tests/seo/__init__.py` (empty file):

```bash
mkdir -p D:/siddarth/youtube/shorts-bot/tests/seo
touch D:/siddarth/youtube/shorts-bot/tests/__init__.py
touch D:/siddarth/youtube/shorts-bot/tests/seo/__init__.py
```

- [ ] **Step 4: Verify pytest discovers the package**

```bash
cd D:/siddarth/youtube/shorts-bot
.venv/Scripts/pytest tests/ --collect-only
```

Expected: `no tests ran` (empty but no errors).

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/__init__.py tests/seo/__init__.py
git commit -m "chore: add pytrends dependency and test package scaffolding"
```

---

## Task 2: DB migration — new columns

**Files:**
- Modify: `src/db/schema.sql`
- Modify: `src/db/database.py`

- [ ] **Step 1: Write the failing test**

Create `tests/seo/test_db_migration.py`:

```python
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch


def _fresh_db(schema_sql: str) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(schema_sql)
    return conn


def test_new_columns_exist_in_fresh_db():
    schema = Path("src/db/schema.sql").read_text(encoding="utf-8")
    conn = _fresh_db(schema)
    cursor = conn.execute("PRAGMA table_info(videos)")
    columns = {row[1] for row in cursor.fetchall()}
    expected = {
        "seo_title", "seo_description", "seo_hashtags_json",
        "seo_thumbnail_phrases_json", "seo_thumbnail_phrase", "thumbnail_path",
    }
    assert expected.issubset(columns), f"Missing columns: {expected - columns}"


def test_migration_adds_columns_to_existing_db():
    # Simulate a DB created before the new columns existed.
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE videos (
            video_id TEXT PRIMARY KEY,
            source_channel_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'discovered'
        )
    """)
    conn.commit()

    # Run only the migration logic (not the full schema which would fail on table exists).
    NEW_COLS = [
        ("seo_title", "TEXT"),
        ("seo_description", "TEXT"),
        ("seo_hashtags_json", "TEXT"),
        ("seo_thumbnail_phrases_json", "TEXT"),
        ("seo_thumbnail_phrase", "TEXT"),
        ("thumbnail_path", "TEXT"),
    ]
    for col, col_type in NEW_COLS:
        try:
            conn.execute(f"ALTER TABLE videos ADD COLUMN {col} {col_type}")
        except Exception:
            pass
    conn.commit()

    cursor = conn.execute("PRAGMA table_info(videos)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "seo_title" in columns
    assert "thumbnail_path" in columns
```

- [ ] **Step 2: Run to confirm it fails**

```bash
cd D:/siddarth/youtube/shorts-bot
.venv/Scripts/pytest tests/seo/test_db_migration.py -v
```

Expected: `FAILED test_new_columns_exist_in_fresh_db` — columns don't exist yet.

- [ ] **Step 3: Add new columns to `src/db/schema.sql`**

Open `src/db/schema.sql`. Inside the `CREATE TABLE IF NOT EXISTS videos (...)` block, add the six new columns before the closing `);`. Insert them after the `cost_usd REAL,` line:

```sql
    -- SEO metadata
    seo_title                    TEXT,
    seo_description              TEXT,
    seo_hashtags_json            TEXT,           -- JSON array
    seo_thumbnail_phrases_json   TEXT,           -- JSON array, 3 options
    seo_thumbnail_phrase         TEXT,           -- user-selected phrase
    thumbnail_path               TEXT,           -- rendered PNG path
```

- [ ] **Step 4: Add `_apply_migrations()` to `src/db/database.py`**

Open `src/db/database.py`. After the `_SCHEMA_PATH` line and before `init_db()`, add:

```python
_NEW_COLUMNS: list[tuple[str, str]] = [
    ("seo_title", "TEXT"),
    ("seo_description", "TEXT"),
    ("seo_hashtags_json", "TEXT"),
    ("seo_thumbnail_phrases_json", "TEXT"),
    ("seo_thumbnail_phrase", "TEXT"),
    ("thumbnail_path", "TEXT"),
]


def _apply_migrations(conn: sqlite3.Connection) -> None:
    for col, col_type in _NEW_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE videos ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass  # column already exists
```

Then update `init_db()` to call it:

```python
def init_db() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    with sqlite3.connect(_DB_PATH) as conn:
        conn.executescript(schema)
        _apply_migrations(conn)
    logger.info(f"DB initialized at {_DB_PATH}")
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
.venv/Scripts/pytest tests/seo/test_db_migration.py -v
```

Expected: `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/db/schema.sql src/db/database.py tests/seo/test_db_migration.py
git commit -m "feat(db): add SEO metadata columns to videos table with safe migration"
```

---

## Task 3: SeoMetadata dataclass

**Files:**
- Create: `src/seo/__init__.py` (empty for now)
- Create: `src/seo/models.py`
- Create: `tests/seo/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/seo/test_models.py`:

```python
from src.seo.models import SeoMetadata


def test_seo_metadata_defaults_thumbnail_phrase_to_none():
    m = SeoMetadata(
        title="The Truth About Hyderabad",
        description="A detailed description about the historic city.",
        hashtags=["#hyderabad", "#history", "#shorts"],
        thumbnail_phrases=["Secret Revealed", "You Won't Believe", "History Shocked"],
        niche="history",
    )
    assert m.thumbnail_phrase is None


def test_seo_metadata_accepts_chosen_phrase():
    m = SeoMetadata(
        title="T",
        description="D",
        hashtags=["#test"],
        thumbnail_phrases=["p1", "p2", "p3"],
        niche="tech",
        thumbnail_phrase="p2",
    )
    assert m.thumbnail_phrase == "p2"


def test_seo_metadata_stores_all_fields():
    m = SeoMetadata(
        title="Breaking: Hyderabad's Hidden Past",
        description="Discover the secrets of the city.",
        hashtags=["#hyderabad", "#documentary"],
        thumbnail_phrases=["Shocking Truth", "Nobody Knew This", "History Exposed"],
        niche="history",
        thumbnail_phrase="Shocking Truth",
    )
    assert m.title == "Breaking: Hyderabad's Hidden Past"
    assert m.niche == "history"
    assert len(m.hashtags) == 2
    assert len(m.thumbnail_phrases) == 3
```

- [ ] **Step 2: Run to confirm it fails**

```bash
.venv/Scripts/pytest tests/seo/test_models.py -v
```

Expected: `ImportError` — `src.seo.models` does not exist.

- [ ] **Step 3: Create `src/seo/__init__.py`**

Create `src/seo/__init__.py` as an empty file:

```python
```

- [ ] **Step 4: Create `src/seo/models.py`**

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SeoMetadata:
    title: str
    description: str
    hashtags: list[str]
    thumbnail_phrases: list[str]
    niche: str
    thumbnail_phrase: str | None = None
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
.venv/Scripts/pytest tests/seo/test_models.py -v
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/seo/__init__.py src/seo/models.py tests/seo/test_models.py
git commit -m "feat(seo): add SeoMetadata dataclass"
```

---

## Task 4: SEO Analyzer

**Files:**
- Create: `src/seo/analyzer.py`
- Create: `tests/seo/test_analyzer.py`

The analyzer calls Claude via OpenRouter using the `openai` SDK (already in `requirements.txt`). It uses a two-step prompt: analyze the script, then emit metadata as JSON. On bad JSON it retries once before raising.

- [ ] **Step 1: Write the failing tests**

Create `tests/seo/test_analyzer.py`:

```python
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.seo.analyzer import generate
from src.seo.models import SeoMetadata

_VALID_JSON = json.dumps({
    "title": "The Shocking Truth About Hyderabad",
    "description": (
        "Hyderabad has a hidden history that most people never hear about. "
        "In this short, we uncover the secrets buried beneath the old city. "
        "Watch the full documentary — link in description."
    ),
    "hashtags": ["#hyderabad", "#history", "#shorts", "#india", "#documentary"],
    "thumbnail_phrases": ["You Won't Believe This", "The Secret Nobody Knows", "History Uncovered"],
    "niche": "history",
})


def _mock_client(content: str) -> MagicMock:
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    client = MagicMock()
    client.chat.completions.create.return_value = resp
    return client


def test_generate_returns_seo_metadata():
    with patch("src.seo.analyzer._make_client", return_value=_mock_client(_VALID_JSON)), \
         patch("src.seo.analyzer.env", return_value="anthropic/claude-sonnet-4-6"):
        result = generate("A short script about Hyderabad.", "Hyderabad History", ["documentary"], "english")

    assert isinstance(result, SeoMetadata)
    assert result.title == "The Shocking Truth About Hyderabad"
    assert result.niche == "history"
    assert len(result.hashtags) == 5
    assert len(result.thumbnail_phrases) == 3
    assert result.thumbnail_phrase is None


def test_generate_strips_markdown_code_fences():
    wrapped = f"```json\n{_VALID_JSON}\n```"
    with patch("src.seo.analyzer._make_client", return_value=_mock_client(wrapped)), \
         patch("src.seo.analyzer.env", return_value="anthropic/claude-sonnet-4-6"):
        result = generate("script", "topic", ["comedy"], "english")

    assert result.title == "The Shocking Truth About Hyderabad"


def test_generate_retries_once_on_bad_json():
    bad_choice = MagicMock()
    bad_choice.message.content = "Not JSON at all, sorry."
    bad_resp = MagicMock()
    bad_resp.choices = [bad_choice]

    good_choice = MagicMock()
    good_choice.message.content = _VALID_JSON
    good_resp = MagicMock()
    good_resp.choices = [good_choice]

    client = MagicMock()
    client.chat.completions.create.side_effect = [bad_resp, good_resp]

    with patch("src.seo.analyzer._make_client", return_value=client), \
         patch("src.seo.analyzer.env", return_value="model"):
        result = generate("script", "topic", ["serious"], "hindi")

    assert client.chat.completions.create.call_count == 2
    assert result.niche == "history"


def test_generate_raises_after_two_failures():
    client = _mock_client("still not json")
    with patch("src.seo.analyzer._make_client", return_value=client), \
         patch("src.seo.analyzer.env", return_value="model"):
        with pytest.raises(ValueError, match="SEO analyzer failed after 2 attempts"):
            generate("script", "topic", ["explainer"], "english")
```

- [ ] **Step 2: Run to confirm they fail**

```bash
.venv/Scripts/pytest tests/seo/test_analyzer.py -v
```

Expected: `ImportError` — `src.seo.analyzer` does not exist.

- [ ] **Step 3: Create `src/seo/analyzer.py`**

```python
from __future__ import annotations

import json

from openai import OpenAI

from src.seo.models import SeoMetadata
from src.utils.config import env
from src.utils.logger import logger

_SYSTEM = (
    "You are an expert YouTube/TikTok/Reels SEO strategist. You deeply analyze "
    "short-form video scripts and generate high-performing metadata that real users "
    "actively search for. Never use generic tags. Every keyword must be directly "
    "traceable to the script's specific topic, emotion, or hook."
)

_USER_TEMPLATE = """\
## Script
{script}

## Context
- Language: {language}
- Style: {styles}
- Target platform: YouTube Shorts (also optimized for TikTok/Reels)
- Source topic: {topic_hint}

## Task
Step 1 — Analyze the script:
  * Main topic and sub-topics
  * Key named entities (people, places, events, brands)
  * Dominant emotion and audience intent
  * Viral hook pattern used
  * Niche (news, history, tech, crime, etc.)

Step 2 — Generate metadata:
  * title: attention-grabbing, 60 chars max, strongest keyword first
  * description: 150-200 words, natural language, secondary and long-tail keywords
    woven in, ends with CTA linking to original video
  * hashtags: list of 15-20 — broad (3), niche (10), trending-adjacent (5-7);
    no spaces inside tags
  * thumbnail_phrases: 3 short options 6 words max each, high shock/curiosity value
  * niche: single word or short phrase for content category

Return ONLY valid JSON — no markdown, no explanation:
{{
  "title": "...",
  "description": "...",
  "hashtags": ["...", "..."],
  "thumbnail_phrases": ["...", "...", "..."],
  "niche": "..."
}}"""


def _make_client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=env("OPENROUTER_API_KEY", required=True),
    )


def _parse(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


def generate(
    script: str,
    topic_hint: str,
    styles: list[str],
    language: str,
) -> SeoMetadata:
    client = _make_client()
    model = env("AI_MODEL", default="anthropic/claude-sonnet-4-6")
    user_msg = _USER_TEMPLATE.format(
        script=script,
        language=language,
        styles=", ".join(styles),
        topic_hint=topic_hint,
    )
    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": user_msg},
    ]

    last_raw = ""
    for attempt in range(2):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
        )
        last_raw = resp.choices[0].message.content or ""
        try:
            data = _parse(last_raw)
            return SeoMetadata(
                title=data["title"],
                description=data["description"],
                hashtags=data["hashtags"],
                thumbnail_phrases=data["thumbnail_phrases"],
                niche=data["niche"],
            )
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning(f"SEO analyzer bad JSON on attempt {attempt + 1}: {exc}")
            if attempt == 0:
                messages.append({"role": "assistant", "content": last_raw})
                messages.append({
                    "role": "user",
                    "content": "Return ONLY valid JSON matching the schema above. No extra text.",
                })

    raise ValueError(
        f"SEO analyzer failed after 2 attempts. Last response: {last_raw[:200]}"
    )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
.venv/Scripts/pytest tests/seo/test_analyzer.py -v
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/seo/analyzer.py tests/seo/test_analyzer.py
git commit -m "feat(seo): add Claude-powered SEO analyzer"
```

---

## Task 5: Trends enrichment

**Files:**
- Create: `src/seo/trends.py`
- Create: `tests/seo/test_trends.py`

The enrichment step is best-effort: any failure returns the original metadata unchanged. It uses `pytrends` (module-level import so tests can patch it) and `requests` (already in requirements.txt).

- [ ] **Step 1: Write the failing tests**

Create `tests/seo/test_trends.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.seo.models import SeoMetadata
from src.seo.trends import _score_keywords, _youtube_autocomplete, enrich


def _meta(**overrides) -> SeoMetadata:
    defaults = dict(
        title="Hyderabad Secret History",
        description="A description.",
        hashtags=["#low", "#high", "#medium"],
        thumbnail_phrases=["Shocked", "Nobody Knew", "History Exposed"],
        niche="history",
    )
    defaults.update(overrides)
    return SeoMetadata(**defaults)


# --- _score_keywords ---

def test_score_keywords_returns_average_interest():
    mock_pt = MagicMock()
    df = pd.DataFrame({"hyderabad": [60, 70, 80], "history": [20, 30, 25]})
    mock_pt.interest_over_time.return_value = df

    with patch("src.seo.trends.TrendReq", return_value=mock_pt):
        scores = _score_keywords(["hyderabad", "history"])

    assert scores["hyderabad"] == 70
    assert scores["history"] == 25


def test_score_keywords_skips_missing_columns():
    mock_pt = MagicMock()
    df = pd.DataFrame({"known": [50, 50]})
    mock_pt.interest_over_time.return_value = df

    with patch("src.seo.trends.TrendReq", return_value=mock_pt):
        scores = _score_keywords(["known", "unknown"])

    assert "known" in scores
    assert "unknown" not in scores


def test_score_keywords_returns_empty_on_pytrends_failure():
    with patch("src.seo.trends.TrendReq", side_effect=Exception("rate limited")):
        scores = _score_keywords(["any"])

    assert scores == {}


# --- _youtube_autocomplete ---

def test_youtube_autocomplete_returns_suggestion_strings():
    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        "hyderabad history",
        [["hyderabad history 2024", {}], ["hyderabad old city", {}]],
    ]
    mock_resp.raise_for_status.return_value = None

    with patch("src.seo.trends.requests.get", return_value=mock_resp):
        results = _youtube_autocomplete("hyderabad history", "english")

    assert results == ["hyderabad history 2024", "hyderabad old city"]


def test_youtube_autocomplete_returns_empty_on_network_failure():
    with patch("src.seo.trends.requests.get", side_effect=Exception("timeout")):
        results = _youtube_autocomplete("anything", "hindi")

    assert results == []


# --- enrich ---

def test_enrich_puts_high_score_hashtag_first():
    # hashtags: #low (score 0), #high (score 85), #medium (score 32)
    base = _meta()

    mock_pt = MagicMock()
    df = pd.DataFrame({"low": [0, 0], "high": [80, 90], "medium": [30, 35]})
    mock_pt.interest_over_time.return_value = df

    mock_resp = MagicMock()
    mock_resp.json.return_value = ["q", []]
    mock_resp.raise_for_status.return_value = None

    with patch("src.seo.trends.TrendReq", return_value=mock_pt), \
         patch("src.seo.trends.requests.get", return_value=mock_resp):
        result = enrich(base, "hyderabad history", "english")

    assert result.hashtags[0] == "#high"
    assert result.hashtags[-1] == "#low"


def test_enrich_injects_autocomplete_tags():
    base = _meta(hashtags=["#hyderabad"])

    mock_pt = MagicMock()
    mock_pt.interest_over_time.return_value = pd.DataFrame()

    mock_resp = MagicMock()
    mock_resp.json.return_value = [
        "q",
        [["brand new term", {}], ["another fresh term", {}]],
    ]
    mock_resp.raise_for_status.return_value = None

    with patch("src.seo.trends.TrendReq", return_value=mock_pt), \
         patch("src.seo.trends.requests.get", return_value=mock_resp):
        result = enrich(base, "topic", "english")

    assert "#brandnewterm" in result.hashtags
    assert "#anotherfreshterm" in result.hashtags


def test_enrich_does_not_duplicate_existing_hashtags():
    base = _meta(hashtags=["#hyderabad"])

    mock_pt = MagicMock()
    mock_pt.interest_over_time.return_value = pd.DataFrame()

    mock_resp = MagicMock()
    # "hyderabad" is already in hashtags → should not be added again
    mock_resp.json.return_value = ["q", [["hyderabad", {}], ["new one", {}]]]
    mock_resp.raise_for_status.return_value = None

    with patch("src.seo.trends.TrendReq", return_value=mock_pt), \
         patch("src.seo.trends.requests.get", return_value=mock_resp):
        result = enrich(base, "topic", "english")

    assert result.hashtags.count("#hyderabad") == 1


def test_enrich_returns_original_on_total_failure():
    base = _meta()

    with patch("src.seo.trends._score_keywords", side_effect=Exception("boom")):
        result = enrich(base, "topic", "english")

    assert result.hashtags == base.hashtags
    assert result.title == base.title
    assert result.niche == base.niche


def test_enrich_passthrough_fields_unchanged():
    base = _meta()

    mock_pt = MagicMock()
    mock_pt.interest_over_time.return_value = pd.DataFrame()

    mock_resp = MagicMock()
    mock_resp.json.return_value = ["q", []]
    mock_resp.raise_for_status.return_value = None

    with patch("src.seo.trends.TrendReq", return_value=mock_pt), \
         patch("src.seo.trends.requests.get", return_value=mock_resp):
        result = enrich(base, "topic", "english")

    assert result.title == base.title
    assert result.description == base.description
    assert result.niche == base.niche
    assert result.thumbnail_phrases == base.thumbnail_phrases
```

- [ ] **Step 2: Run to confirm they fail**

```bash
.venv/Scripts/pytest tests/seo/test_trends.py -v
```

Expected: `ImportError` — `src.seo.trends` does not exist.

- [ ] **Step 3: Create `src/seo/trends.py`**

```python
from __future__ import annotations

import dataclasses

import requests
from pytrends.request import TrendReq

from src.seo.models import SeoMetadata
from src.utils.logger import logger


def _score_keywords(keywords: list[str]) -> dict[str, int]:
    scores: dict[str, int] = {}
    try:
        pt = TrendReq(hl="en-US", tz=330)
        for i in range(0, len(keywords), 5):
            batch = keywords[i : i + 5]
            try:
                pt.build_payload(batch, timeframe="now 7-d")
                df = pt.interest_over_time()
                for kw in batch:
                    if kw in df.columns:
                        scores[kw] = int(df[kw].mean())
            except Exception as exc:
                logger.warning(f"pytrends batch {batch} failed: {exc}")
    except Exception as exc:
        logger.warning(f"pytrends init failed: {exc}")
    return scores


def _youtube_autocomplete(query: str, language: str) -> list[str]:
    lang_code = "hi" if language == "hindi" else "en"
    try:
        r = requests.get(
            "https://suggestqueries.google.com/complete/search",
            params={"client": "youtube", "q": query, "hl": lang_code},
            timeout=5,
        )
        r.raise_for_status()
        suggestions = r.json()[1]
        return [s[0] for s in suggestions]
    except Exception as exc:
        logger.warning(f"YouTube autocomplete failed: {exc}")
        return []


def enrich(metadata: SeoMetadata, topic_hint: str, language: str) -> SeoMetadata:
    try:
        title_tokens = [w.lower() for w in metadata.title.split() if len(w) > 3]
        tag_tokens = [h.lstrip("#") for h in metadata.hashtags[:10]]
        candidates = list(dict.fromkeys(title_tokens + tag_tokens))

        scores = _score_keywords(candidates)

        def _rank(tag: str) -> int:
            score = scores.get(tag.lstrip("#").lower(), -1)
            if score >= 40:
                return 0
            if score >= 1:
                return 1
            return 2

        ranked = sorted(metadata.hashtags, key=_rank)

        existing = {h.lstrip("#").lower() for h in ranked}
        injected = 0
        for suggestion in _youtube_autocomplete(topic_hint, language):
            if injected >= 5:
                break
            normalized = suggestion.lower()
            if normalized not in existing:
                ranked.append("#" + suggestion.replace(" ", "").lower())
                existing.add(normalized)
                injected += 1

        return dataclasses.replace(metadata, hashtags=ranked)

    except Exception as exc:
        logger.warning(f"Trending enrichment failed, returning unchanged: {exc}")
        return metadata
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
.venv/Scripts/pytest tests/seo/test_trends.py -v
```

Expected: `9 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/seo/trends.py tests/seo/test_trends.py
git commit -m "feat(seo): add Google Trends reranking and YouTube autocomplete injection"
```

---

## Task 6: SEO module public API

**Files:**
- Modify: `src/seo/__init__.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/seo/test_models.py` (append at the bottom):

```python
from unittest.mock import patch, MagicMock
from src.seo import generate_and_enrich


def test_generate_and_enrich_chains_both_steps():
    from src.seo.models import SeoMetadata

    raw = SeoMetadata(
        title="Raw Title",
        description="Raw desc.",
        hashtags=["#raw"],
        thumbnail_phrases=["p1", "p2", "p3"],
        niche="tech",
    )
    enriched = SeoMetadata(
        title="Raw Title",
        description="Raw desc.",
        hashtags=["#raw", "#injected"],
        thumbnail_phrases=["p1", "p2", "p3"],
        niche="tech",
    )

    # Patch through the module objects — matches how __init__.py calls them
    with patch("src.seo.analyzer.generate", return_value=raw) as mock_gen, \
         patch("src.seo.trends.enrich", return_value=enriched) as mock_enrich:
        result = generate_and_enrich("script", "topic", ["comedy"], "english")

    mock_gen.assert_called_once_with("script", "topic", ["comedy"], "english")
    mock_enrich.assert_called_once_with(raw, "topic", "english")
    assert "#injected" in result.hashtags
```

- [ ] **Step 2: Run to confirm it fails**

```bash
.venv/Scripts/pytest tests/seo/test_models.py::test_generate_and_enrich_chains_both_steps -v
```

Expected: `ImportError` — `generate_and_enrich` not yet in `__init__.py`.

- [ ] **Step 3: Update `src/seo/__init__.py`**

Import through module objects (not `from ... import name`) so that unit tests can patch `src.seo.analyzer.generate` and `src.seo.trends.enrich` without hitting a stale local reference:

```python
from src.seo import analyzer, trends
from src.seo.models import SeoMetadata


def generate_and_enrich(
    script: str,
    topic_hint: str,
    styles: list[str],
    language: str,
) -> SeoMetadata:
    raw = analyzer.generate(script, topic_hint, styles, language)
    return trends.enrich(raw, topic_hint, language)


__all__ = ["generate_and_enrich", "SeoMetadata"]
```

- [ ] **Step 4: Run all SEO tests**

```bash
.venv/Scripts/pytest tests/seo/ -v
```

Expected: all tests pass (should be 17+).

- [ ] **Step 5: Commit**

```bash
git add src/seo/__init__.py tests/seo/test_models.py
git commit -m "feat(seo): wire generate_and_enrich public API"
```

---

## Task 7: Remotion Thumbnail composition

**Files:**
- Create: `remotion/src/compositions/Thumbnail.tsx`
- Modify: `remotion/src/Root.tsx`

The thumbnail renders a single static frame at 1280×720. It follows the same zod-schema pattern as the other compositions. Background color shifts by niche to distinguish content categories.

- [ ] **Step 1: Create `remotion/src/compositions/Thumbnail.tsx`**

```tsx
import { AbsoluteFill } from "remotion";
import { z } from "zod";

export const thumbnailSchema = z.object({
  phrase: z.string(),
  style: z.string(),
  niche: z.string(),
});

type Props = z.infer<typeof thumbnailSchema>;

const NICHE_PALETTE: Record<string, { bg: string; accent: string }> = {
  history:     { bg: "#0a0e1a", accent: "#c97a20" },
  crime:       { bg: "#0d0a0a", accent: "#c0392b" },
  tech:        { bg: "#080c18", accent: "#2980b9" },
  politics:    { bg: "#0a0c10", accent: "#8e44ad" },
  science:     { bg: "#080f14", accent: "#27ae60" },
  default:     { bg: "#080c18", accent: "#e67e22" },
};

function palette(niche: string) {
  return NICHE_PALETTE[niche.toLowerCase()] ?? NICHE_PALETTE.default;
}

export const Thumbnail: React.FC<Props> = ({ phrase, style, niche }) => {
  const { bg, accent } = palette(niche);

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(ellipse at 40% 50%, ${accent}33 0%, ${bg} 65%)`,
        backgroundColor: bg,
        fontFamily: "'Inter', 'Arial Black', sans-serif",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        padding: "60px 80px",
      }}
    >
      {/* Atmospheric grid */}
      <AbsoluteFill
        style={{
          backgroundImage: `
            linear-gradient(${accent}18 1px, transparent 1px),
            linear-gradient(90deg, ${accent}18 1px, transparent 1px)
          `,
          backgroundSize: "80px 80px",
          opacity: 0.4,
        }}
      />

      {/* Vignette */}
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 35%, rgba(0,0,0,0.80) 100%)",
        }}
      />

      {/* Accent bar */}
      <div
        style={{
          position: "absolute",
          left: 60,
          top: "50%",
          transform: "translateY(-50%)",
          width: 8,
          height: "40%",
          background: accent,
          borderRadius: 4,
          boxShadow: `0 0 24px ${accent}99`,
        }}
      />

      {/* Main phrase */}
      <p
        style={{
          position: "relative",
          zIndex: 10,
          color: "#ffffff",
          fontSize: 88,
          fontWeight: 900,
          lineHeight: 1.1,
          textAlign: "center",
          textTransform: "uppercase",
          letterSpacing: "-1px",
          textShadow: `0 4px 32px rgba(0,0,0,0.9), 0 0 60px ${accent}66`,
          margin: 0,
        }}
      >
        {phrase}
      </p>

      {/* Niche label */}
      <p
        style={{
          position: "absolute",
          bottom: 40,
          right: 60,
          color: `${accent}cc`,
          fontSize: 28,
          fontWeight: 600,
          letterSpacing: "3px",
          textTransform: "uppercase",
          margin: 0,
          zIndex: 10,
        }}
      >
        {niche.toUpperCase()}
      </p>
    </AbsoluteFill>
  );
};
```

- [ ] **Step 2: Register in `remotion/src/Root.tsx`**

Add the import at the top of `Root.tsx` (after the existing imports):

```tsx
import { Thumbnail, thumbnailSchema } from "./compositions/Thumbnail";
```

Then add a new `<Composition>` block inside the `<>...</>` fragment, after the HoogTypography block:

```tsx
      <Composition
        id="Thumbnail"
        component={Thumbnail}
        durationInFrames={1}
        fps={30}
        width={1280}
        height={720}
        schema={thumbnailSchema}
        defaultProps={{
          phrase: "The Truth Revealed",
          style: "documentary",
          niche: "history",
        }}
      />
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd D:/siddarth/youtube/shorts-bot/remotion
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Manually verify in Remotion Studio**

```bash
npm run dev
```

Open the browser at `http://localhost:3000`. Select `Thumbnail` from the composition list. Confirm the 1280×720 thumbnail renders with the phrase, accent bar, grid, and niche label.

- [ ] **Step 5: Test still render**

```bash
npx remotion still Thumbnail test_thumb.png \
  --props='{"phrase":"You Wont Believe This","style":"documentary","niche":"history"}'
```

Expected: `test_thumb.png` created in `remotion/`. Open it and confirm it looks correct. Then delete it:

```bash
rm test_thumb.png
```

- [ ] **Step 6: Commit**

```bash
cd D:/siddarth/youtube/shorts-bot
git add remotion/src/compositions/Thumbnail.tsx remotion/src/Root.tsx
git commit -m "feat(remotion): add Thumbnail composition (1280x720, niche-aware palette)"
```

---

## Task 8: Python thumbnail render helper

**Files:**
- Create: `src/video/render.py`
- Create: `tests/seo/test_render.py`

This wraps `remotion still Thumbnail` in an async subprocess call. It is the bridge spec section 8.3 describes. The full concurrent `render_all()` will be wired in Sprint 3 when the video render module is built; this task delivers the `render_thumbnail()` half so it can be tested and integrated without the rest.

- [ ] **Step 1: Write the failing tests**

Create `tests/seo/test_render.py`:

```python
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.video.render import render_thumbnail


@pytest.mark.asyncio
async def test_render_thumbnail_returns_path_on_success():
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))

    with patch("src.video.render.asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("src.video.render.project_root", return_value=Path("/fake")):
        result = await render_thumbnail(
            video_id="abc123",
            phrase="You Won't Believe This",
            style="documentary",
            niche="history",
        )

    assert result == Path("/fake/data/videos/abc123_thumbnail.png")


@pytest.mark.asyncio
async def test_render_thumbnail_raises_on_nonzero_exit():
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.communicate = AsyncMock(return_value=(b"", b"Render error"))

    with patch("src.video.render.asyncio.create_subprocess_exec", return_value=mock_proc), \
         patch("src.video.render.project_root", return_value=Path("/fake")):
        with pytest.raises(RuntimeError, match="Thumbnail render failed"):
            await render_thumbnail("vid1", "phrase", "style", "niche")


@pytest.mark.asyncio
async def test_render_thumbnail_passes_correct_props():
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))
    captured_args = []

    async def capture(*args, **kwargs):
        captured_args.extend(args)
        return mock_proc

    with patch("src.video.render.asyncio.create_subprocess_exec", side_effect=capture), \
         patch("src.video.render.project_root", return_value=Path("/fake")):
        await render_thumbnail("vid1", "Shocking Truth", "documentary", "history")

    props_arg = next(a for a in captured_args if "--props=" in str(a))
    assert "Shocking Truth" in props_arg
    assert "history" in props_arg
```

- [ ] **Step 2: Add pytest-asyncio to requirements**

```
pytest-asyncio>=0.24.0
```

Add that line to `requirements.txt` under the `# Dev` section.

```bash
.venv/Scripts/pip install pytest-asyncio>=0.24.0
```

Expected: `Successfully installed pytest-asyncio-...`

- [ ] **Step 3: Run to confirm tests fail**

```bash
.venv/Scripts/pytest tests/seo/test_render.py -v
```

Expected: `ImportError` — `src.video.render` does not exist.

- [ ] **Step 4: Create `src/video/render.py`**

(The `src/video/__init__.py` already exists as an empty stub.)

```python
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from src.utils.config import project_root

_REMOTION_DIR = project_root() / "remotion"


async def render_thumbnail(
    video_id: str,
    phrase: str,
    style: str,
    niche: str,
) -> Path:
    out_path = project_root() / "data" / "videos" / f"{video_id}_thumbnail.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    props = json.dumps({"phrase": phrase, "style": style, "niche": niche})
    proc = await asyncio.create_subprocess_exec(
        "npx", "remotion", "still", "Thumbnail", str(out_path),
        f"--props={props}",
        cwd=str(_REMOTION_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Thumbnail render failed: {stderr.decode()}")
    return out_path
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
.venv/Scripts/pytest tests/seo/test_render.py -v
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/video/render.py tests/seo/test_render.py requirements.txt
git commit -m "feat(video): add async render_thumbnail helper wrapping remotion still"
```

---

## Task 9: Streamlit review UI with SEO panel  

**Files:**
- Create: `src/review/__init__.py`
- Create: `src/review/app.py`

This is the integration point. The app reads a pending video from the DB (or accepts manual input for testing), calls `generate_and_enrich`, and presents both the script and SEO panels. On Approve it writes all fields to DB.

- [ ] **Step 1: Create `src/review/__init__.py`**

Empty file:

```python
```

- [ ] **Step 2: Create `src/review/app.py`**

```python
from __future__ import annotations

import json

import streamlit as st

from src.db.database import get_conn, init_db, log_event
from src.seo import SeoMetadata, generate_and_enrich

st.set_page_config(page_title="Shorts Review", layout="wide", page_icon="🎬")
init_db()

st.title("Shorts Review")
st.caption("Review the script and SEO metadata before rendering.")

# ── Sidebar: video selection ──────────────────────────────────────────────────
with st.sidebar:
    st.header("Video")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT video_id, source_title, status FROM videos "
            "WHERE status IN ('script_drafted', 'script_approved', 'seo_generated') "
            "ORDER BY discovered_at DESC LIMIT 20"
        ).fetchall()

    if rows:
        options = {f"{r['video_id']} — {r['source_title'] or 'untitled'} [{r['status']}]": r['video_id']
                   for r in rows}
        selected_label = st.selectbox("Pending videos", list(options.keys()))
        video_id = options[selected_label]

        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM videos WHERE video_id=?", (video_id,)
            ).fetchone()

        script_value = ""
        if row and row["final_script_path"]:
            try:
                from pathlib import Path
                script_value = Path(row["final_script_path"]).read_text(encoding="utf-8")
            except Exception:
                pass

        topic_hint = (row["source_title"] or "") if row else ""
        language = (row["target_language"] or "english") if row else "english"
        styles_raw = row["styles_json"] if row else "[]"
        styles = json.loads(styles_raw) if styles_raw else ["documentary"]
    else:
        st.info("No pending videos. Use manual entry below.")
        video_id = st.text_input("Video ID (manual)")
        script_value = ""
        topic_hint = ""
        language = "english"
        styles = ["documentary"]

    st.divider()
    language = st.selectbox("Language override", ["english", "hindi"],
                            index=0 if language == "english" else 1)
    styles = st.multiselect(
        "Style override",
        ["documentary", "comedy", "serious", "storytelling", "explainer", "sarcastic"],
        default=styles,
    )

# ── Main: two-column layout ───────────────────────────────────────────────────
col_script, col_seo = st.columns([1, 1], gap="large")

with col_script:
    st.subheader("Script")
    script_text = st.text_area(
        "Edit script",
        value=script_value,
        height=400,
        label_visibility="collapsed",
    )

with col_seo:
    st.subheader("SEO Metadata")

    if st.button("Generate / Regenerate SEO", type="primary"):
        if not script_text.strip():
            st.error("Paste or load a script first.")
        else:
            with st.spinner("Analyzing script and fetching trending signals..."):
                try:
                    seo = generate_and_enrich(script_text, topic_hint, styles, language)
                    st.session_state["seo"] = seo
                    st.success("Done!")
                except Exception as exc:
                    st.error(f"SEO generation failed: {exc}")

    seo: SeoMetadata | None = st.session_state.get("seo")

    # Pre-fill from DB if already generated
    if seo is None and rows and row and row["seo_title"]:
        seo = SeoMetadata(
            title=row["seo_title"],
            description=row["seo_description"] or "",
            hashtags=json.loads(row["seo_hashtags_json"] or "[]"),
            thumbnail_phrases=json.loads(row["seo_thumbnail_phrases_json"] or '["","",""]'),
            niche="",
            thumbnail_phrase=row["seo_thumbnail_phrase"],
        )
        st.session_state["seo"] = seo

    if seo:
        title = st.text_input("Title", value=seo.title)
        char_count = len(title)
        st.caption(
            f"{'🔴' if char_count > 60 else '🟢'} {char_count}/60 chars"
        )

        description = st.text_area("Description", value=seo.description, height=150)

        hashtags_raw = st.text_area(
            "Hashtags (one per line)",
            value="\n".join(seo.hashtags),
            height=130,
        )
        hashtags = [t.strip() for t in hashtags_raw.splitlines() if t.strip()]

        thumbnail_phrase = st.radio(
            "Thumbnail phrase",
            options=seo.thumbnail_phrases,
            index=0,
        )
    else:
        st.info("Click **Generate / Regenerate SEO** to populate this panel.")

# ── Actions ───────────────────────────────────────────────────────────────────
st.divider()
btn_col1, btn_col2 = st.columns([1, 3])

with btn_col1:
    if st.button("Reject", type="secondary"):
        if video_id:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE videos SET status='failed', failure_reason='Rejected at review' "
                    "WHERE video_id=?",
                    (video_id,),
                )
            log_event(video_id, "review", "Video rejected by operator", level="warn")
            st.warning("Video rejected.")

with btn_col2:
    if st.button("Approve & Render", type="primary"):
        seo_data: SeoMetadata | None = st.session_state.get("seo")
        if not video_id:
            st.error("No video selected.")
        elif not seo_data:
            st.error("Generate SEO metadata first.")
        else:
            with get_conn() as conn:
                conn.execute(
                    """
                    UPDATE videos SET
                        seo_title=?, seo_description=?, seo_hashtags_json=?,
                        seo_thumbnail_phrases_json=?, seo_thumbnail_phrase=?,
                        status='seo_generated', updated_at=datetime('now')
                    WHERE video_id=?
                    """,
                    (
                        title,
                        description,
                        json.dumps(hashtags),
                        json.dumps(seo_data.thumbnail_phrases),
                        thumbnail_phrase,
                        video_id,
                    ),
                )
            log_event(video_id, "review", "SEO metadata approved. Render queued.")
            st.success(f"Approved! Video {video_id} queued for render.")
```

- [ ] **Step 3: Manually verify the UI**

```bash
cd D:/siddarth/youtube/shorts-bot
.venv/Scripts/streamlit run src/review/app.py
```

Open `http://localhost:8501` in a browser. Confirm:
1. Sidebar shows "No pending videos" (DB is empty — that's fine).
2. Manually enter any text in the script box and click **Generate / Regenerate SEO**. It will fail with an auth error (no `OPENROUTER_API_KEY` set yet) — that is expected and correct.
3. Confirm the title char counter appears, the hashtag text area is present, and the radio buttons for thumbnail phrase are visible once SEO is populated.
4. Stop with Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add src/review/__init__.py src/review/app.py
git commit -m "feat(review): add Streamlit review UI with script and SEO panels"
```

---

## Task 10: Wire OPENROUTER_API_KEY env var in config

**Files:**
- Modify: `config/config.example.yaml` (add a comment pointing to .env)

This task ensures the next developer knows which env var to set.

- [ ] **Step 1: Run the full test suite**

```bash
cd D:/siddarth/youtube/shorts-bot
.venv/Scripts/pytest tests/ -v
```

Expected: all tests pass. If `test_db_migration.py` was saved as `tests/seo/test_db_migration.py`, it should also run.

- [ ] **Step 2: Add .env documentation to config.example.yaml**

Open `config/config.example.yaml`. Append at the bottom:

```yaml
# ── Environment variables (set in .env, never commit) ─────────────────────────
# OPENROUTER_API_KEY=<your key from openrouter.ai>
# AI_MODEL=anthropic/claude-sonnet-4-6   # default; override to use a different model
```

- [ ] **Step 3: Final commit**

```bash
git add config/config.example.yaml
git commit -m "docs: document OPENROUTER_API_KEY and AI_MODEL env vars"
```

---

## Upload module integration note

The upload module (`src/upload/__init__.py`) is a stub. When it is implemented in Sprint 4, it must:

1. Read `seo_title`, `seo_description`, `seo_hashtags_json` from the `videos` DB row.
2. Fall back to `config.yaml`'s `upload.description_template` if any are `NULL`.
3. After calling `videos().insert()`, call `thumbnails().set()` with the file at `thumbnail_path`.

The DB columns and the `SeoMetadata` contract are stable — no changes needed to `src/seo/` when the upload module is built.
