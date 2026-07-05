"""
utils.py
--------
Small stateless helper functions shared across pages: currency formatting,
"Today / Yesterday" style date grouping for the transaction timeline, and
UI constant palettes (colors/icons) used in account & category pickers.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

IST_OFFSET = dt.timedelta(hours=5, minutes=30)


def now_ist() -> dt.datetime:
    """Current time in IST. The server (and dt.datetime.now()) runs in UTC on
    Streamlit Cloud, so every 'current time' default in the app should go
    through this instead, or date/time pickers default to the wrong time."""
    return dt.datetime.utcnow() + IST_OFFSET

CURRENCY_SYMBOLS = {"INR": "\u20B9", "USD": "$", "EUR": "\u20AC", "GBP": "\u00A3"}

ACCOUNT_COLORS = [
    "#6C5CE7", "#00B894", "#0984E3", "#E17055", "#FDCB6E",
    "#D63031", "#00CEC9", "#E84393", "#2D3436", "#0057B8",
]

ACCOUNT_ICONS = ["\U0001F4B3", "\U0001F3E6", "\U0001F4B5", "\U0001F4B0", "\U0001F4C8",
                 "\U0001F4B4", "\U0001F3E2", "\U0001F45B", "\U0001FA99"]

TRANSACTION_TYPE_ICONS = {
    "Expense": "\U0001F4B8",
    "Income": "\U0001F4B0",
    "Transfer": "\U0001F504",
    "Adjustment": "\U00002696\U0000FE0F",
}

PAYMENT_MODES = ["Cash", "UPI", "Splitwise", "Debit Card", "Netbanking"]
DEFAULT_PAYERS = ["Mom", "Dad", "Pravis Consulting", "Aaryann Mavani", "Other"]


def format_currency(amount: float, currency: str = "INR") -> str:
    symbol = CURRENCY_SYMBOLS.get(currency, currency + " ")
    sign = "-" if amount < 0 else ""
    return f"{sign}{symbol}{abs(amount):,.2f}"


def format_signed_currency(amount: float, currency: str = "INR") -> str:
    symbol = CURRENCY_SYMBOLS.get(currency, currency + " ")
    sign = "+" if amount >= 0 else "-"
    return f"{sign}{symbol}{abs(amount):,.2f}"


def day_bucket_label(date: dt.datetime) -> str:
    """Return 'Today', 'Yesterday', or a formatted date for grouping the timeline."""
    d = date.date() if isinstance(date, dt.datetime) else date
    today = dt.date.today()
    if d == today:
        return "Today"
    if d == today - dt.timedelta(days=1):
        return "Yesterday"
    if d.year == today.year:
        return d.strftime("%A, %d %b")
    return d.strftime("%d %b %Y")


def group_transactions_by_day(df: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    """Group an already-sorted (desc by date) transactions dataframe into day buckets."""
    if df.empty:
        return []
    df = df.copy()
    df["_bucket"] = df["date"].apply(day_bucket_label)
    groups = []
    seen = []
    for bucket in df["_bucket"]:
        if bucket not in seen:
            seen.append(bucket)
    for bucket in seen:
        groups.append((bucket, df[df["_bucket"] == bucket]))
    return groups


def transaction_line_icon(row: dict) -> str:
    """Pick a display icon for a transaction row: category icon takes priority."""
    if row.get("category_icon"):
        return row["category_icon"]
    return TRANSACTION_TYPE_ICONS.get(row.get("type", ""), "\U0001F4B5")


def month_bounds(reference: dt.date | None = None) -> tuple[dt.date, dt.date]:
    reference = reference or dt.date.today()
    start = reference.replace(day=1)
    if reference.month == 12:
        end = reference.replace(year=reference.year + 1, month=1, day=1) - dt.timedelta(days=1)
    else:
        end = reference.replace(month=reference.month + 1, day=1) - dt.timedelta(days=1)
    return start, end
