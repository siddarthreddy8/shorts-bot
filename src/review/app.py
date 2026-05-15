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
