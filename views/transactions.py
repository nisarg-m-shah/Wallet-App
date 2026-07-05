"""views/transactions.py - Searchable, filterable transaction history with edit/delete/duplicate."""
from __future__ import annotations

import datetime as dt

import streamlit as st

import services
from utils import (
    DEFAULT_PAYERS,
    PAYMENT_MODES,
    format_currency,
    format_signed_currency,
    group_transactions_by_day,
    now_ist,
    transaction_line_icon,
)


@st.dialog("\U0000270F\uFE0F Edit Transaction")
def edit_transaction_dialog(user_id: int, row: dict) -> None:
    accounts = services.get_accounts(user_id, include_system=False)
    account_options = {f"{a['icon']} {a['name']}": a["id"] for a in accounts}
    account_labels = list(account_options.keys())

    def _label_for_account_id(acc_id):
        for label, aid in account_options.items():
            if aid == acc_id:
                return label
        return account_labels[0] if account_labels else None

    if row["type"] == "Adjustment":
        st.info(
            "Balance adjustments can't be edited directly since they act as a "
            "checkpoint for every other balance calculation. Delete this one "
            "and create a fresh adjustment instead."
        )
        return

    if row["type"] == "Expense":
        cats = services.get_categories(user_id, kind="Expense")
        cat_options = {f"{c['icon']} {c['name']}": c["id"] for c in cats}
        cat_labels = list(cat_options.keys())
        current_cat_label = next((lbl for lbl, cid in cat_options.items()
                                   if cid == next((c["id"] for c in cats if c["name"] == row["category"]), None)), cat_labels[0] if cat_labels else None)

        amount = st.number_input("Amount", min_value=0.0, step=50.0, format="%.2f", value=float(row["amount"]), key="edit_amt")
        description = st.text_input("Description", value=row["description"], key="edit_desc")
        category_label = st.selectbox("Category", cat_labels, index=cat_labels.index(current_cat_label) if current_cat_label in cat_labels else 0, key="edit_cat")
        c1, c2 = st.columns(2)
        date = c1.date_input("Date", value=row["date"].date(), key="edit_date")
        time = c2.time_input("Time", value=row["date"].time(), key="edit_time")
        mode_idx = PAYMENT_MODES.index(row["payment_mode"]) if row["payment_mode"] in PAYMENT_MODES else 0
        payment_mode = st.selectbox("Payment Mode", PAYMENT_MODES, index=mode_idx, key="edit_mode")
        acc_label_default = _label_for_account_id(row["account_id"])
        account_label = st.selectbox("Account", account_labels,
                                      index=account_labels.index(acc_label_default) if acc_label_default in account_labels else 0,
                                      key="edit_acc")
        payee = st.text_input("Payee", value=row["payee"] or "", key="edit_payee")

        if st.button("Save Changes", type="primary", use_container_width=True, key="edit_save"):
            ok, msg = services.update_transaction(
                user_id, row["id"], type="Expense", amount=amount, description=description,
                category_id=cat_options[category_label], date=dt.datetime.combine(date, time),
                payment_mode=payment_mode, account_id=account_options[account_label], payee=payee,
            )
            if ok:
                st.toast("Transaction updated.", icon="\U00002705")
                st.rerun()
            else:
                st.error(msg)

    elif row["type"] == "Income":
        cats = services.get_categories(user_id, kind="Income")
        cat_options = {f"{c['icon']} {c['name']}": c["id"] for c in cats}
        cat_labels = list(cat_options.keys())
        current_cat_label = next((lbl for lbl, cid in cat_options.items()
                                   if cid == next((c["id"] for c in cats if c["name"] == row["category"]), None)), cat_labels[0] if cat_labels else None)

        amount = st.number_input("Amount", min_value=0.0, step=50.0, format="%.2f", value=float(row["amount"]), key="edit_inc_amt")
        description = st.text_input("Description", value=row["description"], key="edit_inc_desc")
        payer = st.text_input("Payer", value=row["payee"] or "", key="edit_inc_payer")
        category_label = st.selectbox("Category", cat_labels, index=cat_labels.index(current_cat_label) if current_cat_label in cat_labels else 0, key="edit_inc_cat")
        mode_idx = PAYMENT_MODES.index(row["payment_mode"]) if row["payment_mode"] in PAYMENT_MODES else 0
        payment_mode = st.selectbox("Payment Mode", PAYMENT_MODES, index=mode_idx, key="edit_inc_mode")
        c1, c2 = st.columns(2)
        date = c1.date_input("Date", value=row["date"].date(), key="edit_inc_date")
        time = c2.time_input("Time", value=row["date"].time(), key="edit_inc_time")
        acc_label_default = _label_for_account_id(row["account_id"])
        account_label = st.selectbox("Account", account_labels,
                                      index=account_labels.index(acc_label_default) if acc_label_default in account_labels else 0,
                                      key="edit_inc_acc")

        if st.button("Save Changes", type="primary", use_container_width=True, key="edit_inc_save"):
            ok, msg = services.update_transaction(
                user_id, row["id"], type="Income", amount=amount, description=description,
                payee=payer, category_id=cat_options[category_label], payment_mode=payment_mode,
                date=dt.datetime.combine(date, time), account_id=account_options[account_label],
            )
            if ok:
                st.toast("Transaction updated.", icon="\U00002705")
                st.rerun()
            else:
                st.error(msg)

    elif row["type"] == "Transfer":
        amount = st.number_input("Amount", min_value=0.0, step=50.0, format="%.2f", value=float(row["amount"]), key="edit_tr_amt")
        from_default = _label_for_account_id(row["account_id"])
        to_default = _label_for_account_id(row["to_account_id"])
        from_label = st.selectbox("From Account", account_labels,
                                   index=account_labels.index(from_default) if from_default in account_labels else 0,
                                   key="edit_tr_from")
        to_label = st.selectbox("To Account", account_labels,
                                 index=account_labels.index(to_default) if to_default in account_labels else 0,
                                 key="edit_tr_to")
        c1, c2 = st.columns(2)
        date = c1.date_input("Date", value=row["date"].date(), key="edit_tr_date")
        time = c2.time_input("Time", value=row["date"].time(), key="edit_tr_time")
        notes = st.text_input("Notes", value=row["notes"] or "", key="edit_tr_notes")

        if st.button("Save Changes", type="primary", use_container_width=True, key="edit_tr_save"):
            ok, msg = services.update_transaction(
                user_id, row["id"], type="Transfer", amount=amount,
                account_id=account_options[from_label], to_account_id=account_options[to_label],
                date=dt.datetime.combine(date, time), notes=notes,
            )
            if ok:
                st.toast("Transaction updated.", icon="\U00002705")
                st.rerun()
            else:
                st.error(msg)


