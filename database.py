"""
database.py
------------
Central place for the SQLAlchemy engine, session factory, and one-time
schema creation. Also seeds sensible per-user defaults (accounts,
categories, the Splitwise virtual account) the first time a user signs up.

Deployment note
----------------
Streamlit Community Cloud's filesystem is EPHEMERAL - anything written to
local disk (including a SQLite file) is wiped on every reboot/redeploy.
So in production this connects to a hosted Postgres database instead,
configured via `st.secrets["DATABASE_URL"]` (Settings -> Secrets in the
Streamlit Cloud dashboard). Free options that work well: Supabase, Neon,
or Railway Postgres.

For local development, if no DATABASE_URL secret/env var is found, it
transparently falls back to a local SQLite file so `streamlit run app.py`
still works with zero setup.
"""
from __future__ import annotations

import os
from contextlib import contextmanager

import streamlit as st
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from models import (
    Account,
    AccountType,
    Base,
    Category,
    CategoryKind,
)


def _get_database_url() -> str | None:
    """Look for a Postgres connection string in Streamlit secrets, then env vars."""
    try:
        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
        if "connections" in st.secrets and "postgres" in st.secrets["connections"]:
            return st.secrets["connections"]["postgres"]["url"]
    except (FileNotFoundError, KeyError, AttributeError):
        pass  # No secrets.toml present (e.g. fresh local clone) - that's fine.
    return os.environ.get("DATABASE_URL")


def _build_engine():
    database_url = _get_database_url()

    if database_url:
        # Normalize the common "postgres://" scheme (used by Supabase/Railway/Heroku)
        # to the "postgresql+psycopg2://" driver SQLAlchemy expects.
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)

        return create_engine(
            database_url,
            pool_pre_ping=True,   # avoids "server closed the connection" after idle periods
            pool_recycle=300,     # recycle connections every 5 min (hosted PG free tiers idle-timeout)
        ), "postgres"

    # --- Local dev fallback: SQLite ---
    db_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "finance_tracker.db")
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return engine, "sqlite"


engine, DB_BACKEND = _build_engine()

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create all tables if they do not already exist."""
    Base.metadata.create_all(engine)


@contextmanager
def get_session():
    """Context-managed session: commits on success, rolls back on error."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# --------------------------------------------------------------------------- #
# Default data seeded for every new user
# --------------------------------------------------------------------------- #
DEFAULT_ACCOUNTS = [
    dict(name="Cash", type=AccountType.CASH, color="#00B894", icon="\U0001F4B5"),
    dict(name="HDFC Bank", type=AccountType.SAVINGS, color="#0057B8", icon="\U0001F3E6"),
    dict(name="Kotak Mahindra Bank", type=AccountType.SAVINGS, color="#ED1C24", icon="\U0001F3E6"),
]

EXPENSE_CATEGORIES = [
    ("Housing", "\U0001F3E0"),
    ("Food", "\U0001F374"),
    ("Utilities", "\U0001F4A1"),
    ("Party / Recreation", "\U0001F389"),
    ("Entertainment & Leisure", "\U0001F3AC"),
    ("Investment", "\U0001F4C8"),
    ("Transport", "\U0001F697"),
    ("Personal Care", "\U0001F9F4"),
    ("Clothing", "\U0001F455"),
    ("Debt Repayment", "\U0001F4B8"),
    ("Streaming", "\U0001F4FA"),
    ("Groceries", "\U0001F6D2"),
]

INCOME_CATEGORIES = [
    ("Salary", "\U0001F4BC"),
    ("Parents", "\U0001F46A"),
    ("Friends", "\U0001F91D"),
    ("Refund", "\U0001F4B1"),
    ("Interest", "\U0001F3E6"),
    ("Other", "\U00002728"),
]

DEFAULT_PAYERS = ["Mom", "Dad", "Pravis Consulting", "Aaryann Mavani"]
EXPENSE_PAYMENT_MODES = ["Cash", "UPI", "Splitwise", "Debit Card", "Netbanking"]
RECURRING_FREQUENCIES = ["Daily", "Weekly", "Monthly", "Yearly"]


def seed_defaults_for_user(user_id: int) -> None:
    """Populate default accounts + categories for a freshly created user."""
    with get_session() as session:
        for acc in DEFAULT_ACCOUNTS:
            session.add(Account(user_id=user_id, balance=0.0, currency="INR", notes="", **acc))

        # Virtual Splitwise account (system account, not shown in normal account pickers)
        session.add(
            Account(
                user_id=user_id,
                name="Splitwise",
                type=AccountType.SPLITWISE,
                balance=0.0,
                currency="INR",
                color="#1CC29F",
                icon="\U0001F91D",
                notes="Virtual account tracking Splitwise debts & loans",
                is_system=True,
            )
        )

        for name, icon in EXPENSE_CATEGORIES:
            session.add(Category(user_id=user_id, name=name, kind=CategoryKind.EXPENSE, icon=icon, is_system=True))

        for name, icon in INCOME_CATEGORIES:
            session.add(Category(user_id=user_id, name=name, kind=CategoryKind.INCOME, icon=icon, is_system=True))
