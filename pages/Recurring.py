"""pages/Recurring.py - View and manage scheduled automatic payments."""
from __future__ import annotations

import os

import streamlit as st

import services
from utils import format_currency

st.set_page_config(page_title="Recurring | Wallet Tracker", page_icon="\U0001F501", layout="wide")

with open(os.path.join(os.path.dirname(__file__), "..", "assets", "style.css")) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

if "user" not in st.session_state:
    st.warning("Please log in from the Dashboard page first.")
    st.stop()

USER_ID = st.session_state.user["id"]

st.markdown("## \U0001F501 Automatic Payments")
st.caption("Yeah gurl go get that Netflix subscription.")

generated = services.process_due_recurring_payments(USER_ID)
if generated:
    st.toast(f"Generated {generated} transaction(s) for due payments.", icon="\U0001F501")

payments = services.get_recurring_payments(USER_ID, active_only=False)

if not payments:
    st.info("No automatic payments scheduled yet. Add one from the Dashboard's Quick Add.")
else:
    for p in payments:
        col1, col2, col3 = st.columns([4, 1.5, 1.5])
        status = "\U0001F7E2 Active" if p["is_active"] else "\u26AA Paused"
        col1.markdown(
            f"<div class='metric-card'>"
            f"<div class='metric-value' style='font-size:16px;'>{p['description']}</div>"
            f"<div class='metric-sub'>{p['category']} \u2022 {p['account']} \u2022 {p['frequency']} \u2022 {status}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        col2.metric("Amount", format_currency(p["amount"]))
        col3.write("")
        col3.write("")
        toggle_label = "Pause" if p["is_active"] else "Resume"
        if col3.button(toggle_label, key=f"toggle_{p['id']}", use_container_width=True):
            services.toggle_recurring_payment(USER_ID, p["id"], not p["is_active"])
            st.rerun()
        st.caption(f"Next due: {p['next_due_date'].strftime('%d %b %Y')}")
        st.divider()
