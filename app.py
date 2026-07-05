"""
app.py
------
Main entry point. Mobile-first: navigation is a horizontal top bar (not the
native Streamlit sidebar, which auto-collapses on phones after every tap -
this was the root cause of the "nav disappears" bug). Everything routes
through here; `views/*.py` expose plain `render(user_id)` functions instead
of being separate auto-detected Streamlit pages.
"""
from __future__ import annotations

import datetime as dt
import os

import streamlit as st

import auth
import charts
import services
from database import init_db
from utils import (
    format_currency,
    format_signed_currency,
    group_transactions_by_day,
    transaction_line_icon,
)
from views import accounts as view_accounts
from views import analytics as view_analytics
from views import recurring as view_recurring
from views import settings as view_settings
from views import transactions as view_transactions

import pandas as pd
import session_auth

st.set_page_config(page_title="Wallet Tracker", page_icon="\U0001F4B0", layout="centered", initial_sidebar_state="collapsed")

init_db()


def load_css() -> None:
    css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css()
# Hide the native sidebar entirely - navigation now lives in the top bar,
# so there's nothing for it to do except cause the mobile collapse bug.
st.markdown("<style>section[data-testid='stSidebar'] {display:none;}</style>", unsafe_allow_html=True)


# --------------------------------------------------------------------------- #
# Persistent login: Streamlit's session_state resets on every page reload,
# so "remember me" is implemented via a signed token in a browser cookie.
# --------------------------------------------------------------------------- #
@st.cache_resource
def get_cookie_manager():
    import extra_streamlit_components as stx
    return stx.CookieManager(key="wallet_cookie_manager")


cookie_manager = get_cookie_manager()
COOKIE_NAME = "wallet_session"

if st.session_state.pop("logout_requested", False):
    cookie_manager.delete(COOKIE_NAME)
    st.session_state.pop("user", None)

if "user" not in st.session_state:
    token = cookie_manager.get(COOKIE_NAME)
    if token:
        restored_uid = session_auth.verify_token(token)
        if restored_uid:
            restored_user = auth.get_user_by_id(restored_uid)
            if restored_user:
                st.session_state.user = restored_user


def _remember_login(user: dict) -> None:
    st.session_state.user = user
    token = session_auth.create_token(user["id"])
    cookie_manager.set(COOKIE_NAME, token, expires_at=dt.datetime.now() + dt.timedelta(days=30), key="set_wallet_cookie")


# --------------------------------------------------------------------------- #
# Auth gate
# --------------------------------------------------------------------------- #
def render_auth_screen() -> None:
    st.markdown(
        "<div style='text-align:center; margin-top:3rem;'>"
        "<div style='font-size:42px;'>\U0001F4B0</div>"
        "<div style='font-size:26px; font-weight:800; color:#EDEEF2;'>Wallet Tracker</div>"
        "<div style='color:#9096A8; margin-bottom:2rem;'>Your money, minus the spreadsheet.</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log In", type="primary", use_container_width=True)
        if submitted:
            ok, msg, user = auth.log_in(email, password)
            if ok:
                _remember_login(user)
                st.rerun()
            else:
                st.error(msg)

    with tab_signup:
        with st.form("signup_form"):
            name = st.text_input("Name")
            email_s = st.text_input("Email", key="signup_email")
            password_s = st.text_input("Password", type="password", key="signup_pw",
                                        help="At least 8 characters")
            submitted_s = st.form_submit_button("Create Account", type="primary", use_container_width=True)
        if submitted_s:
            ok, msg = auth.sign_up(email_s, password_s, name)
            if ok:
                st.success(msg + " Please log in.")
            else:
                st.error(msg)


if "user" not in st.session_state:
    render_auth_screen()
    st.stop()

USER = st.session_state.user
USER_ID = USER["id"]

# --------------------------------------------------------------------------- #
# Auth gate
# --------------------------------------------------------------------------- #
def render_auth_screen() -> None:
    st.markdown(
        "<div style='text-align:center; margin-top:3rem;'>"
        "<div style='font-size:42px;'>\U0001F4B0</div>"
        "<div style='font-size:26px; font-weight:800; color:#EDEEF2;'>Wallet Tracker</div>"
        "<div style='color:#9096A8; margin-bottom:2rem;'>Your money, minus the spreadsheet.</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log In", type="primary", use_container_width=True)
        if submitted:
            ok, msg, user = auth.log_in(email, password)
            if ok:
                st.session_state.user = user
                st.rerun()
            else:
                st.error(msg)

    with tab_signup:
        with st.form("signup_form"):
            name = st.text_input("Name")
            email_s = st.text_input("Email", key="signup_email")
            password_s = st.text_input("Password", type="password", key="signup_pw",
                                        help="At least 8 characters")
            submitted_s = st.form_submit_button("Create Account", type="primary", use_container_width=True)
        if submitted_s:
            ok, msg = auth.sign_up(email_s, password_s, name)
            if ok:
                st.success(msg + " Please log in.")
            else:
                st.error(msg)


