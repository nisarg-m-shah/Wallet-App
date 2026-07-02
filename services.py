"""
services.py
-----------
All business logic lives here. Streamlit pages should call into these
functions rather than touching the ORM directly - this keeps balance
calculations, validation, and side-effects (like Splitwise bookkeeping)
consistent no matter which page triggers them.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd
from dateutil.relativedelta import relativedelta
from sqlalchemy import func

from database import get_session
from models import (
    Account,
    AccountType,
    BalanceAdjustment,
    Category,
    CategoryKind,
    RecurrenceFrequency,
    RecurringPayment,
    SplitwiseKind,
    SplitwiseRecord,
    Transaction,
    TransactionType,
)


# --------------------------------------------------------------------------- #
# Accounts
# --------------------------------------------------------------------------- #
def get_accounts(user_id: int, include_system: bool = True, include_archived: bool = False) -> list[dict]:
    with get_session() as session:
        q = session.query(Account).filter(Account.user_id == user_id)
        if not include_system:
            q = q.filter(Account.is_system.is_(False))
        if not include_archived:
            q = q.filter(Account.is_archived.is_(False))
        accounts = q.order_by(Account.is_system.asc(), Account.name.asc()).all()
        return [
            dict(
                id=a.id, name=a.name, type=a.type.value, balance=a.balance,
                currency=a.currency, color=a.color, icon=a.icon, notes=a.notes,
                is_system=a.is_system, is_archived=a.is_archived,
            )
            for a in accounts
        ]


def get_account(user_id: int, account_id: int) -> dict | None:
    with get_session() as session:
        a = session.query(Account).filter(Account.id == account_id, Account.user_id == user_id).first()
        if not a:
            return None
        return dict(
            id=a.id, name=a.name, type=a.type.value, balance=a.balance,
            currency=a.currency, color=a.color, icon=a.icon, notes=a.notes,
        )


def get_splitwise_account(user_id: int) -> Account:
    with get_session() as session:
        acc = session.query(Account).filter(
            Account.user_id == user_id, Account.type == AccountType.SPLITWISE
        ).first()
        session.expunge(acc)
        return acc


def create_account(user_id: int, name: str, type_: str, balance: float, currency: str,
                    color: str, icon: str, notes: str) -> tuple[bool, str]:
    if not name.strip():
        return False, "Account name is required."
    with get_session() as session:
        exists = session.query(Account).filter(Account.user_id == user_id, Account.name == name.strip()).first()
        if exists:
            return False, "An account with this name already exists."
        session.add(Account(
            user_id=user_id, name=name.strip(), type=AccountType(type_), balance=balance,
            currency=currency, color=color, icon=icon, notes=notes,
        ))
    return True, "Account created."


def update_account(user_id: int, account_id: int, **fields) -> None:
    with get_session() as session:
        acc = session.query(Account).filter(Account.id == account_id, Account.user_id == user_id).first()
        if not acc:
            return
        for k, v in fields.items():
            if hasattr(acc, k) and v is not None:
                setattr(acc, k, v)


def archive_account(user_id: int, account_id: int) -> None:
    update_account(user_id, account_id, is_archived=True)


def _adjust_balance(session, account_id: int, delta: float) -> None:
    acc = session.query(Account).filter(Account.id == account_id).first()
    if acc:
        acc.balance = round(acc.balance + delta, 2)


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #
def get_categories(user_id: int, kind: str | None = None) -> list[dict]:
    with get_session() as session:
        q = session.query(Category).filter(Category.user_id == user_id)
        if kind:
            q = q.filter(Category.kind == CategoryKind(kind))
        cats = q.order_by(Category.name.asc()).all()
        return [dict(id=c.id, name=c.name, kind=c.kind.value, icon=c.icon) for c in cats]


def create_category(user_id: int, name: str, kind: str, icon: str = "\U0001F4B0") -> tuple[bool, str]:
    if not name.strip():
        return False, "Category name is required."
    with get_session() as session:
        exists = session.query(Category).filter(
            Category.user_id == user_id, Category.name == name.strip(), Category.kind == CategoryKind(kind)
        ).first()
        if exists:
            return False, "This category already exists."
        session.add(Category(user_id=user_id, name=name.strip(), kind=CategoryKind(kind), icon=icon))
    return True, "Category created."


# --------------------------------------------------------------------------- #
# Transaction creation
# --------------------------------------------------------------------------- #
def add_expense(user_id: int, amount: float, description: str, category_id: int | None,
                 date: dt.datetime, payment_mode: str, account_id: int, payee: str = "") -> tuple[bool, str]:
    if amount <= 0:
        return False, "Amount must be greater than zero."

    with get_session() as session:
        acc = session.query(Account).filter(Account.id == account_id, Account.user_id == user_id).first()
        if not acc:
            return False, "Invalid account."

        is_splitwise = payment_mode == "Splitwise"
        txn_account_id = account_id
        if is_splitwise:
            sw_acc = session.query(Account).filter(
                Account.user_id == user_id, Account.type == AccountType.SPLITWISE
            ).first()
            txn_account_id = sw_acc.id

        txn = Transaction(
            user_id=user_id, type=TransactionType.EXPENSE, amount=amount, description=description,
            category_id=category_id, payee=payee, payment_mode=payment_mode,
            account_id=txn_account_id, date=date, is_splitwise=is_splitwise,
        )
        session.add(txn)
        session.flush()

        _adjust_balance(session, txn_account_id, -amount)

        if is_splitwise:
            session.add(SplitwiseRecord(
                user_id=user_id, transaction_id=txn.id, person=payee or "Unknown",
                amount=amount, kind=SplitwiseKind.DEBT, date=date,
                notes=f"Expense: {description}",
            ))

    return True, "Expense added."


def add_income(user_id: int, amount: float, description: str, payer: str, category_id: int | None,
                payment_mode: str, date: dt.datetime, account_id: int) -> tuple[bool, str]:
    if amount <= 0:
        return False, "Amount must be greater than zero."

    with get_session() as session:
        acc = session.query(Account).filter(Account.id == account_id, Account.user_id == user_id).first()
        if not acc:
            return False, "Invalid account."

        txn = Transaction(
            user_id=user_id, type=TransactionType.INCOME, amount=amount, description=description,
            category_id=category_id, payee=payer, payment_mode=payment_mode,
            account_id=account_id, date=date,
        )
        session.add(txn)
        _adjust_balance(session, account_id, amount)

    return True, "Income added."


def add_transfer(user_id: int, amount: float, from_account_id: int, to_account_id: int,
                  date: dt.datetime, notes: str = "") -> tuple[bool, str]:
    if amount <= 0:
        return False, "Amount must be greater than zero."
    if from_account_id == to_account_id:
        return False, "Source and destination accounts must be different."

    with get_session() as session:
        from_acc = session.query(Account).filter(Account.id == from_account_id, Account.user_id == user_id).first()
        to_acc = session.query(Account).filter(Account.id == to_account_id, Account.user_id == user_id).first()
        if not from_acc or not to_acc:
            return False, "Invalid account selection."

        txn = Transaction(
            user_id=user_id, type=TransactionType.TRANSFER, amount=amount, description=notes or "Transfer",
            account_id=from_account_id, to_account_id=to_account_id, date=date, notes=notes,
        )
        session.add(txn)

        _adjust_balance(session, from_account_id, -amount)
        _adjust_balance(session, to_account_id, amount)

        # If this transfer settles a Splitwise liability, mark matching records settled
        sw_acc = session.query(Account).filter(
            Account.user_id == user_id, Account.type == AccountType.SPLITWISE
        ).first()
        if sw_acc and to_account_id == sw_acc.id:
            _settle_splitwise_amount(session, user_id, amount)

    return True, "Transfer completed."


def _settle_splitwise_amount(session, user_id: int, amount: float) -> None:
    """Mark unsettled Splitwise debt records as settled (oldest first) up to `amount`."""
    remaining = amount
    records = session.query(SplitwiseRecord).filter(
        SplitwiseRecord.user_id == user_id,
        SplitwiseRecord.kind == SplitwiseKind.DEBT,
        SplitwiseRecord.settled.is_(False),
    ).order_by(SplitwiseRecord.date.asc()).all()

    for rec in records:
        if remaining <= 0:
            break
        if rec.amount <= remaining:
            remaining -= rec.amount
            rec.settled = True
        else:
            # Partially settle: shrink this record, done.
            rec.amount -= remaining
            remaining = 0


def adjust_balance(user_id: int, account_id: int, new_balance: float, date: dt.datetime,
                    reason: str) -> tuple[bool, str]:
    with get_session() as session:
        acc = session.query(Account).filter(Account.id == account_id, Account.user_id == user_id).first()
        if not acc:
            return False, "Invalid account."

        old_balance = acc.balance
        session.add(BalanceAdjustment(
            user_id=user_id, account_id=account_id, old_balance=old_balance,
            new_balance=new_balance, reason=reason, date=date,
        ))
        acc.balance = new_balance

        txn = Transaction(
            user_id=user_id, type=TransactionType.ADJUSTMENT,
            amount=round(new_balance - old_balance, 2),
            description=f"Balance adjustment: {reason}" if reason else "Balance adjustment",
            account_id=account_id, date=date,
        )
        session.add(txn)

    return True, "Balance adjusted."


def delete_transaction(user_id: int, transaction_id: int) -> tuple[bool, str]:
    """Delete a transaction and reverse its effect on account balances."""
    with get_session() as session:
        txn = session.query(Transaction).filter(
            Transaction.id == transaction_id, Transaction.user_id == user_id
        ).first()
        if not txn:
            return False, "Transaction not found."

        if txn.type == TransactionType.EXPENSE:
            _adjust_balance(session, txn.account_id, txn.amount)
        elif txn.type == TransactionType.INCOME:
            _adjust_balance(session, txn.account_id, -txn.amount)
        elif txn.type == TransactionType.TRANSFER:
            _adjust_balance(session, txn.account_id, txn.amount)
            _adjust_balance(session, txn.to_account_id, -txn.amount)
        elif txn.type == TransactionType.ADJUSTMENT:
            # Reverting an adjustment: subtract the delta that was applied
            _adjust_balance(session, txn.account_id, -txn.amount)

        session.delete(txn)

    return True, "Transaction deleted."


def duplicate_transaction(user_id: int, transaction_id: int) -> tuple[bool, str]:
    with get_session() as session:
        txn = session.query(Transaction).filter(
            Transaction.id == transaction_id, Transaction.user_id == user_id
        ).first()
        if not txn:
            return False, "Transaction not found."

        if txn.type == TransactionType.EXPENSE:
            return add_expense(user_id, txn.amount, txn.description, txn.category_id,
                                dt.datetime.utcnow(), txn.payment_mode, txn.account_id, txn.payee)
        elif txn.type == TransactionType.INCOME:
            return add_income(user_id, txn.amount, txn.description, txn.payee, txn.category_id,
                               txn.payment_mode, dt.datetime.utcnow(), txn.account_id)
        elif txn.type == TransactionType.TRANSFER:
            return add_transfer(user_id, txn.amount, txn.account_id, txn.to_account_id,
                                 dt.datetime.utcnow(), txn.notes)
        return False, "This transaction type cannot be duplicated."


def update_transaction(user_id: int, transaction_id: int, **fields) -> tuple[bool, str]:
    """Edit a transaction's core fields, correctly re-applying balance deltas."""
    ok, msg = delete_transaction(user_id, transaction_id)
    if not ok:
        return ok, msg

    txn_type = fields.pop("type")
    if txn_type == TransactionType.EXPENSE.value:
        return add_expense(
            user_id, fields["amount"], fields.get("description", ""), fields.get("category_id"),
            fields["date"], fields.get("payment_mode", ""), fields["account_id"], fields.get("payee", ""),
        )
    if txn_type == TransactionType.INCOME.value:
        return add_income(
            user_id, fields["amount"], fields.get("description", ""), fields.get("payee", ""),
            fields.get("category_id"), fields.get("payment_mode", ""), fields["date"], fields["account_id"],
        )
    if txn_type == TransactionType.TRANSFER.value:
        return add_transfer(
            user_id, fields["amount"], fields["account_id"], fields["to_account_id"],
            fields["date"], fields.get("notes", ""),
        )
    return False, "Unsupported transaction type for editing."


