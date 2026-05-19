"""
dashboard/app.py
AutoAssign AI — Streamlit Dashboard (Phase 4)
Run: streamlit run dashboard/app.py

Install first: pip install streamlit
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import streamlit as st
except ImportError:
    print("Install streamlit first: pip install streamlit==1.37.0")
    sys.exit(1)

from core.config import cfg
from core.database import db
from agents.approval import approval_agent

cfg.load()

st.set_page_config(
    page_title="AutoAssign AI",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 AutoAssign AI — Dashboard")

# ── Stats row ─────────────────────────────────────────────────
stats = db.stats()
col1, col2, col3 = st.columns(3)
col1.metric("Total Assignments", stats["total"])
col2.metric("Submitted", stats["submitted"])
col3.metric("Pending", stats["pending"])

st.divider()

# ── Assignment table ──────────────────────────────────────────
st.subheader("📋 Assignments")
assignments = db.get_all(50)

if not assignments:
    st.info("No assignments detected yet. Start main.py to begin monitoring.")
else:
    for a in assignments:
        status_colors = {
            "submitted": "🟢",
            "error": "🔴",
            "skipped": "⚫",
            "notified": "🟡",
            "approved": "🔵",
            "detected": "⚪",
        }
        icon = status_colors.get(a["status"], "⚪")
        with st.expander(f"{icon} #{a['id']} — {a['title']} ({a['status']})"):
            col_a, col_b = st.columns(2)
            col_a.write(f"**Subject:** {a.get('subject', 'N/A')}")
            col_a.write(f"**Deadline:** {a.get('deadline', 'N/A')}")
            col_a.write(f"**Confidence:** {a.get('confidence', 0)}%")
            col_b.write(f"**Source:** {a.get('source', 'N/A')}")
            col_b.write(f"**Created:** {a.get('created_at', 'N/A')}")
            if a.get("drive_link"):
                col_b.markdown(f"[📄 View PDF]({a['drive_link']})")

            # Approve button
            if a["status"] == "notified":
                if st.button(f"✅ Approve & Submit #{a['id']}", key=f"approve_{a['id']}"):
                    approval_agent.approve_manually(a["id"])
                    st.success(f"Assignment #{a['id']} approved! Will submit on next tick.")
                    st.rerun()

            # Logs
            logs = db.get_logs(a["id"])
            if logs:
                st.write("**Timeline:**")
                for log in logs:
                    st.caption(f"`{log['created_at']}` — **{log['event']}** {log.get('detail', '')}")

st.divider()
st.caption(
    f"AutoAssign AI | User: {cfg.user_name} | "
    f"Active: {cfg.active_start}–{cfg.active_end} PKT"
)