if "user" not in st.session_state:
    render_auth_screen()
    st.stop()

USER = st.session_state.user
USER_ID = USER["id"]

# Catch up any due automatic payments as soon as the user is authenticated.
generated = services.process_due_recurring_payments(USER_ID)
if generated:
    st.toast(f"Generated {generated} automatic payment transaction(s).", icon="\U0001F501")


# --------------------------------------------------------------------------- #
# Top navigation bar (mobile-first: survives phone browsers, no auto-collapse)
# --------------------------------------------------------------------------- #
NAV_ITEMS = [
    ("Dashboard", "\U0001F3E0"),
    ("Accounts", "\U0001F3E6"),
    ("Transactions", "\U0001F4CB"),
    ("Analytics", "\U0001F4C8"),
    ("Recurring", "\U0001F501"),
    ("Settings", "\U00002699\U0000FE0F"),
]

if "active_nav" not in st.session_state:
    st.session_state.active_nav = "Dashboard"

nav_cols = st.columns(len(NAV_ITEMS))
for (label, icon), col in zip(NAV_ITEMS, nav_cols):
    is_active = st.session_state.active_nav == label
    if col.button(f"{icon}\n{label}", key=f"nav_{label}", use_container_width=True,
                  type="primary" if is_active else "secondary"):
        st.session_state.active_nav = label
        st.rerun()

st.divider()


# --------------------------------------------------------------------------- #
# Route to non-dashboard views
# --------------------------------------------------------------------------- #
if st.session_state.active_nav == "Accounts":
    view_accounts.render(USER_ID)
    st.stop()
elif st.session_state.active_nav == "Transactions":
    view_transactions.render(USER_ID)
    st.stop()
elif st.session_state.active_nav == "Analytics":
    view_analytics.render(USER_ID)
    st.stop()
elif st.session_state.active_nav == "Recurring":
    view_recurring.render(USER_ID)
    st.stop()
elif st.session_state.active_nav == "Settings":
    view_settings.render(USER_ID, USER)
    st.stop()


# --------------------------------------------------------------------------- #
# Shared dropdown data (Dashboard + dialogs)
# --------------------------------------------------------------------------- #
accounts = services.get_accounts(USER_ID, include_system=False)
account_options = {f"{a['icon']} {a['name']}": a["id"] for a in accounts}
expense_categories = services.get_categories(USER_ID, kind="Expense")
income_categories = services.get_categories(USER_ID, kind="Income")
expense_cat_options = {f"{c['icon']} {c['name']}": c["id"] for c in expense_categories}
income_cat_options = {f"{c['icon']} {c['name']}": c["id"] for c in income_categories}

PAYMENT_MODES = ["Cash", "UPI", "Splitwise", "Debit Card", "Netbanking"]
DEFAULT_PAYERS = ["Mom", "Dad", "Pravis Consulting", "Aaryann Mavani", "Other"]


# --------------------------------------------------------------------------- #
# Modals (Streamlit dialogs) for the six quick-entry actions
# --------------------------------------------------------------------------- #
@st.dialog("\U0001F4B8 Add Expense")
def expense_dialog():
    st.caption("Congratulations! You're broke.")
    if not account_options:
        st.warning("Create an account first.")
        return
    amount = st.number_input("Amount", min_value=0.0, step=50.0, format="%.2f", key="exp_amt")
    description = st.text_input("Description", key="exp_desc")
    category_label = st.selectbox("Category", list(expense_cat_options.keys()), key="exp_cat")
    c1, c2 = st.columns(2)
    # Explicit keys + no upper bound, so any past date/time can be selected -
    # this is what lets you log an expense days after it actually happened.
    date = c1.date_input("Date", value=dt.date.today(), key="exp_date")
    time = c2.time_input("Time", value=dt.datetime.now().time(), key="exp_time")
    payment_mode = st.selectbox("Payment Mode", PAYMENT_MODES, key="exp_mode")
    account_label = st.selectbox("Account", list(account_options.keys()), key="exp_acc")
    payee = st.text_input("Payee", placeholder="Who did you pay?", key="exp_payee")

    if st.button("Save Expense", type="primary", use_container_width=True, key="exp_save"):
        ok, msg = services.add_expense(
            USER_ID, amount, description, expense_cat_options[category_label],
            dt.datetime.combine(date, time), payment_mode, account_options[account_label], payee,
        )
        if ok:
            st.toast(msg, icon="\U00002705")
            st.rerun()
        else:
            st.error(msg)