# --------------------------------------------------------------------------- #
# Transaction retrieval / search / filters
# --------------------------------------------------------------------------- #
def get_transactions_df(user_id: int, search: str = "", type_filter: list[str] | None = None,
                         account_filter: list[int] | None = None, category_filter: list[int] | None = None,
                         date_from: dt.date | None = None, date_to: dt.date | None = None,
                         amount_min: float | None = None, amount_max: float | None = None,
                         limit: int | None = None) -> pd.DataFrame:
    with get_session() as session:
        q = session.query(Transaction).filter(Transaction.user_id == user_id)

        if type_filter:
            q = q.filter(Transaction.type.in_([TransactionType(t) for t in type_filter]))
        if account_filter:
            q = q.filter(
                (Transaction.account_id.in_(account_filter)) | (Transaction.to_account_id.in_(account_filter))
            )
        if category_filter:
            q = q.filter(Transaction.category_id.in_(category_filter))
        if date_from:
            q = q.filter(Transaction.date >= dt.datetime.combine(date_from, dt.time.min))
        if date_to:
            q = q.filter(Transaction.date <= dt.datetime.combine(date_to, dt.time.max))
        if amount_min is not None:
            q = q.filter(Transaction.amount >= amount_min)
        if amount_max is not None:
            q = q.filter(Transaction.amount <= amount_max)

        q = q.order_by(Transaction.date.desc(), Transaction.id.desc())
        if limit:
            q = q.limit(limit)

        rows = []
        for t in q.all():
            rows.append(dict(
                id=t.id, type=t.type.value, amount=t.amount, description=t.description,
                category=t.category.name if t.category else "", category_icon=t.category.icon if t.category else "",
                payee=t.payee, payment_mode=t.payment_mode,
                account=t.account.name if t.account else "", account_id=t.account_id,
                to_account=t.to_account.name if t.to_account else None, to_account_id=t.to_account_id,
                notes=t.notes, date=t.date, is_splitwise=t.is_splitwise,
            ))

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    if search:
        s = search.lower()
        mask = (
            df["description"].str.lower().str.contains(s, na=False)
            | df["category"].str.lower().str.contains(s, na=False)
            | df["payee"].str.lower().str.contains(s, na=False)
            | df["account"].str.lower().str.contains(s, na=False)
            | df["notes"].str.lower().str.contains(s, na=False)
        )
        df = df[mask]

    return df