@st.dialog("\U0001F501 Duplicate Transaction")
def duplicate_dialog(user_id: int, row: dict) -> None:
    st.write(f"Duplicating: **{row['description'] or row['type']}** ({format_currency(row['amount'])})")
    c1, c2 = st.columns(2)
    date = c1.date_input("Date", value=now_ist().date(), key="dup_date")
    time = c2.time_input("Time", value=now_ist().time(), key="dup_time")
    if st.button("Create Duplicate", type="primary", use_container_width=True, key="dup_confirm"):
        ok, msg = services.duplicate_transaction(user_id, row["id"], dt.datetime.combine(date, time))
        st.toast(msg, icon="\U00002705" if ok else "\U000026A0\U0000FE0F")
        if ok:
            st.rerun()


def render(user_id: int) -> None:
    st.markdown("## \U0001F4CB Transactions")

    accounts = services.get_accounts(user_id, include_system=False)
    account_options = {f"{a['icon']} {a['name']}": a["id"] for a in accounts}
    all_categories = services.get_categories(user_id)
    category_options = {f"{c['icon']} {c['name']}": c["id"] for c in all_categories}

    with st.expander("\U0001F50D Search & Filters", expanded=False):
        search = st.text_input("Search merchant, description, category, person, account, notes")
        type_filter = st.multiselect("Type", ["Expense", "Income", "Transfer", "Adjustment"])
        account_filter_labels = st.multiselect("Account", list(account_options.keys()))
        category_filter_labels = st.multiselect("Category", list(category_options.keys()))

        c4, c5 = st.columns(2)
        date_from = c4.date_input("From", value=None, key="txn_date_from")
        date_to = c5.date_input("To", value=None, key="txn_date_to")
        c6, c7 = st.columns(2)
        amount_min = c6.number_input("Min Amount", value=0.0, step=100.0, key="txn_amt_min")
        amount_max = c7.number_input("Max Amount", value=0.0, step=100.0, key="txn_amt_max")

    df = services.get_transactions_df(
        user_id,
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
        return

    for bucket, group in group_transactions_by_day(df):
        st.markdown(f"<div class='timeline-day-label'>{bucket}</div>", unsafe_allow_html=True)
        for _, row in group.iterrows():
            row = row.to_dict()
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
                f"<div class='timeline-meta'>{meta} \u2022 {row['date'].strftime('%d %b, %I:%M %p')}</div></div></div>"
                f"{amt_html}</div>",
                unsafe_allow_html=True,
            )

            confirm_key = f"confirm_delete_{row['id']}"

            with col_actions.popover("\u22EF", use_container_width=True):
                if st.session_state.get(confirm_key):
                    st.warning("Delete this transaction? This can't be undone.")
                    cc1, cc2 = st.columns(2)
                    if cc1.button("Yes, delete", key=f"confirm_yes_{row['id']}", use_container_width=True):
                        ok, msg = services.delete_transaction(user_id, row["id"])
                        st.session_state.pop(confirm_key, None)
                        st.toast(msg, icon="\U00002705" if ok else "\U000026A0\U0000FE0F")
                        st.rerun()
                    if cc2.button("Cancel", key=f"confirm_no_{row['id']}", use_container_width=True):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()
                else:
                    if row["type"] != "Adjustment" and st.button("\U0000270F\uFE0F Edit", key=f"edit_{row['id']}", use_container_width=True):
                        edit_transaction_dialog(user_id, row)
                    if row["type"] != "Adjustment" and st.button("\U0001F501 Duplicate", key=f"dup_{row['id']}", use_container_width=True):
                        duplicate_dialog(user_id, row)
                    if st.button("\U0001F5D1\uFE0F Delete", key=f"del_{row['id']}", use_container_width=True):
                        st.session_state[confirm_key] = True
                        st.rerun()
