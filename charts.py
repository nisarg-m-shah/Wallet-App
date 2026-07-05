"""
charts.py
---------
Every Plotly figure used in the app lives here so styling stays consistent
(fonts, colors, transparent backgrounds to blend with the custom CSS cards).
"""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

PALETTE = ["#6C5CE7", "#00B894", "#0984E3", "#E17055", "#FDCB6E",
           "#D63031", "#00CEC9", "#E84393", "#2D3436", "#0057B8"]

FONT = dict(family="Inter, -apple-system, sans-serif", size=13, color="#EDEEF2")


def _base_layout(fig: go.Figure, height: int = 320, title: str | None = None) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=40 if title else 10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=FONT,
        title=dict(text=title, x=0.02, font=dict(size=15, color="#EDEEF2")) if title else None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(color="#EDEEF2")),
        hoverlabel=dict(bgcolor="#1B1E29", font_size=12, font_color="#EDEEF2"),
    )
    return fig


def spending_by_category_pie(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_state("No expenses yet")
    grouped = df[df["type"] == "Expense"].groupby("category")["amount"].sum().reset_index()
    grouped = grouped.sort_values("amount", ascending=False)
    fig = px.pie(grouped, names="category", values="amount", hole=0.55, color_discrete_sequence=PALETTE)
    fig.update_traces(textposition="outside", textinfo="percent+label")
    return _base_layout(fig, title="Spending by Category")


def monthly_spending_bar(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_state("No transactions yet")
    d = df.copy()
    d["month"] = pd.to_datetime(d["date"]).dt.to_period("M").astype(str)
    grouped = d[d["type"] == "Expense"].groupby("month")["amount"].sum().reset_index()
    fig = px.bar(grouped, x="month", y="amount", color_discrete_sequence=[PALETTE[0]])
    fig.update_traces(marker_line_width=0, width=0.5)
    return _base_layout(fig, title="Monthly Spending")


def income_vs_expense_bar(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_state("No transactions yet")
    d = df.copy()
    d["month"] = pd.to_datetime(d["date"]).dt.to_period("M").astype(str)
    grouped = d[d["type"].isin(["Income", "Expense"])].groupby(["month", "type"])["amount"].sum().reset_index()
    fig = px.bar(grouped, x="month", y="amount", color="type", barmode="group",
                 color_discrete_map={"Income": "#00B894", "Expense": "#D63031"})
    return _base_layout(fig, title="Income vs Expense")


def net_worth_line(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_state("Not enough history yet")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["net_worth"], mode="lines", fill="tozeroy",
        line=dict(color=PALETTE[0], width=2.5),
        fillcolor="rgba(108,92,231,0.12)",
    ))
    return _base_layout(fig, title="Net Worth Over Time")


def account_balances_bar(accounts: list[dict]) -> go.Figure:
    if not accounts:
        return empty_state("No accounts yet")
    df = pd.DataFrame(accounts)
    fig = px.bar(df, x="name", y="balance", color="name", color_discrete_sequence=PALETTE)
    fig.update_layout(showlegend=False)
    return _base_layout(fig, title="Account Balances")


def cash_flow_line(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_state("No transactions yet")
    d = df.copy()
    d["date_only"] = pd.to_datetime(d["date"]).dt.date
    d["signed"] = d.apply(lambda r: r["amount"] if r["type"] == "Income" else (-r["amount"] if r["type"] == "Expense" else 0), axis=1)
    grouped = d.groupby("date_only")["signed"].sum().reset_index()
    grouped["cumulative"] = grouped["signed"].cumsum()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=grouped["date_only"], y=grouped["cumulative"], mode="lines",
                              line=dict(color=PALETTE[2], width=2.5)))
    return _base_layout(fig, title="Cash Flow")


def category_trend_line(df: pd.DataFrame, kind: str = "Expense") -> go.Figure:
    if df.empty:
        return empty_state(f"No {kind.lower()} data yet")
    d = df[df["type"] == kind].copy()
    if d.empty:
        return empty_state(f"No {kind.lower()} data yet")
    d["month"] = pd.to_datetime(d["date"]).dt.to_period("M").astype(str)
    grouped = d.groupby("month")["amount"].sum().reset_index()
    fig = px.line(grouped, x="month", y="amount", markers=True,
                  color_discrete_sequence=[PALETTE[1] if kind == "Income" else PALETTE[5]])
    return _base_layout(fig, title=f"{kind} Trend")



def largest_transactions_bar(df: pd.DataFrame, kind: str = "Expense", n: int = 10) -> go.Figure:
    if df.empty:
        return empty_state("No data yet")
    d = df[df["type"] == kind].nlargest(n, "amount")
    if d.empty:
        return empty_state("No data yet")
    label_col = "description" if kind == "Expense" else "payee"
    d = d.copy()
    d["label"] = d[label_col].fillna("")
    empty_mask = d["label"] == ""
    d.loc[empty_mask, "label"] = d.loc[empty_mask, "category"]
    fig = px.bar(d.sort_values("amount"), x="amount", y="label", orientation="h",
                 color_discrete_sequence=[PALETTE[3] if kind == "Expense" else PALETTE[1]])
    return _base_layout(fig, title=f"Largest {kind}s", height=380)

def empty_state(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(size=14, color="#B2BEC3"))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _base_layout(fig, height=280)
