"""views/accounts.py - Manage accounts: view balances, create, edit, archive."""
from __future__ import annotations

import streamlit as st

import services
from utils import ACCOUNT_COLORS, ACCOUNT_ICONS, format_currency


def render(user_id: int) -> None:
    st.markdown("## \U0001F3E6 Accounts")

    accounts = services.get_accounts(user_id, include_system=False)

    cols = st.columns(2)
    for i, acc in enumerate(accounts):
        with cols[i % 2]:
            st.markdown(
                f"<div class='metric-card' style='border-left:5px solid {acc['color']};'>"
                f"<div style='font-size:26px;'>{acc['icon']}</div>"
                f"<div class='metric-label'>{acc['type']}</div>"
                f"<div class='metric-value' style='font-size:17px;'>{acc['name']}</div>"
                f"<div style='font-size:19px;font-weight:800;margin-top:6px;'>{format_currency(acc['balance'], acc['currency'])}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            with st.expander("Edit"):
                new_name = st.text_input("Name", value=acc["name"], key=f"name_{acc['id']}")
                new_notes = st.text_area("Notes", value=acc["notes"], key=f"notes_{acc['id']}")
                c1, c2 = st.columns(2)
                if c1.button("Save", key=f"save_{acc['id']}", use_container_width=True):
                    services.update_account(user_id, acc["id"], name=new_name, notes=new_notes)
                    st.toast("Account updated.", icon="\U00002705")
                    st.rerun()
                if c2.button("Archive", key=f"archive_{acc['id']}", use_container_width=True):
                    services.archive_account(user_id, acc["id"])
                    st.toast("Account archived.", icon="\U0001F4E6")
                    st.rerun()
            st.write("")

    st.divider()
    st.markdown("### \u2795 Add New Account")

    with st.form("new_account_form"):
        name = st.text_input("Account Name")
        acc_type = st.selectbox("Type", [
            "Cash", "Savings Account", "Current Account", "Credit Card",
            "Investment", "Wallet", "Liability",
        ])
        c3, c4 = st.columns(2)
        balance = c3.number_input("Opening Balance", step=100.0, format="%.2f")
        currency = c4.selectbox("Currency", ["INR", "USD", "EUR", "GBP"])
        c5, c6 = st.columns(2)
        color = c5.selectbox("Color", ACCOUNT_COLORS)
        icon = c6.selectbox("Icon", ACCOUNT_ICONS)
        notes = st.text_area("Notes", placeholder="Optional")

        submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)
        if submitted:
            ok, msg = services.create_account(user_id, name, acc_type, balance, currency, color, icon, notes)
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

    st.divider()
    with st.expander("\U0001F4E6 Archived Accounts"):
        archived = [a for a in services.get_accounts(user_id, include_system=False, include_archived=True) if a["is_archived"]]
        if not archived:
            st.caption("No archived accounts.")
        for a in archived:
            st.write(f"{a['icon']} {a['name']} — {format_currency(a['balance'], a['currency'])}")
