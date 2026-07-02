"""pages/Analytics.py - Deep-dive analytics: spending, trends, cash flow, net worth growth."""
from __future__ import annotations

import os

import streamlit as st

import charts
import services

st.set_page_config(page_title="Analytics | Wallet Tracker", page_icon="\U0001F4C8", layout="wide")

with open(os.path.join(os.path.dirname(__file__), "..", "assets", "style.css")) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

if "user" not in st.session_state:
    st.warning("Please log in from the Dashboard page first.")
    st.stop()

USER_ID = st.session_state.user["id"]

st.markdown("## \U0001F4C8 Analytics")

df = services.get_transactions_df(USER_ID)
accounts = services.get_accounts(USER_ID, include_system=False)

if df.empty:
    st.info("Add some transactions to see analytics here.")
    st.stop()

tab_overview, tab_trends, tab_top, tab_accounts = st.tabs(
    ["Overview", "Trends", "Largest Transactions", "Account Balances"]
)

with tab_overview:
    c1, c2 = st.columns(2)
    c1.plotly_chart(charts.spending_by_category_pie(df), use_container_width=True, config={"displayModeBar": False})
    c2.plotly_chart(charts.income_vs_expense_bar(df), use_container_width=True, config={"displayModeBar": False})

    c3, c4 = st.columns(2)
    c3.plotly_chart(charts.monthly_spending_bar(df), use_container_width=True, config={"displayModeBar": False})
    c4.plotly_chart(charts.cash_flow_line(df), use_container_width=True, config={"displayModeBar": False})

with tab_trends:
    c1, c2 = st.columns(2)
    c1.plotly_chart(charts.category_trend_line(df, "Expense"), use_container_width=True, config={"displayModeBar": False})
    c2.plotly_chart(charts.category_trend_line(df, "Income"), use_container_width=True, config={"displayModeBar": False})

    net_worth_df = services.get_net_worth_over_time(USER_ID, days=365)
    st.plotly_chart(charts.net_worth_line(net_worth_df), use_container_width=True, config={"displayModeBar": False})

with tab_top:
    c1, c2 = st.columns(2)
    c1.plotly_chart(charts.largest_transactions_bar(df, "Expense"), use_container_width=True, config={"displayModeBar": False})
    c2.plotly_chart(charts.largest_transactions_bar(df, "Income"), use_container_width=True, config={"displayModeBar": False})

with tab_accounts:
    st.plotly_chart(charts.account_balances_bar(accounts), use_container_width=True, config={"displayModeBar": False})

    st.markdown("#### Yearly Spending")
    d = df[df["type"] == "Expense"].copy()
    d["year"] = d["date"].dt.year
    yearly = d.groupby("year")["amount"].sum().reset_index().sort_values("year", ascending=False)
    st.dataframe(yearly, use_container_width=True, hide_index=True)