# --------------------------------------------------------------------------- #
# Recurring payments (automatic payments)
# --------------------------------------------------------------------------- #
def _advance_date(date: dt.datetime, frequency: RecurrenceFrequency) -> dt.datetime:
    if frequency == RecurrenceFrequency.DAILY:
        return date + relativedelta(days=1)
    if frequency == RecurrenceFrequency.WEEKLY:
        return date + relativedelta(weeks=1)
    if frequency == RecurrenceFrequency.MONTHLY:
        return date + relativedelta(months=1)
    return date + relativedelta(years=1)


def add_recurring_payment(user_id: int, amount: float, description: str, frequency: str,
                           first_date: dt.datetime, category_id: int | None, account_id: int) -> tuple[bool, str]:
    if amount <= 0:
        return False, "Amount must be greater than zero."
    with get_session() as session:
        session.add(RecurringPayment(
            user_id=user_id, amount=amount, description=description,
            frequency=RecurrenceFrequency(frequency), first_payment_date=first_date,
            next_due_date=first_date, category_id=category_id, account_id=account_id,
        ))
    return True, "Automatic payment scheduled."


def get_recurring_payments(user_id: int, active_only: bool = True) -> list[dict]:
    with get_session() as session:
        q = session.query(RecurringPayment).filter(RecurringPayment.user_id == user_id)
        if active_only:
            q = q.filter(RecurringPayment.is_active.is_(True))
        rows = q.order_by(RecurringPayment.next_due_date.asc()).all()
        return [
            dict(
                id=r.id, amount=r.amount, description=r.description, frequency=r.frequency.value,
                next_due_date=r.next_due_date, account=r.account.name if r.account else "",
                account_id=r.account_id, category=r.category.name if r.category else "",
                category_id=r.category_id, is_active=r.is_active,
            )
            for r in rows
        ]


