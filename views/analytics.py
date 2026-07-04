"""views/analytics.py - Deep-dive analytics: spending, trends, cash flow, net worth growth."""
from __future__ import annotations

import streamlit as st

import charts
import services


def render(user_id: int) -> None:
    st.markdown("## \U0001F4C8 Analytics")

    df = services.get_transactions_df(user_id)
    accounts = services.get_accounts(user_id, include_system=False)

    if df.empty:
        st.info("Add some transactions to see analytics here.")
        return

    tab_overview, tab_trends, tab_top, tab_accounts = st.tabs(
        ["Overview", "Trends", "Top", "Accounts"]
    )

    with tab_overview:
        st.plotly_chart(charts.spending_by_category_pie(df), use_container_width=True, config={"displayModeBar": False})
        st.plotly_chart(charts.income_vs_expense_bar(df), use_container_width=True, config={"displayModeBar": False})
        st.plotly_chart(charts.monthly_spending_bar(df), use_container_width=True, config={"displayModeBar": False})
        st.plotly_chart(charts.cash_flow_line(df), use_container_width=True, config={"displayModeBar": False})

    with tab_trends:
        st.plotly_chart(charts.category_trend_line(df, "Expense"), use_container_width=True, config={"displayModeBar": False})
        st.plotly_chart(charts.category_trend_line(df, "Income"), use_container_width=True, config={"displayModeBar": False})
        net_worth_df = services.get_net_worth_over_time(user_id, days=365)
        st.plotly_chart(charts.net_worth_line(net_worth_df), use_container_width=True, config={"displayModeBar": False})

    with tab_top:
        st.plotly_chart(charts.largest_transactions_bar(df, "Expense"), use_container_width=True, config={"displayModeBar": False})
        st.plotly_chart(charts.largest_transactions_bar(df, "Income"), use_container_width=True, config={"displayModeBar": False})

    with tab_accounts:
        st.plotly_chart(charts.account_balances_bar(accounts), use_container_width=True, config={"displayModeBar": False})
        st.markdown("#### Yearly Spending")
        d = df[df["type"] == "Expense"].copy()
        d["year"] = d["date"].dt.year
        yearly = d.groupby("year")["amount"].sum().reset_index().sort_values("year", ascending=False)
        st.dataframe(yearly, use_container_width=True, hide_index=True)
