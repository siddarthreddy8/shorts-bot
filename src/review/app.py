from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from src.db.database import get_conn
from src.utils.config import project_root

st.set_page_config(
    page_title="Shorts Bot",
    page_icon="🎬",
    layout="wide",
)

_SCRIPTS_DIR = project_root() / "data" / "scripts"
_AUDIO_DIR   = project_root() / "remotion" / "public" / "audio"
_VIDEOS_DIR  = project_root() / "data" / "videos"

# ── pipeline stage order ──────────────────────────────────────────────────────
_STAGES = [
    ("discovered",      "🔍 Discovered"),
    ("transcribed",     "📝 Transcribed"),
    ("script_drafted",  "✍️  Drafted"),
    ("script_approved", "✅ Approved"),
    ("video_rendered",  "🎬 Rendered"),
    ("uploaded",        "🚀 Uploaded"),
]

_STATUS_COLOR = {
    "discovered":      "#4a90d9",
    "transcribed":     "#7b68ee",
    "script_drafted":  "#f0a500",
    "script_approved": "#2ecc71",
    "video_rendered":  "#1abc9c",
    "uploaded":        "#27ae60",
    "failed":          "#e74c3c",
    "skipped":         "#95a5a6",
}

# ── data helpers ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=10)
def _load_videos() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM videos ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@st.cache_data(ttl=10)
def _load_events(limit: int = 30) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT e.*, v.source_title FROM events e "
            "LEFT JOIN videos v ON e.video_id = v.video_id "
            "ORDER BY e.created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


@st.cache_data(ttl=30)
def _load_channels() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM channel_state").fetchall()
    return [dict(r) for r in rows]


