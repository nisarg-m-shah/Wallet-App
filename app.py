"""
app.py
------
Main entry point. Handles the auth gate, then renders the Dashboard with
the six quick-entry action buttons (Expense / Income / Transfer / Automatic
Payment / Splitwise / Adjust Balance), each opening as a modal via
st.dialog so the user never leaves the dashboard.
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

st.set_page_config(page_title="Wallet Tracker", page_icon="\U0001F4B0", layout="wide", initial_sidebar_state="expanded")

init_db()


def load_css() -> None:
    css_path = os.path.join(os.path.dirname(__file__), "assets", "style.css")
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


load_css()


# --------------------------------------------------------------------------- #
# Auth gate
# --------------------------------------------------------------------------- #
def render_auth_screen() -> None:
    st.markdown(
        "<div style='text-align:center; margin-top:4rem;'>"
        "<div style='font-size:42px;'>\U0001F4B0</div>"
        "<div style='font-size:26px; font-weight:800; color:#2D3436;'>Wallet Tracker</div>"
        "<div style='color:#8395A7; margin-bottom:2rem;'>Your money, minus the spreadsheet.</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    col = st.columns([1, 1.2, 1])[1]
    with col:
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
# Sidebar
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.markdown(f"### \U0001F44B {USER['display_name']}")
    st.caption(USER["email"])
    st.divider()
    st.page_link("app.py", label="Dashboard", icon="\U0001F3E0")
    st.page_link("pages/Accounts.py", label="Accounts", icon="\U0001F3E6")
    st.page_link("pages/Transactions.py", label="Transactions", icon="\U0001F4CB")
    st.page_link("pages/Analytics.py", label="Analytics", icon="\U0001F4C8")
    st.page_link("pages/Recurring.py", label="Recurring", icon="\U0001F501")
    st.page_link("pages/Settings.py", label="Settings", icon="\U00002699\U0000FE0F")
    st.divider()
    if st.button("Log Out", use_container_width=True):
        del st.session_state["user"]
        st.rerun()


# --------------------------------------------------------------------------- #
# Shared dropdown data
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
    amount = st.number_input("Amount", min_value=0.0, step=50.0, format="%.2f")
    description = st.text_input("Description")
    category_label = st.selectbox("Category", list(expense_cat_options.keys()))
    c1, c2 = st.columns(2)
    date = c1.date_input("Date", value=dt.date.today())
    time = c2.time_input("Time", value=dt.datetime.now().time())
    payment_mode = st.selectbox("Payment Mode", PAYMENT_MODES)
    account_label = st.selectbox("Account", list(account_options.keys()))
    payee = st.text_input("Payee", placeholder="Who did you pay?")

    if st.button("Save Expense", type="primary", use_container_width=True):
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
    payer = st.selectbox("Payer", DEFAULT_PAYERS)
    if payer == "Other":
        payer = st.text_input("Payer name")
    category_label = st.selectbox("Category", list(income_cat_options.keys()))
    payment_mode = st.selectbox("Payment Mode", PAYMENT_MODES, key="inc_mode")
    c1, c2 = st.columns(2)
    date = c1.date_input("Date", value=dt.date.today(), key="inc_date")
    time = c2.time_input("Time", value=dt.datetime.now().time(), key="inc_time")
    account_label = st.selectbox("Account", list(account_options.keys()), key="inc_acc")

    if st.button("Save Income", type="primary", use_container_width=True):
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

    if st.button("Save Transfer", type="primary", use_container_width=True):
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
    frequency = st.selectbox("Frequency", ["Daily", "Weekly", "Monthly", "Yearly"])
    first_date = st.date_input("First Payment Date", value=dt.date.today(), key="rec_date")
    category_label = st.selectbox("Category", list(expense_cat_options.keys()), key="rec_cat")
    account_label = st.selectbox("Account", list(account_options.keys()), key="rec_acc")

    if st.button("Schedule Payment", type="primary", use_container_width=True):
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
    tab1, tab2 = st.tabs(["Someone owes me", "Settle a debt"])

    with tab1:
        st.write("Record money you lent to a friend (outside of an expense).")
        person = st.text_input("Friend's name", key="sw_person")
        amount = st.number_input("Amount", min_value=0.0, step=50.0, format="%.2f", key="sw_amt")
        notes = st.text_input("Notes", key="sw_notes")
        if st.button("Record Loan", type="primary", use_container_width=True):
            ok, msg = services.add_splitwise_loan(USER_ID, person, amount, notes)
            if ok:
                st.toast(msg, icon="\U00002705")
                st.rerun()
            else:
                st.error(msg)

    with tab2:
        st.write("Settling a debt moves money from a real account into Splitwise, "
                 "clearing your outstanding balance automatically.")
        if account_options:
            amount2 = st.number_input("Amount to settle", min_value=0.0, step=50.0, format="%.2f", key="sw_settle_amt")
            from_label2 = st.selectbox("Pay from", list(account_options.keys()), key="sw_settle_acc")
            if st.button("Settle via Transfer", type="primary", use_container_width=True):
                sw_acc = services.get_splitwise_account(USER_ID)
                ok, msg = services.add_transfer(
                    USER_ID, amount2, account_options[from_label2], sw_acc.id, dt.datetime.utcnow(),
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
    reason = st.text_input("Reason", placeholder="e.g. Bank statement reconciliation")

    if st.button("Save Adjustment", type="primary", use_container_width=True):
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
st.markdown("## \U0001F3E0 Dashboard")

metrics = services.get_dashboard_metrics(USER_ID)


def metric_card(label: str, value: str, sub: str | None = None, sub_class: str = "") -> str:
    sub_html = f"<div class='metric-sub {sub_class}'>{sub}</div>" if sub else ""
    return (
        f"<div class='metric-card'><div class='metric-label'>{label}</div>"
        f"<div class='metric-value'>{value}</div>{sub_html}</div>"
    )


row1 = st.columns(3)
row1[0].markdown(metric_card("Net Worth", format_currency(metrics.net_worth)), unsafe_allow_html=True)
row1[1].markdown(metric_card("Cash Balance", format_currency(metrics.cash_balance)), unsafe_allow_html=True)
row1[2].markdown(metric_card("Total Bank Balance", format_currency(metrics.bank_balance)), unsafe_allow_html=True)

st.write("")
row2 = st.columns(3)
row2[0].markdown(metric_card("Investment Value", format_currency(metrics.investment_value)), unsafe_allow_html=True)
row2[1].markdown(metric_card("Amount Owed", format_currency(metrics.amount_owed), "You owe this", "negative"), unsafe_allow_html=True)
row2[2].markdown(metric_card("Amount Receivable", format_currency(metrics.amount_receivable), "Owed to you", "positive"), unsafe_allow_html=True)

st.write("")
row3 = st.columns(3)
row3[0].markdown(metric_card("Monthly Income", format_currency(metrics.monthly_income), sub_class="positive"), unsafe_allow_html=True)
row3[1].markdown(metric_card("Monthly Expenses", format_currency(metrics.monthly_expenses), sub_class="negative"), unsafe_allow_html=True)
savings_class = "positive" if metrics.monthly_savings >= 0 else "negative"
row3[2].markdown(metric_card("Monthly Savings", format_signed_currency(metrics.monthly_savings), sub_class=savings_class), unsafe_allow_html=True)

# ---------------- Quick action buttons ---------------- #
st.markdown("<div class='section-title'>Quick Add</div>", unsafe_allow_html=True)
action_cols = st.columns(6)
if action_cols[0].button("\U0001F4B8\nExpense", use_container_width=True):
    expense_dialog()
if action_cols[1].button("\U0001F4B0\nIncome", use_container_width=True):
    income_dialog()
if action_cols[2].button("\U0001F504\nTransfer", use_container_width=True):
    transfer_dialog()
if action_cols[3].button("\U0001F501\nAuto Payment", use_container_width=True):
    recurring_dialog()
if action_cols[4].button("\U0001F91D\nSplitwise", use_container_width=True):
    splitwise_dialog()
if action_cols[5].button("\U00002696\U0000FE0F\nAdjust", use_container_width=True):
    adjust_balance_dialog()

# ---------------- Charts row ---------------- #
st.markdown("<div class='section-title'>Overview</div>", unsafe_allow_html=True)
all_txns = services.get_transactions_df(USER_ID)

chart_col1, chart_col2 = st.columns(2)
with chart_col1:
    st.plotly_chart(charts.income_vs_expense_bar(all_txns), use_container_width=True, config={"displayModeBar": False})
with chart_col2:
    st.plotly_chart(charts.spending_by_category_pie(all_txns), use_container_width=True, config={"displayModeBar": False})

chart_col3, chart_col4 = st.columns(2)
with chart_col3:
    st.plotly_chart(charts.account_balances_bar(accounts), use_container_width=True, config={"displayModeBar": False})
with chart_col4:
    net_worth_df = services.get_net_worth_over_time(USER_ID)
    st.plotly_chart(charts.net_worth_line(net_worth_df), use_container_width=True, config={"displayModeBar": False})

# ---------------- Recurring + Splitwise summary ---------------- #
sum_col1, sum_col2 = st.columns(2)
with sum_col1:
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

with sum_col2:
    st.markdown("<div class='section-title'>Outstanding Splitwise Debts</div>", unsafe_allow_html=True)
    sw = services.get_splitwise_summary(USER_ID)
    if not sw["records"]:
        st.caption("You're all settled up! \U0001F389")
    for r in sw["records"][:5]:
        css_class = "debt-card" if r["kind"] == "Debt" else "loan-card"
        verb = "You owe" if r["kind"] == "Debt" else "Owes you"
        st.markdown(
            f"<div class='{css_class}'><b>{r['person']}</b><br>"
            f"<span style='font-size:13px;color:#636E72;'>{verb}</span> "
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
