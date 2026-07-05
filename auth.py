"""
auth.py
-------
Minimal, dependency-light email/password authentication.

Passwords are hashed with bcrypt (never stored in plain text). Session state
(who is logged in) is held in Streamlit's `st.session_state`, which is
per-browser-session and cleared on logout.
"""
from __future__ import annotations

import re

import bcrypt

from database import get_session, seed_defaults_for_user
from models import User

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def sign_up(email: str, password: str, display_name: str) -> tuple[bool, str]:
    """Create a new user account. Returns (success, message)."""
    email = email.strip().lower()

    if not EMAIL_RE.match(email):
        return False, "Please enter a valid email address."
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."

    with get_session() as session:
        existing = session.query(User).filter(User.email == email).first()
        if existing:
            return False, "An account with this email already exists."

        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=display_name.strip() or email.split("@")[0],
        )
        session.add(user)
        session.flush()  # populate user.id before we use it
        new_user_id = user.id

    seed_defaults_for_user(new_user_id)
    return True, "Account created successfully."


def log_in(email: str, password: str) -> tuple[bool, str, dict | None]:
    """Validate credentials. Returns (success, message, user_dict)."""
    email = email.strip().lower()

    with get_session() as session:
        user = session.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.password_hash):
            return False, "Invalid email or password.", None

        user_dict = {"id": user.id, "email": user.email, "display_name": user.display_name}

    return True, "Logged in successfully.", user_dict


def get_user_by_id(user_id: int) -> dict | None:
    """Look up a user by id - used to restore a session from a 'remember me' cookie token."""
    with get_session() as session:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        return {"id": user.id, "email": user.email, "display_name": user.display_name}