def toggle_recurring_payment(user_id: int, payment_id: int, is_active: bool) -> None:
    with get_session() as session:
        r = session.query(RecurringPayment).filter(
            RecurringPayment.id == payment_id, RecurringPayment.user_id == user_id
        ).first()
        if r:
            r.is_active = is_active


def process_due_recurring_payments(user_id: int) -> int:
    """
    Create Expense transactions for every recurring payment whose next_due_date
    has arrived, then roll the due date forward. Call this once per app load.
    Returns the number of transactions generated.
    """
    now = dt.datetime.utcnow()
    generated = 0

    with get_session() as session:
        due = session.query(RecurringPayment).filter(
            RecurringPayment.user_id == user_id,
            RecurringPayment.is_active.is_(True),
            RecurringPayment.next_due_date <= now,
        ).all()

        for r in due:
            # Guard against runaway loops if the app hasn't run in a long time -
            # cap catch-up at 500 occurrences.
            safety = 0
            while r.next_due_date <= now and safety < 500:
                acc = session.query(Account).filter(Account.id == r.account_id).first()
                if acc:
                    txn = Transaction(
                        user_id=user_id, type=TransactionType.EXPENSE, amount=r.amount,
                        description=r.description, category_id=r.category_id,
                        payment_mode="Automatic Payment", account_id=r.account_id,
                        date=r.next_due_date, is_recurring_generated=True, recurring_payment_id=r.id,
                    )
                    session.add(txn)
                    acc.balance = round(acc.balance - r.amount, 2)
                    generated += 1
                r.next_due_date = _advance_date(r.next_due_date, r.frequency)
                safety += 1

    return generated


