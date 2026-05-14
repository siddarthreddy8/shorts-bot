from __future__ import annotations

import json
import sys
from pathlib import Path

# pages/ is one level deeper than app.py, so go up 4 levels to project root
_ROOT = Path(__file__).parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from src.db.database import get_conn
from src.utils.config import project_root

_STORYBOARDS_DIR = project_root() / "data" / "storyboards"
_SCENES_DIR = project_root() / "remotion" / "public" / "scenes"


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_videos() -> list[dict]:
    """Videos that have an approved script (ready for storyboarding or beyond)."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT video_id, source_title, source_channel_name, status
               FROM videos
               WHERE status IN ('script_approved','video_rendered','uploaded')
               ORDER BY updated_at DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


def _load_storyboard(video_id: str) -> dict | None:
    p = _STORYBOARDS_DIR / f"{video_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _save_storyboard(data: dict) -> None:
    p = _STORYBOARDS_DIR / f"{data['video_id']}.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _ms_to_ts(ms: int) -> str:
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


# ── page ──────────────────────────────────────────────────────────────────────

st.title("🎬 Shorts Bot — Storyboard Review")

videos = _load_videos()

if not videos:
    st.info(
        "No approved scripts yet. "
        "Approve a script in **Script Review** first."
    )
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
st.subheader(video.get("source_title") or video_id)
st.caption(f"Channel: {video.get('source_channel_name') or '—'}")
st.divider()

storyboard = _load_storyboard(video_id)

# ── No plan yet ───────────────────────────────────────────────────────────────

if storyboard is None:
    st.info("No scene plan yet for this video.")
    if st.button("🗺️  Plan Scenes", type="primary"):
        with st.spinner("Planning scenes via LLM…"):
            from src.storyboard.generator import plan_only
            plan_only(video_id, regenerate=True)
        st.rerun()
    st.stop()

status = storyboard.get("status", "planned")
scenes: list[dict] = storyboard["scenes"]
duration_ms: int = storyboard.get("duration_ms", 0)

# ── Status badge ──────────────────────────────────────────────────────────────

col_status, col_replan = st.columns([3, 1])
with col_status:
    if status == "generated":
        st.success(f"✓ Visuals generated — {len(scenes)} scenes")
    else:
        st.warning(f"Plan ready — {len(scenes)} scenes. Edit prompts, then generate.")

with col_replan:
    if st.button("↺  Re-plan", help="Discard current plan and generate a new one from the LLM"):
        with st.spinner("Re-planning…"):
            from src.storyboard.generator import plan_only
            plan_only(video_id, regenerate=True)
        st.rerun()

st.divider()

# ── Scene editor ──────────────────────────────────────────────────────────────

st.subheader("Visual Scenes")
st.caption(
    "Edit any prompt before generating. "
    "Motion type controls the Ken Burns effect (images only — video clips have their own motion)."
)

MOTION_OPTIONS = ["zoom_in", "zoom_out", "pan_left", "pan_right", "static"]

edited_scenes: list[dict] = []
for i, scene in enumerate(scenes):
    start_ts = _ms_to_ts(scene["start_ms"])
    end_ts = _ms_to_ts(scene["end_ms"])
    dur_s = (scene["end_ms"] - scene["start_ms"]) / 1000

    asset_badge = ""
    if "video_path" in scene:
        asset_badge = " 🎬"
    elif "image_path" in scene:
        asset_badge = " 🖼️"

    with st.expander(
        f"Scene {i + 1}  {start_ts} → {end_ts}  ({dur_s:.1f}s){asset_badge}",
        expanded=(status == "planned"),
    ):
        col_prompt, col_motion = st.columns([4, 1])

        with col_prompt:
            new_prompt = st.text_area(
                "Prompt",
                value=scene["prompt"],
                height=100,
                key=f"prompt_{i}",
                label_visibility="collapsed",
            )

        with col_motion:
            motion_idx = MOTION_OPTIONS.index(scene.get("motion", "zoom_in"))
            new_motion = st.selectbox(
                "Motion",
                MOTION_OPTIONS,
                index=motion_idx,
                key=f"motion_{i}",
            )

        # Show generated asset if available
        if "video_path" in scene:
            video_file = _SCENES_DIR / video_id / f"{i:02d}.mp4"
            if video_file.exists():
                st.video(str(video_file))
        elif "image_path" in scene:
            img_file = _SCENES_DIR / video_id / f"{i:02d}.png"
            if img_file.exists():
                st.image(str(img_file), use_container_width=True)

        edited_scenes.append({
            **scene,
            "prompt": new_prompt,
            "motion": new_motion,
        })

st.divider()

# ── Action buttons ────────────────────────────────────────────────────────────

col_save, col_gen, col_regen, _ = st.columns([2, 2, 2, 3])

if col_save.button("💾  Save Prompts", use_container_width=True):
    storyboard["scenes"] = edited_scenes
    _save_storyboard(storyboard)
    st.success("Prompts saved.")
    st.rerun()

if col_gen.button(
    "🚀  Generate Visuals",
    type="primary",
    use_container_width=True,
    disabled=(status == "generated"),
    help="Submit all scenes to FAL in parallel, wait for results, download clips.",
):
    # Save any edits first
    storyboard["scenes"] = edited_scenes
    _save_storyboard(storyboard)

    with st.spinner(
        f"Generating {len(edited_scenes)} video clips via FAL… "
        "This takes ~5–10 min. Check the terminal for live progress."
    ):
        from src.storyboard.generator import generate_visuals
        generate_visuals(video_id)
    st.success("Visuals generated!")
    st.rerun()

if col_regen.button(
    "🔄  Re-generate All",
    use_container_width=True,
    help="Re-submit all scenes even if clips already exist.",
):
    storyboard["scenes"] = edited_scenes
    _save_storyboard(storyboard)

    with st.spinner("Re-generating all clips…"):
        from src.storyboard.generator import generate_visuals
        generate_visuals(video_id, regenerate=True)
    st.success("Re-generation complete!")
    st.rerun()