@st.dialog("\U0001F4B0 Add Income")
def income_dialog():
    st.caption("It's not much but it's honest work.")
    if not account_options:
        st.warning("Create an account first.")
        return
    amount = st.number_input("Amount", min_value=0.0, step=50.0, format="%.2f", key="inc_amt")
    description = st.text_input("Description", key="inc_desc")
    payer = st.selectbox("Payer", DEFAULT_PAYERS, key="inc_payer")
    if payer == "Other":
        payer = st.text_input("Payer name", key="inc_payer_other")
    category_label = st.selectbox("Category", list(income_cat_options.keys()), key="inc_cat")
    payment_mode = st.selectbox("Payment Mode", PAYMENT_MODES, key="inc_mode")
    c1, c2 = st.columns(2)
    date = c1.date_input("Date", value=dt.date.today(), key="inc_date")
    time = c2.time_input("Time", value=dt.datetime.now().time(), key="inc_time")
    account_label = st.selectbox("Account", list(account_options.keys()), key="inc_acc")

    if st.button("Save Income", type="primary", use_container_width=True, key="inc_save"):
        ok, msg = services.add_income(
            USER_ID, amount, description, payer, income_cat_options[category_label],
            payment_mode, dt.datetime.combine(date, time), account_options[account_label],
        )
        if ok:
            st.toast(msg, icon="\U00002705")
            st.rerun()
        else:
            st.error(msg)


@st.dialog("\U0001F504 Transfer Money")
def transfer_dialog():
    st.caption("Modern problems require outstanding moves.")
    if len(account_options) < 2:
        st.warning("You need at least two accounts to transfer between.")
        return
    amount = st.number_input("Amount", min_value=0.0, step=50.0, format="%.2f", key="tr_amt")
    from_label = st.selectbox("From Account", list(account_options.keys()), key="tr_from")
    to_label = st.selectbox("To Account", list(account_options.keys()), key="tr_to")
    c1, c2 = st.columns(2)
    date = c1.date_input("Date", value=dt.date.today(), key="tr_date")
    time = c2.time_input("Time", value=dt.datetime.now().time(), key="tr_time")
    notes = st.text_input("Notes", key="tr_notes")

    if st.button("Save Transfer", type="primary", use_container_width=True, key="tr_save"):
        ok, msg = services.add_transfer(
            USER_ID, amount, account_options[from_label], account_options[to_label],
            dt.datetime.combine(date, time), notes,
        )
        if ok:
            st.toast(msg, icon="\U00002705")
            st.rerun()
        else:
            st.error(msg)


@st.dialog("\U0001F501 Automatic Payment")
def recurring_dialog():
    st.caption("Yeah gurl go get that Netflix subscription.")
    if not account_options:
        st.warning("Create an account first.")
        return
    amount = st.number_input("Amount", min_value=0.0, step=50.0, format="%.2f", key="rec_amt")
    description = st.text_input("Description", key="rec_desc")
    frequency = st.selectbox("Frequency", ["Daily", "Weekly", "Monthly", "Yearly"], key="rec_freq")
    first_date = st.date_input("First Payment Date", value=dt.date.today(), key="rec_date")
    category_label = st.selectbox("Category", list(expense_cat_options.keys()), key="rec_cat")
    account_label = st.selectbox("Account", list(account_options.keys()), key="rec_acc")

    if st.button("Schedule Payment", type="primary", use_container_width=True, key="rec_save"):
        ok, msg = services.add_recurring_payment(
            USER_ID, amount, description, frequency,
            dt.datetime.combine(first_date, dt.time.min),
            expense_cat_options[category_label], account_options[account_label],
        )
        if ok:
            st.toast(msg, icon="\U00002705")
            st.rerun()
        else:
            st.error(msg)


