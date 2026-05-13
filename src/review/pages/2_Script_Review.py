from __future__ import annotations

import json
import sys
from pathlib import Path

# pages/ is one level deeper than app.py, so go up 4 levels to project root
_ROOT = Path(__file__).parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from src.db.database import get_conn, log_event
from src.utils.config import project_root

_SCRIPTS_DIR = project_root() / "data" / "scripts"
_TRANSCRIPTS_DIR = project_root() / "data" / "transcripts"




# ── helpers ──────────────────────────────────────────────────────────────────

def _load_videos() -> list[dict]:
    """All videos that have a draft script on disk."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT video_id, source_title, source_url, source_channel_name,
                      status, transcript_path, target_language, styles_json
               FROM videos
               ORDER BY updated_at DESC"""
        ).fetchall()
    result = []
    for row in rows:
        if (_SCRIPTS_DIR / f"{row['video_id']}_draft.json").exists():
            result.append(dict(row))
    return result


def _load_draft(video_id: str) -> dict | None:
    p = _SCRIPTS_DIR / f"{video_id}_draft.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _load_transcript(path: str | None) -> str:
    if path and Path(path).exists():
        return Path(path).read_text(encoding="utf-8")
    return ""


def _approve(video_id: str, hook: str, body: str, cta: str) -> Path:
    from src.script.rewriter import save_approved
    approved_path = save_approved(video_id, hook, body, cta)
    wc = len(f"{hook}\n\n{body}\n\n{cta}".split())
    with get_conn() as conn:
        conn.execute(
            "UPDATE videos SET status='script_approved', final_script_path=?, "
            "script_word_count=?, updated_at=datetime('now') WHERE video_id=?",
            (str(approved_path), wc, video_id),
        )
    log_event(video_id, "review", f"Script approved ({wc} words)")
    return approved_path


def _delete_draft(video_id: str) -> None:
    p = _SCRIPTS_DIR / f"{video_id}_draft.json"
    if p.exists():
        p.unlink()


# ── page ─────────────────────────────────────────────────────────────────────

st.title("🎬 Shorts Bot — Script Review")

videos = _load_videos()

if not videos:
    st.info("No draft scripts found. Run `python -m src.main generate-script <video_id>` first.")
    st.stop()

# ── sidebar: video picker ─────────────────────────────────────────────────────

with st.sidebar:
    st.header("Videos")
    labels = [
        f"{v['source_title'][:40] if v['source_title'] else v['video_id']}  [{v['status']}]"
        for v in videos
    ]
    idx = st.radio("Select", range(len(videos)), format_func=lambda i: labels[i])
    video = videos[idx]

video_id = video["video_id"]
draft = _load_draft(video_id)

if draft is None:
    st.error("Draft JSON not found on disk.")
    st.stop()

# ── header ────────────────────────────────────────────────────────────────────

st.subheader(video.get("source_title") or video_id)
c1, c2, c3 = st.columns(3)
c1.caption(f"Channel: {video.get('source_channel_name') or '—'}")
c2.caption(f"Language: {draft.get('language', 'english').title()}")
c3.caption(f"Styles: {', '.join(draft.get('styles', []))}")
if video.get("source_url"):
    st.markdown(f"[Watch source ↗]({video['source_url']})")

if video.get("status") == "script_approved":
    st.success("✓ Script previously approved — you can re-approve after editing.")

st.divider()

# ── hook picker ───────────────────────────────────────────────────────────────

hooks: list[str] = draft.get("hooks", [""])
st.subheader("Hook  *(pick one)*")
hook_idx = st.radio(
    "hook",
    range(len(hooks)),
    format_func=lambda i: hooks[i],
    label_visibility="collapsed",
)
selected_hook = hooks[hook_idx]

st.divider()

# ── body editor ───────────────────────────────────────────────────────────────

st.subheader("Body")
body = st.text_area("body", value=draft.get("body", ""), height=220, label_visibility="collapsed")

# ── CTA ───────────────────────────────────────────────────────────────────────

st.subheader("CTA")
cta = st.text_input(
    "cta",
    value=draft.get("cta", "Watch the full video — link in description."),
    label_visibility="collapsed",
)

# ── live word count ───────────────────────────────────────────────────────────

wc = len(f"{selected_hook} {body} {cta}".split())
ok = 90 <= wc <= 180
st.markdown(
    f"**Word count:** {'🟢' if ok else '🔴'} **{wc}**"
    + (f"  *(target: 90–180)*" if not ok else "  ✓")
)

st.divider()

# ── preview + transcript ──────────────────────────────────────────────────────

with st.expander("Full script preview"):
    st.markdown(f"{selected_hook}\n\n{body}\n\n*{cta}*")

transcript_text = _load_transcript(video.get("transcript_path"))
if transcript_text:
    with st.expander("Original Telugu transcript"):
        st.text(transcript_text[:4000] + ("…" if len(transcript_text) > 4000 else ""))

st.divider()

# ── action buttons ────────────────────────────────────────────────────────────

col_approve, col_regen, _ = st.columns([2, 2, 5])

if col_approve.button("✅  Approve Script", type="primary", use_container_width=True):
    path = _approve(video_id, selected_hook, body, cta)
    st.success(f"Approved! Saved to `{path.name}`")
    st.balloons()
    st.rerun()

if col_regen.button("🔄  Regenerate", use_container_width=True):
    _delete_draft(video_id)
    transcript = _load_transcript(video.get("transcript_path"))
    if not transcript:
        st.error("No transcript found — cannot regenerate.")
    else:
        with st.spinner("Generating new script…"):
            from src.script.rewriter import generate
            generate(
                video_id,
                transcript,
                language=draft.get("language", "english"),
                styles=draft.get("styles", ["documentary"]),
            )
        st.rerun()
