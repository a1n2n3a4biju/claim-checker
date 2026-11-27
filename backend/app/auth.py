"""Sign-in, passwords and access control (owner: M3).

Tokens are signed with TOKEN_SECRET (HMAC-SHA256) and hold the user id, role
and an expiry of 8 hours, so they cannot be changed by the browser.
"""
import base64
import hashlib
import hmac
import json
import os
import re
import time

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import models
from .database import get_db

ROLES = ("claimant", "assessor", "insurer")
TOKEN_HOURS = 8
bearer = HTTPBearer(auto_error=False)


def _secret() -> bytes:
    secret = os.getenv("TOKEN_SECRET", "")
    if not secret:
        raise HTTPException(500, "TOKEN_SECRET is not set on the server (backend/.env)")
    return secret.encode()


# ---------------------------------------------------------------- passwords

def hash_password(password: str) -> str:
    """bcrypt hash; the seed script uses this too."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


# ---------------------------------------------------------------- tokens

def make_token(user: models.User) -> str:
    payload = {"sub": user.id, "role": user.role, "exp": int(time.time()) + TOKEN_HOURS * 3600}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def read_token(token: str) -> dict:
    try:
        body, sig = token.rsplit(".", 1)
        good = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, good):
            raise ValueError("bad signature")
        data = json.loads(base64.urlsafe_b64decode(body))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Invalid sign-in token; please sign in again")
    if data.get("exp", 0) < time.time():
        raise HTTPException(401, "Sign-in expired; please sign in again")
    return data


def user_out(user: models.User) -> dict:
    return {"id": user.id, "name": user.name, "role": user.role, "email": user.email}


# ---------------------------------------------------------------- dependencies

def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                 db: Session = Depends(get_db)) -> models.User:
    if not creds:
        raise HTTPException(401, "Please sign in")
    data = read_token(creds.credentials)
    user = db.get(models.User, data["sub"])
    if not user or user.role != data.get("role"):
        raise HTTPException(401, "This account is no longer valid; please sign in again")
    return user


def require_role(*roles: str):
    """Dependency: the signed-in user must have one of these roles, else 403."""
    def check(user: models.User = Depends(current_user)) -> models.User:
        if user.role not in roles:
            raise HTTPException(403, "You don't have access to this")
        return user
    return check


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8


def register(db: Session, name: str, email: str, password: str) -> dict:
    """Create a new customer account and sign it in.

    Self sign-up always makes a claimant: assessor and insurer accounts can see
    every claim and approve payouts, so they are only created by the team (seed script).
    The password is stored only as a bcrypt hash.
    """
    name, email = " ".join(name.split()), email.strip().lower()
    if not name:
        raise HTTPException(422, "name: enter your full name")
    if not EMAIL_RE.match(email):
        raise HTTPException(422, "email: enter a valid email address")
    if len(password) < MIN_PASSWORD:
        raise HTTPException(422, f"password: use at least {MIN_PASSWORD} characters")
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(400, "An account with this email already exists. Sign in instead.")
    user = models.User(email=email, name=name, role="claimant", password_hash=hash_password(password))
    db.add(user)
    db.commit()
    return {"token": make_token(user), "user": {"id": user.id, "name": user.name, "role": user.role}}


def login(db: Session, email: str, password: str) -> dict:
    user = db.query(models.User).filter(models.User.email == email.strip().lower()).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return {"token": make_token(user), "user": {"id": user.id, "name": user.name, "role": user.role}}
