"""views/recurring.py - View and manage scheduled automatic payments."""
from __future__ import annotations

import streamlit as st

import services
from utils import format_currency


def render(user_id: int) -> None:
    st.markdown("## \U0001F501 Automatic Payments")
    st.caption("Yeah gurl go get that Netflix subscription.")

    generated = services.process_due_recurring_payments(user_id)
    if generated:
        st.toast(f"Generated {generated} transaction(s) for due payments.", icon="\U0001F501")

    payments = services.get_recurring_payments(user_id, active_only=False)

    if not payments:
        st.info("No automatic payments scheduled yet. Add one from the Dashboard's Quick Add.")
        return

    for p in payments:
        status = "\U0001F7E2 Active" if p["is_active"] else "\u26AA Paused"
        st.markdown(
            f"<div class='metric-card'>"
            f"<div class='metric-value' style='font-size:16px;'>{p['description']}</div>"
            f"<div class='metric-sub'>{p['category']} \u2022 {p['account']} \u2022 {p['frequency']} \u2022 {status}</div>"
            f"<div style='font-size:20px;font-weight:800;margin-top:6px;'>{format_currency(p['amount'])}</div>"
            f"<div class='metric-sub'>Next due: {p['next_due_date'].strftime('%d %b %Y')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        toggle_label = "Pause" if p["is_active"] else "Resume"
        if st.button(toggle_label, key=f"toggle_{p['id']}", use_container_width=True):
            services.toggle_recurring_payment(user_id, p["id"], not p["is_active"])
            st.rerun()
        st.write("")
