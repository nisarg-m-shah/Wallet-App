"""pages/Transactions.py - Searchable, filterable transaction history with edit/delete/duplicate."""
from __future__ import annotations

import datetime as dt
import os

import streamlit as st

import services
from utils import format_currency, format_signed_currency, group_transactions_by_day, transaction_line_icon

st.set_page_config(page_title="Transactions | Wallet Tracker", page_icon="\U0001F4CB", layout="wide")

with open(os.path.join(os.path.dirname(__file__), "..", "assets", "style.css")) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

if "user" not in st.session_state:
    st.warning("Please log in from the Dashboard page first.")
    st.stop()

USER_ID = st.session_state.user["id"]

st.markdown("## \U0001F4CB Transactions")

accounts = services.get_accounts(USER_ID, include_system=False)
account_options = {f"{a['icon']} {a['name']}": a["id"] for a in accounts}
all_categories = services.get_categories(USER_ID)
category_options = {f"{c['icon']} {c['name']}": c["id"] for c in all_categories}

with st.expander("\U0001F50D Search & Filters", expanded=False):
    search = st.text_input("Search merchant, description, category, person, account, notes")
    c1, c2, c3 = st.columns(3)
    type_filter = c1.multiselect("Type", ["Expense", "Income", "Transfer", "Adjustment"])
    account_filter_labels = c2.multiselect("Account", list(account_options.keys()))
    category_filter_labels = c3.multiselect("Category", list(category_options.keys()))

    c4, c5, c6, c7 = st.columns(4)
    date_from = c4.date_input("From", value=None)
    date_to = c5.date_input("To", value=None)
    amount_min = c6.number_input("Min Amount", value=0.0, step=100.0)
    amount_max = c7.number_input("Max Amount", value=0.0, step=100.0)

df = services.get_transactions_df(
    USER_ID,
    search=search,
    type_filter=type_filter or None,
    account_filter=[account_options[a] for a in account_filter_labels] or None,
    category_filter=[category_options[c] for c in category_filter_labels] or None,
    date_from=date_from if date_from else None,
    date_to=date_to if date_to else None,
    amount_min=amount_min if amount_min > 0 else None,
    amount_max=amount_max if amount_max > 0 else None,
)

st.caption(f"{len(df)} transaction(s) found")

if df.empty:
    st.info("No transactions match your filters.")
else:
    for bucket, group in group_transactions_by_day(df):
        st.markdown(f"<div class='timeline-day-label'>{bucket}</div>", unsafe_allow_html=True)
        for _, row in group.iterrows():
            icon = transaction_line_icon(row)
            col_main, col_actions = st.columns([5, 1.3])

            if row["type"] == "Expense":
                amt_html = f"<span class='timeline-amount negative'>-{format_currency(row['amount'])}</span>"
                meta = f"{row['category']} \u2022 {row['account']} \u2022 {row['payment_mode']}"
            elif row["type"] == "Income":
                amt_html = f"<span class='timeline-amount positive'>+{format_currency(row['amount'])}</span>"
                meta = f"{row['category']} \u2022 {row['account']}"
            elif row["type"] == "Transfer":
                amt_html = f"<span class='timeline-amount'>{format_currency(row['amount'])}</span>"
                meta = f"{row['account']} \u2192 {row['to_account']}"
            else:
                cls = "positive" if row["amount"] >= 0 else "negative"
                amt_html = f"<span class='timeline-amount {cls}'>{format_signed_currency(row['amount'])}</span>"
                meta = f"Adjustment \u2022 {row['account']}"

            desc = row["description"] or row["type"]
            col_main.markdown(
                f"<div class='timeline-row'><div class='timeline-left'>"
                f"<div class='timeline-icon'>{icon}</div>"
                f"<div><div class='timeline-desc'>{desc}</div>"
                f"<div class='timeline-meta'>{meta} \u2022 {row['date'].strftime('%I:%M %p')}</div></div></div>"
                f"{amt_html}</div>",
                unsafe_allow_html=True,
            )

            with col_actions.popover("\u22EF", use_container_width=True):
                if row["type"] != "Adjustment" and st.button("\U0001F501 Duplicate", key=f"dup_{row['id']}", use_container_width=True):
                    ok, msg = services.duplicate_transaction(USER_ID, row["id"])
                    st.toast(msg, icon="\U00002705" if ok else "\U000026A0\U0000FE0F")
                    st.rerun()
                if st.button("\U0001F5D1\uFE0F Delete", key=f"del_{row['id']}", use_container_width=True):
                    ok, msg = services.delete_transaction(USER_ID, row["id"])
                    st.toast(msg, icon="\U00002705" if ok else "\U000026A0\U0000FE0F")
                    st.rerun()
