"""views/settings.py - Manage categories and view account/profile info."""
from __future__ import annotations

import streamlit as st

import services
from database import DB_BACKEND
from utils import ACCOUNT_ICONS


def render(user_id: int, user: dict) -> None:
    st.markdown("## \U00002699\U0000FE0F Settings")

    st.markdown("### Profile")
    st.write(f"**Name:** {user['display_name']}")
    st.write(f"**Email:** {user['email']}")

    st.divider()
    st.markdown("### Storage")
    if DB_BACKEND == "postgres":
        st.success("Connected to Postgres - your data persists across app reboots/redeploys.")
    else:
        st.error(
            "\U000026A0\U0000FE0F Running on local SQLite, NOT Postgres. "
            "On Streamlit Community Cloud this file is wiped every time the app "
            "goes to sleep and reboots. Go to your app -> Settings -> Secrets on "
            "Streamlit Cloud and confirm `DATABASE_URL` is saved there."
        )

    st.divider()
    st.markdown("### Categories")

    tab_exp, tab_inc = st.tabs(["Expense", "Income"])

    with tab_exp:
        cats = services.get_categories(user_id, kind="Expense")
        cols = st.columns(2)
        for i, c in enumerate(cats):
            cols[i % 2].markdown(f"{c['icon']} {c['name']}")

        with st.form("new_expense_cat"):
            name = st.text_input("New category name", key="exp_cat_name")
            icon = st.selectbox("Icon", ACCOUNT_ICONS, key="exp_cat_icon")
            if st.form_submit_button("Add Category", use_container_width=True):
                ok, msg = services.create_category(user_id, name, "Expense", icon)
                st.toast(msg, icon="\U00002705" if ok else "\U000026A0\U0000FE0F")
                if ok:
                    st.rerun()

    with tab_inc:
        cats = services.get_categories(user_id, kind="Income")
        cols = st.columns(2)
        for i, c in enumerate(cats):
            cols[i % 2].markdown(f"{c['icon']} {c['name']}")

        with st.form("new_income_cat"):
            name = st.text_input("New category name", key="inc_cat_name")
            icon = st.selectbox("Icon", ACCOUNT_ICONS, key="inc_cat_icon")
            if st.form_submit_button("Add Category", use_container_width=True):
                ok, msg = services.create_category(user_id, name, "Income", icon)
                st.toast(msg, icon="\U00002705" if ok else "\U000026A0\U0000FE0F")
                if ok:
                    st.rerun()

    st.divider()
    st.markdown("### Data Export")
    df = services.get_transactions_df(user_id)
    if not df.empty:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("\U0001F4E5 Export Transactions (CSV)", csv, "transactions.csv", "text/csv", use_container_width=True)
    else:
        st.caption("No transactions to export yet.")

    st.divider()
    if st.button("Log Out", use_container_width=True):
        st.session_state.logout_requested = True
        st.rerun()