"""
session_auth.py
----------------
Lightweight signed-token "remember me" session so you aren't forced to log
in again every time the browser tab reloads. Streamlit's `st.session_state`
alone resets on every full page reload - there's no built-in fix for this,
so the standard workaround is a signed token stored in a browser cookie,
verified on load.

Note: this does NOT use encryption, only an HMAC signature - the token is
not secret (it's just a user id + expiry), but it can't be forged or
tampered with without knowing SESSION_SECRET.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import streamlit as st

TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days


def _get_secret() -> bytes:
    try:
        key = st.secrets.get("SESSION_SECRET")
    except Exception:
        key = None
    if not key:
        # Local-dev fallback: sessions won't survive an app restart, which is
        # fine locally. On a real deployment, set SESSION_SECRET in Secrets
        # so "remember me" tokens stay valid across reboots.
        key = "dev-only-insecure-secret-change-in-production"
    return key.encode("utf-8")


def create_token(user_id: int) -> str:
    payload = {"uid": user_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    payload_bytes = json.dumps(payload).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8")
    signature = hmac.new(_get_secret(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_token(token: str) -> int | None:
    try:
        payload_b64, signature = token.split(".")
        expected_sig = hmac.new(_get_secret(), payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")))
        if payload["exp"] < time.time():
            return None
        return payload["uid"]
    except Exception:
        return None