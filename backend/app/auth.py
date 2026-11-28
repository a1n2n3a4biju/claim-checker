import base64
import hashlib
import hmac
import json
import os
import time

import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from . import models
from .database import get_db

load_dotenv()
TOKEN_SECRET = os.getenv("TOKEN_SECRET", "")
TOKEN_HOURS = 8
bearer = HTTPBearer(auto_error=False)


# ---------- passwords ----------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ---------- tokens ----------

def make_token(user: models.User) -> str:
    body = base64.urlsafe_b64encode(json.dumps(
        {"uid": user.id, "role": user.role, "exp": time.time() + TOKEN_HOURS * 3600}
    ).encode()).decode()
    sig = hmac.new(TOKEN_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                 db: Session = Depends(get_db)) -> models.User:
    if not creds:
        raise HTTPException(401, "Please sign in")
    try:
        body, sig = creds.credentials.rsplit(".", 1)
        good = hmac.new(TOKEN_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
        data = json.loads(base64.urlsafe_b64decode(body))
    except Exception:
        raise HTTPException(401, "Invalid sign-in token")
    if not hmac.compare_digest(sig, good):
        raise HTTPException(401, "Invalid sign-in token")
    if data["exp"] < time.time():
        raise HTTPException(401, "Sign-in expired; please sign in again")
    user = db.get(models.User, data["uid"])
    if not user:
        raise HTTPException(401, "This account no longer exists")
    return user


def require_role(*roles: str):
    """Use as: user = Depends(require_role("insurer"))"""
    def checker(user: models.User = Depends(current_user)) -> models.User:
        if user.role not in roles:
            raise HTTPException(403, "You don't have access to this")
        return user
    return checker