@st.dialog("\U0001F91D Splitwise")
def splitwise_dialog():
    st.caption("Split it now, sort it out later.")
    tab1, tab2, tab3 = st.tabs(["Owed to me", "I owe someone", "Settle a debt"])

    with tab1:
        st.write("Record money you lent to a friend (outside of an expense).")
        person = st.text_input("Friend's name", key="sw_loan_person")
        amount = st.number_input("Amount", min_value=0.0, step=50.0, format="%.2f", key="sw_loan_amt")
        notes = st.text_input("Notes", key="sw_loan_notes")
        if st.button("Record Loan", type="primary", use_container_width=True, key="sw_loan_save"):
            ok, msg = services.add_splitwise_loan(USER_ID, person, amount, notes)
            if ok:
                st.toast(msg, icon="\U00002705")
                st.rerun()
            else:
                st.error(msg)

    with tab2:
        st.write("Record money you owe a friend directly - not tied to an expense "
                 "(e.g. they covered a bill outright, or a personal loan).")
        person2 = st.text_input("Friend's name", key="sw_debt_person")
        amount2b = st.number_input("Amount", min_value=0.0, step=50.0, format="%.2f", key="sw_debt_amt")
        notes2 = st.text_input("Notes", key="sw_debt_notes")
        if st.button("Record Debt", type="primary", use_container_width=True, key="sw_debt_save"):
            ok, msg = services.add_splitwise_debt(USER_ID, person2, amount2b, notes2)
            if ok:
                st.toast(msg, icon="\U00002705")
                st.rerun()
            else:
                st.error(msg)

    with tab3:
        st.write("Settling a debt moves money from a real account into Splitwise, "
                 "clearing your outstanding balance automatically (oldest first).")
        if account_options:
            amount3 = st.number_input("Amount to settle", min_value=0.0, step=50.0, format="%.2f", key="sw_settle_amt")
            from_label3 = st.selectbox("Pay from", list(account_options.keys()), key="sw_settle_acc")
            if st.button("Settle via Transfer", type="primary", use_container_width=True, key="sw_settle_save"):
                sw_acc = services.get_splitwise_account(USER_ID)
                ok, msg = services.add_transfer(
                    USER_ID, amount3, account_options[from_label3], sw_acc.id, dt.datetime.utcnow(),
                    "Splitwise settlement",
                )
                if ok:
                    st.toast(msg, icon="\U00002705")
                    st.rerun()
                else:
                    st.error(msg)


@st.dialog("\U00002696\U0000FE0F Adjust Balance")
def adjust_balance_dialog():
    st.caption("Reality check your account balance.")
    if not account_options:
        st.warning("Create an account first.")
        return
    account_label = st.selectbox("Account", list(account_options.keys()), key="adj_acc")
    current = next(a for a in accounts if a["id"] == account_options[account_label])
    st.metric("Current Balance", format_currency(current["balance"], current["currency"]))
    new_balance = st.number_input("New Balance", step=50.0, format="%.2f", key="adj_new")
    c1, c2 = st.columns(2)
    date = c1.date_input("Date", value=dt.date.today(), key="adj_date")
    time = c2.time_input("Time", value=dt.datetime.now().time(), key="adj_time")
    reason = st.text_input("Reason", placeholder="e.g. Bank statement reconciliation", key="adj_reason")

    if st.button("Save Adjustment", type="primary", use_container_width=True, key="adj_save"):
        ok, msg = services.adjust_balance(
            USER_ID, account_options[account_label], new_balance,
            dt.datetime.combine(date, time), reason,
        )
        if ok:
            st.toast(msg, icon="\U00002705")
            st.rerun()
        else:
            st.error(msg)


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
st.markdown(f"### \U0001F44B {USER['display_name']}")

metrics = services.get_dashboard_metrics(USER_ID)


def metric_card(label: str, value: str, sub: str | None = None, sub_class: str = "") -> str:
    sub_html = f"<div class='metric-sub {sub_class}'>{sub}</div>" if sub else ""
    return (
        f"<div class='metric-card'><div class='metric-label'>{label}</div>"
        f"<div class='metric-value'>{value}</div>{sub_html}</div>"
    )


# Mobile-first: 2 cards per row instead of 3 so text never gets cramped on a phone.
metric_rows = [
    ("Net Worth", format_currency(metrics.net_worth), None, ""),
    ("Cash Balance", format_currency(metrics.cash_balance), None, ""),
    ("Total Bank Balance", format_currency(metrics.bank_balance), None, ""),
    ("Investment Value", format_currency(metrics.investment_value), None, ""),
    ("Amount Owed", format_currency(metrics.amount_owed), "You owe this", "negative"),
    ("Amount Receivable", format_currency(metrics.amount_receivable), "Owed to you", "positive"),
    ("Monthly Income", format_currency(metrics.monthly_income), None, "positive"),
    ("Monthly Expenses", format_currency(metrics.monthly_expenses), None, "negative"),
    ("Monthly Savings", format_signed_currency(metrics.monthly_savings), None,
     "positive" if metrics.monthly_savings >= 0 else "negative"),
]