# --------------------------------------------------------------------------- #
# Splitwise
# --------------------------------------------------------------------------- #
def get_splitwise_summary(user_id: int) -> dict:
    with get_session() as session:
        owed_by_me = session.query(func.coalesce(func.sum(SplitwiseRecord.amount), 0.0)).filter(
            SplitwiseRecord.user_id == user_id, SplitwiseRecord.kind == SplitwiseKind.DEBT,
            SplitwiseRecord.settled.is_(False),
        ).scalar()
        owed_to_me = session.query(func.coalesce(func.sum(SplitwiseRecord.amount), 0.0)).filter(
            SplitwiseRecord.user_id == user_id, SplitwiseRecord.kind == SplitwiseKind.LOAN,
            SplitwiseRecord.settled.is_(False),
        ).scalar()

        records = session.query(SplitwiseRecord).filter(
            SplitwiseRecord.user_id == user_id, SplitwiseRecord.settled.is_(False)
        ).order_by(SplitwiseRecord.date.desc()).all()

        detail = [
            dict(id=r.id, person=r.person, amount=r.amount, kind=r.kind.value, date=r.date, notes=r.notes)
            for r in records
        ]

    return {"i_owe": owed_by_me, "owed_to_me": owed_to_me, "records": detail}


def add_splitwise_loan(user_id: int, person: str, amount: float, notes: str) -> tuple[bool, str]:
    """Record money I lent to someone else (they owe me)."""
    if amount <= 0:
        return False, "Amount must be greater than zero."
    with get_session() as session:
        session.add(SplitwiseRecord(
            user_id=user_id, person=person, amount=amount, kind=SplitwiseKind.LOAN,
            date=dt.datetime.utcnow(), notes=notes,
        ))
    return True, "Loan recorded."


def settle_splitwise_record(user_id: int, record_id: int) -> tuple[bool, str]:
    with get_session() as session:
        rec = session.query(SplitwiseRecord).filter(
            SplitwiseRecord.id == record_id, SplitwiseRecord.user_id == user_id
        ).first()
        if not rec:
            return False, "Record not found."
        rec.settled = True
    return True, "Marked as settled."


# --------------------------------------------------------------------------- #
# Dashboard aggregates
# --------------------------------------------------------------------------- #
@dataclass
class DashboardMetrics:
    net_worth: float
    cash_balance: float
    bank_balance: float
    investment_value: float
    amount_owed: float
    amount_receivable: float
    monthly_income: float
    monthly_expenses: float
    monthly_savings: float


