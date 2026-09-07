from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from appunti_backend.core.config import settings


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_password: str) -> bool:
    try:
        salt_hex, digest_hex = stored_password.split("$", 1)
    except ValueError:
        return False

    check = hashlib.scrypt(
        password.encode("utf-8"),
        salt=bytes.fromhex(salt_hex),
        n=2**14,
        r=8,
        p=1,
    )
    return secrets.compare_digest(check.hex(), digest_hex)


def ensure_password_strength(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La password deve contenere almeno 8 caratteri.",
        )


def create_access_token(subject: str) -> tuple[str, datetime]:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": subject,
        "exp": expires_at,
        "iat": datetime.now(UTC),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    return token, expires_at


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o scaduto.",
        ) from exc

    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token privo di subject valido.",
        )
    return subject