for i in range(0, len(metric_rows), 2):
    cols = st.columns(2)
    for col, row in zip(cols, metric_rows[i:i + 2]):
        col.markdown(metric_card(*row), unsafe_allow_html=True)
    st.write("")

# ---------------- Quick action buttons (3-per-row grid, phone-friendly) ---------------- #
st.markdown("<div class='section-title'>Quick Add</div>", unsafe_allow_html=True)
qa_row1 = st.columns(3)
qa_row2 = st.columns(3)
if qa_row1[0].button("\U0001F4B8 Expense", use_container_width=True):
    expense_dialog()
if qa_row1[1].button("\U0001F4B0 Income", use_container_width=True):
    income_dialog()
if qa_row1[2].button("\U0001F504 Transfer", use_container_width=True):
    transfer_dialog()
if qa_row2[0].button("\U0001F501 Auto Pay", use_container_width=True):
    recurring_dialog()
if qa_row2[1].button("\U0001F91D Splitwise", use_container_width=True):
    splitwise_dialog()
if qa_row2[2].button("\U00002696\U0000FE0F Adjust", use_container_width=True):
    adjust_balance_dialog()

# ---------------- Charts (single column - stacked charts read far better on a phone) ---------------- #
st.markdown("<div class='section-title'>Overview</div>", unsafe_allow_html=True)
all_txns = services.get_transactions_df(USER_ID)

st.plotly_chart(charts.income_vs_expense_bar(all_txns), use_container_width=True, config={"displayModeBar": False})
st.plotly_chart(charts.spending_by_category_pie(all_txns), use_container_width=True, config={"displayModeBar": False})
st.plotly_chart(charts.account_balances_bar(accounts), use_container_width=True, config={"displayModeBar": False})
net_worth_df = services.get_net_worth_over_time(USER_ID)
st.plotly_chart(charts.net_worth_line(net_worth_df), use_container_width=True, config={"displayModeBar": False})

# ---------------- Recurring + Splitwise summary ---------------- #
st.markdown("<div class='section-title'>Upcoming Automatic Payments</div>", unsafe_allow_html=True)
upcoming = services.get_recurring_payments(USER_ID)[:5]
if not upcoming:
    st.caption("No automatic payments scheduled.")
for r in upcoming:
    st.markdown(
        f"<div class='timeline-row'><div class='timeline-left'>"
        f"<div class='timeline-icon'>\U0001F501</div>"
        f"<div><div class='timeline-desc'>{r['description']}</div>"
        f"<div class='timeline-meta'>{r['account']} \u2022 {r['frequency']} \u2022 "
        f"next {r['next_due_date'].strftime('%d %b %Y')}</div></div></div>"
        f"<div class='timeline-amount negative'>{format_currency(r['amount'])}</div></div>",
        unsafe_allow_html=True,
    )

st.markdown("<div class='section-title'>Outstanding Splitwise Debts</div>", unsafe_allow_html=True)
sw = services.get_splitwise_summary(USER_ID)
if not sw["records"]:
    st.caption("You're all settled up! \U0001F389")
for r in sw["records"][:5]:
    css_class = "debt-card" if r["kind"] == "Debt" else "loan-card"
    verb = "You owe" if r["kind"] == "Debt" else "Owes you"
    st.markdown(
        f"<div class='{css_class}'><b>{r['person']}</b><br>"
        f"<span style='font-size:13px;color:#9096A8;'>{verb}</span> "
        f"<b>{format_currency(r['amount'])}</b></div>",
        unsafe_allow_html=True,
    )

# ---------------- Recent transaction timeline ---------------- #
st.markdown("<div class='section-title'>Recent Transactions</div>", unsafe_allow_html=True)
recent = services.get_transactions_df(USER_ID, limit=15)

if recent.empty:
    st.info("No transactions yet. Use Quick Add above to get started!")
else:
    for bucket, group in group_transactions_by_day(recent):
        st.markdown(f"<div class='timeline-day-label'>{bucket}</div>", unsafe_allow_html=True)
        for _, row in group.iterrows():
            icon = transaction_line_icon(row)
            if row["type"] == "Expense":
                amt_html = f"<span class='timeline-amount negative'>-{format_currency(row['amount'])}</span>"
                meta = f"{row['category']} \u2022 {row['account']}"
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
            st.markdown(
                f"<div class='timeline-row'><div class='timeline-left'>"
                f"<div class='timeline-icon'>{icon}</div>"
                f"<div><div class='timeline-desc'>{desc}</div>"
                f"<div class='timeline-meta'>{meta}</div></div></div>{amt_html}</div>",
                unsafe_allow_html=True,
            )