def get_dashboard_metrics(user_id: int) -> DashboardMetrics:
    accounts = get_accounts(user_id, include_system=False)

    cash_balance = sum(a["balance"] for a in accounts if a["type"] == AccountType.CASH.value)
    bank_balance = sum(a["balance"] for a in accounts if a["type"] in (
        AccountType.SAVINGS.value, AccountType.CURRENT.value, AccountType.WALLET.value
    ))
    investment_value = sum(a["balance"] for a in accounts if a["type"] == AccountType.INVESTMENT.value)
    liabilities = sum(a["balance"] for a in accounts if a["type"] in (
        AccountType.CREDIT_CARD.value, AccountType.LIABILITY.value
    ))

    sw = get_splitwise_summary(user_id)

    net_worth = sum(a["balance"] for a in accounts) - liabilities * 2 + sw["owed_to_me"] - sw["i_owe"]
    # NOTE: liability accounts typically store a negative balance already for what you owe;
    # if using positive balances for liabilities, net worth should subtract them once.
    net_worth = sum(a["balance"] for a in accounts if a["type"] not in (
        AccountType.CREDIT_CARD.value, AccountType.LIABILITY.value
    )) - liabilities + sw["owed_to_me"] - sw["i_owe"]

    today = dt.date.today()
    month_start = dt.datetime(today.year, today.month, 1)

    with get_session() as session:
        income = session.query(func.coalesce(func.sum(Transaction.amount), 0.0)).filter(
            Transaction.user_id == user_id, Transaction.type == TransactionType.INCOME,
            Transaction.date >= month_start,
        ).scalar()
        expenses = session.query(func.coalesce(func.sum(Transaction.amount), 0.0)).filter(
            Transaction.user_id == user_id, Transaction.type == TransactionType.EXPENSE,
            Transaction.date >= month_start,
        ).scalar()

    return DashboardMetrics(
        net_worth=round(net_worth, 2), cash_balance=round(cash_balance, 2),
        bank_balance=round(bank_balance, 2), investment_value=round(investment_value, 2),
        amount_owed=round(sw["i_owe"], 2), amount_receivable=round(sw["owed_to_me"], 2),
        monthly_income=round(income, 2), monthly_expenses=round(expenses, 2),
        monthly_savings=round(income - expenses, 2),
    )


def get_net_worth_over_time(user_id: int, days: int = 180) -> pd.DataFrame:
    """
    Reconstruct historical net worth by walking backwards from current account
    balances and undoing each transaction in reverse chronological order.
    """
    accounts = get_accounts(user_id, include_system=False, include_archived=True)
    current_total = sum(a["balance"] for a in accounts if a["type"] not in (
        AccountType.CREDIT_CARD.value, AccountType.LIABILITY.value
    ))
    liabilities_total = sum(a["balance"] for a in accounts if a["type"] in (
        AccountType.CREDIT_CARD.value, AccountType.LIABILITY.value
    ))
    current_net = current_total - liabilities_total

    since = dt.datetime.utcnow() - dt.timedelta(days=days)
    with get_session() as session:
        txns = session.query(Transaction).filter(
            Transaction.user_id == user_id, Transaction.date >= since,
        ).order_by(Transaction.date.desc()).all()

        daily_delta: dict[dt.date, float] = {}
        running = current_net
        for t in txns:
            d = t.date.date()
            if t.type == TransactionType.INCOME:
                daily_delta[d] = daily_delta.get(d, 0) + t.amount
            elif t.type == TransactionType.EXPENSE:
                daily_delta[d] = daily_delta.get(d, 0) - t.amount
            elif t.type == TransactionType.ADJUSTMENT:
                daily_delta[d] = daily_delta.get(d, 0) + t.amount
            # transfers net to zero, no effect on total net worth

    dates = pd.date_range(since.date(), dt.date.today(), freq="D")
    values = []
    running = current_net
    # Walk from today backwards, undoing each day's net delta
    reverse_map = {}
    for d, delta in daily_delta.items():
        reverse_map[d] = reverse_map.get(d, 0) + delta

    net_by_date = {}
    cursor = dt.date.today()
    net_by_date[cursor] = running
    while cursor > since.date():
        running -= reverse_map.get(cursor, 0)
        cursor -= dt.timedelta(days=1)
        net_by_date[cursor] = running

    df = pd.DataFrame(
        [{"date": d, "net_worth": net_by_date.get(d, current_net)} for d in dates]
    )
    return df
