"""
models.py
---------
SQLAlchemy ORM models for the personal finance tracker.

Every table (except `User` itself) carries a `user_id` foreign key so that
data for multiple users can live in the same SQLite database while staying
completely isolated from one another.
"""
from __future__ import annotations

import datetime as dt
import enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class AccountType(str, enum.Enum):
    CASH = "Cash"
    SAVINGS = "Savings Account"
    CURRENT = "Current Account"
    CREDIT_CARD = "Credit Card"
    INVESTMENT = "Investment"
    WALLET = "Wallet"
    LIABILITY = "Liability"
    SPLITWISE = "Splitwise"  # internal virtual account type


class TransactionType(str, enum.Enum):
    EXPENSE = "Expense"
    INCOME = "Income"
    TRANSFER = "Transfer"
    ADJUSTMENT = "Adjustment"


class CategoryKind(str, enum.Enum):
    EXPENSE = "Expense"
    INCOME = "Income"


class RecurrenceFrequency(str, enum.Enum):
    DAILY = "Daily"
    WEEKLY = "Weekly"
    MONTHLY = "Monthly"
    YEARLY = "Yearly"


class SplitwiseKind(str, enum.Enum):
    DEBT = "Debt"       # I owe someone
    LOAN = "Loan"        # someone owes me


# --------------------------------------------------------------------------- #
# User
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    accounts: Mapped[list["Account"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    categories: Mapped[list["Category"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #
class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[AccountType] = mapped_column(Enum(AccountType))
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    color: Mapped[str] = mapped_column(String(20), default="#6C5CE7")
    icon: Mapped[str] = mapped_column(String(10), default="\U0001F4B3")  # 💳
    notes: Mapped[str] = mapped_column(Text, default="")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)  # e.g. the Splitwise virtual account
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="accounts")

    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_account_user_name"),)


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #
class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[CategoryKind] = mapped_column(Enum(CategoryKind))
    icon: Mapped[str] = mapped_column(String(10), default="\U0001F4B0")  # 💰
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="categories")

    __table_args__ = (UniqueConstraint("user_id", "name", "kind", name="uq_category_user_name_kind"),)


# --------------------------------------------------------------------------- #
# Transactions
# --------------------------------------------------------------------------- #
class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType), index=True)
    amount: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(String(255), default="")

    # Expense / Income specific
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    payee: Mapped[str] = mapped_column(String(120), default="")  # payee (expense) or payer (income)
    payment_mode: Mapped[str] = mapped_column(String(50), default="")

    # Account linkage
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    # Only populated for Transfers (destination account)
    to_account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)

    notes: Mapped[str] = mapped_column(Text, default="")
    date: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    # Set true when this expense/income was routed through the Splitwise virtual account
    is_splitwise: Mapped[bool] = mapped_column(Boolean, default=False)
    # Set true when this transaction was auto-generated from a RecurringPayment
    is_recurring_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    recurring_payment_id: Mapped[int | None] = mapped_column(ForeignKey("recurring_payments.id"), nullable=True)

    user: Mapped["User"] = relationship(back_populates="transactions")
    account: Mapped["Account"] = relationship(foreign_keys=[account_id])
    to_account: Mapped["Account"] = relationship(foreign_keys=[to_account_id])
    category: Mapped["Category"] = relationship()


# --------------------------------------------------------------------------- #
# Recurring Payments (Automatic Payments)
# --------------------------------------------------------------------------- #
class RecurringPayment(Base):
    __tablename__ = "recurring_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    amount: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(String(255))
    frequency: Mapped[RecurrenceFrequency] = mapped_column(Enum(RecurrenceFrequency))
    first_payment_date: Mapped[dt.date] = mapped_column(DateTime)
    next_due_date: Mapped[dt.date] = mapped_column(DateTime)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    account: Mapped["Account"] = relationship()
    category: Mapped["Category"] = relationship()


# --------------------------------------------------------------------------- #
# Balance Adjustments
# --------------------------------------------------------------------------- #
class BalanceAdjustment(Base):
    __tablename__ = "balance_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    old_balance: Mapped[float] = mapped_column(Float)
    new_balance: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(String(255), default="")
    date: Mapped[dt.datetime] = mapped_column(DateTime)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    account: Mapped["Account"] = relationship()


# --------------------------------------------------------------------------- #
# Splitwise Records
# --------------------------------------------------------------------------- #
class SplitwiseRecord(Base):
    __tablename__ = "splitwise_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    transaction_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)
    person: Mapped[str] = mapped_column(String(120))
    amount: Mapped[float] = mapped_column(Float)
    kind: Mapped[SplitwiseKind] = mapped_column(Enum(SplitwiseKind))
    settled: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    date: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    transaction: Mapped["Transaction"] = relationship()


# --------------------------------------------------------------------------- #
# Settings (key/value per user)
# --------------------------------------------------------------------------- #
class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    key: Mapped[str] = mapped_column(String(120))
    value: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_setting_user_key"),)