def _stage_counts(videos: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for v in videos:
        s = v.get("status", "unknown")
        counts[s] = counts.get(s, 0) + 1
    return counts


def _estimate_costs(videos: list[dict]) -> dict:
    """Rough cost estimate from on-disk artefacts."""
    # OpenRouter — Gemini Flash 2.0: ~$0.10/1M input tokens, $0.40/1M output
    # A typical script generation uses ~800 input tokens + ~200 output tokens
    # ≈ $0.000080 + $0.000080 = ~$0.00016 per script
    scripts_generated = sum(
        1 for v in videos
        if v.get("status") in ("script_drafted", "script_approved", "video_rendered", "uploaded")
    )
    openrouter_cost = scripts_generated * 0.00016

    # ElevenLabs — Multilingual v2: $0.30 / 1000 chars
    tts_chars = 0
    for p in _AUDIO_DIR.glob("*_captions.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            tts_chars += sum(len(c["word"]) + 1 for c in data.get("captions", []))
        except Exception:
            pass
    elevenlabs_cost = tts_chars / 1000 * 0.30

    return {
        "openrouter": openrouter_cost,
        "elevenlabs": elevenlabs_cost,
        "total": openrouter_cost + elevenlabs_cost,
        "tts_chars": tts_chars,
        "scripts": scripts_generated,
    }


def _style_distribution(videos: list[dict]) -> dict[str, int]:
    dist: dict[str, int] = {}
    for v in videos:
        raw = v.get("styles_json")
        if raw:
            try:
                for s in json.loads(raw):
                    dist[s] = dist.get(s, 0) + 1
            except Exception:
                pass
    return dist


# ── pipeline actions ──────────────────────────────────────────────────────────

def _run_cmd(label: str, *args: str) -> None:
    with st.spinner(f"{label}…"):
        result = subprocess.run(
            [sys.executable, "-m", "src.main"] + list(args),
            cwd=str(project_root()),
            capture_output=True,
            text=True,
            timeout=300,
            encoding="utf-8",
            errors="replace",
        )
    if result.returncode == 0:
        st.success(f"{label} — done")
    else:
        st.error(f"{label} failed")
        st.code(result.stdout[-2000:] + result.stderr[-2000:])
    _load_videos.clear()
    _load_events.clear()
    st.rerun()


# ── layout ────────────────────────────────────────────────────────────────────

st.title("🎬 Shorts Bot")

# Refresh
col_title, col_refresh = st.columns([8, 1])
with col_refresh:
    if st.button("↺ Refresh", use_container_width=True):
        _load_videos.clear()
        _load_events.clear()
        _load_channels.clear()
        st.rerun()

videos   = _load_videos()
events   = _load_events()
channels = _load_channels()
counts   = _stage_counts(videos)
costs    = _estimate_costs(videos)

# ── metric cards ──────────────────────────────────────────────────────────────
st.divider()
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total videos",  len(videos))
m2.metric("Pending action", sum(counts.get(s, 0) for s in ("discovered", "transcribed", "script_approved")))
m3.metric("Drafts ready",  counts.get("script_drafted", 0))
m4.metric("Uploaded",      counts.get("uploaded", 0))
m5.metric("Failed",        counts.get("failed", 0))

# ── pipeline kanban ───────────────────────────────────────────────────────────
st.divider()
st.subheader("Pipeline")

cols = st.columns(len(_STAGES))
for col, (status, label) in zip(cols, _STAGES):
    n = counts.get(status, 0)
    col.markdown(f"**{label}**")
    clr = _STATUS_COLOR.get(status, "#888")
    col.markdown(
        f"<div style='font-size:2rem;font-weight:900;color:{clr}'>{n}</div>",
        unsafe_allow_html=True,
    )
    # Action button per stage
    if status == "discovered" and n:
        if col.button("▶ Transcribe all", key="btn_transcribe", use_container_width=True):
            for v in videos:
                if v["status"] == "discovered" and v.get("source_url"):
                    _run_cmd(f"Transcribe {v['video_id']}", "transcribe", v["video_id"], v["source_url"])
    elif status == "transcribed" and n:
        if col.button("▶ Generate scripts", key="btn_generate", use_container_width=True):
            for v in videos:
                if v["status"] == "transcribed":
                    _run_cmd(f"Script {v['video_id']}", "generate-script", v["video_id"])
    elif status == "script_drafted" and n:
        col.page_link("pages/2_Script_Review.py", label="✏️ Open Review UI", use_container_width=True)
    elif status == "script_approved" and n:
        if col.button("▶ Render all", key="btn_render", use_container_width=True):
            for v in videos:
                if v["status"] == "script_approved":
                    _run_cmd(f"Render {v['video_id']}", "render", v["video_id"])
    elif status == "video_rendered" and n:
        if col.button("▶ Upload all", key="btn_upload", use_container_width=True):
            for v in videos:
                if v["status"] == "video_rendered":
                    _run_cmd(f"Upload {v['video_id']}", "upload", v["video_id"])

# ── Monitor button ────────────────────────────────────────────────────────────
st.divider()
c1, c2, _ = st.columns([2, 2, 7])
if c1.button("🔍 Poll channels for new videos", use_container_width=True):
    _run_cmd("Poll channels", "monitor")
if c2.button("▶ Run full pipeline", use_container_width=True):
    _run_cmd("Full pipeline run", "run")

# ── activity log + channel health ─────────────────────────────────────────────
st.divider()
col_act, col_ch = st.columns([3, 2])

with col_act:
    st.subheader("Recent Activity")
    if not events:
        st.caption("No events yet.")
    for ev in events[:20]:
        icon = "✅" if ev.get("level") == "info" else "⚠️" if ev.get("level") == "warn" else "❌"
        title = (ev.get("source_title") or ev.get("video_id") or "")[:30]
        st.markdown(
            f"{icon} **{ev.get('stage','?')}** — {ev.get('message','')}  "
            f"<small style='color:#888'>{title} · {(ev.get('created_at') or '')[:16]}</small>",
            unsafe_allow_html=True,
        )

with col_ch:
    st.subheader("Channel Health")
    if not channels:
        st.caption("No channels polled yet. Run Monitor.")
    for ch in channels:
        polled = (ch.get("last_polled_at") or "never")[:16]
        seen   = ch.get("last_seen_video_id") or "—"
        st.markdown(f"**{ch['channel_id'][:20]}…**")
        st.caption(f"Last polled: {polled}")
        st.caption(f"Last video:  {seen}")
        st.markdown("---")

# ── cost + style distribution ─────────────────────────────────────────────────
st.divider()
col_cost, col_style = st.columns(2)

with col_cost:
    st.subheader("Estimated Costs")
    st.metric("OpenRouter (AI scripts)", f"${costs['openrouter']:.4f}",
              help=f"{costs['scripts']} scripts × ~$0.00016")
    st.metric("ElevenLabs (TTS audio)", f"${costs['elevenlabs']:.4f}",
              help=f"{costs['tts_chars']:,} chars × $0.30/1K")
    st.metric("Total", f"${costs['total']:.4f}")
    st.caption("Estimates only — actual usage may vary.")

with col_style:
    st.subheader("Style Distribution")
    dist = _style_distribution(videos)
    if dist:
        for style, count in sorted(dist.items(), key=lambda x: -x[1]):
            st.markdown(f"**{style}** — {count}")
            st.progress(count / max(dist.values()))
    else:
        st.caption("No scripts generated yet.")

# ── videos table ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("All Videos")

if not videos:
    st.info("No videos in the pipeline yet. Click 'Poll channels' to start.")
else:
    for v in videos:
        status = v.get("status", "unknown")
        color = _STATUS_COLOR.get(status, "#888")
        with st.expander(
            f"{v.get('source_title') or v['video_id']}  "
            f"[{v.get('source_channel_name') or ''}]",
            expanded=False,
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.markdown(
                f"<span style='color:{color};font-weight:bold'>{status}</span>",
                unsafe_allow_html=True,
            )
            c2.caption(f"ID: {v['video_id']}")
            c3.caption(f"Lang: {v.get('target_language') or '—'}")
            c4.caption(f"Words: {v.get('script_word_count') or '—'}")
            if v.get("source_url"):
                st.markdown(f"[Source ↗]({v['source_url']})")
            if v.get("youtube_url"):
                st.markdown(f"[YouTube Short ↗]({v['youtube_url']})")
            st.caption(f"Updated: {(v.get('updated_at') or '')[:16]}")
