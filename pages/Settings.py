"""pages/Settings.py - Manage categories and view account/profile info."""
from __future__ import annotations

import os

import streamlit as st

import services
from utils import ACCOUNT_ICONS

st.set_page_config(page_title="Settings | Wallet Tracker", page_icon="\U00002699\U0000FE0F", layout="wide")

with open(os.path.join(os.path.dirname(__file__), "..", "assets", "style.css")) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

if "user" not in st.session_state:
    st.warning("Please log in from the Dashboard page first.")
    st.stop()

USER = st.session_state.user
USER_ID = USER["id"]

st.markdown("## \U00002699\U0000FE0F Settings")

st.markdown("### Profile")
st.write(f"**Name:** {USER['display_name']}")
st.write(f"**Email:** {USER['email']}")

st.divider()
st.markdown("### Categories")

tab_exp, tab_inc = st.tabs(["Expense Categories", "Income Categories"])

with tab_exp:
    cats = services.get_categories(USER_ID, kind="Expense")
    cols = st.columns(4)
    for i, c in enumerate(cats):
        cols[i % 4].markdown(f"{c['icon']} {c['name']}")

    with st.form("new_expense_cat"):
        c1, c2 = st.columns([3, 1])
        name = c1.text_input("New category name", key="exp_cat_name")
        icon = c2.selectbox("Icon", ACCOUNT_ICONS, key="exp_cat_icon")
        if st.form_submit_button("Add Category"):
            ok, msg = services.create_category(USER_ID, name, "Expense", icon)
            st.toast(msg, icon="\U00002705" if ok else "\U000026A0\U0000FE0F")
            if ok:
                st.rerun()

with tab_inc:
    cats = services.get_categories(USER_ID, kind="Income")
    cols = st.columns(4)
    for i, c in enumerate(cats):
        cols[i % 4].markdown(f"{c['icon']} {c['name']}")

    with st.form("new_income_cat"):
        c1, c2 = st.columns([3, 1])
        name = c1.text_input("New category name", key="inc_cat_name")
        icon = c2.selectbox("Icon", ACCOUNT_ICONS, key="inc_cat_icon")
        if st.form_submit_button("Add Category"):
            ok, msg = services.create_category(USER_ID, name, "Income", icon)
            st.toast(msg, icon="\U00002705" if ok else "\U000026A0\U0000FE0F")
            if ok:
                st.rerun()

st.divider()
st.markdown("### Data Export")
df = services.get_transactions_df(USER_ID)
if not df.empty:
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("\U0001F4E5 Export Transactions (CSV)", csv, "transactions.csv", "text/csv")
else:
    st.caption("No transactions to export yet.")
