from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fastapi import APIRouter, Depends, HTTPException, status

from appunti_backend.api.deps import get_current_user, get_db
from appunti_backend.core.security import (
    create_access_token,
    ensure_password_strength,
    hash_password,
    verify_password,
)
from appunti_backend.db.models import User
from appunti_backend.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserPublic


router = APIRouter()


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserPublic:
    ensure_password_strength(payload.password)

    existing = db.scalar(
        select(User).where(func.lower(User.username) == payload.username.strip().lower())
    )
    if existing:
        raise HTTPException(status_code=409, detail="Username gia` in uso.")

    if payload.email:
        existing_email = db.scalar(
            select(User).where(func.lower(User.email) == payload.email.strip().lower())
        )
        if existing_email:
            raise HTTPException(status_code=409, detail="Email gia` in uso.")

    user = User(
        username=payload.username.strip(),
        display_name=payload.display_name.strip(),
        email=payload.email.strip().lower() if payload.email else None,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserPublic.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(
        select(User).where(func.lower(User.username) == payload.username.strip().lower())
    )
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide.",
        )

    token, expires_at = create_access_token(user.id)
    return TokenResponse(
        access_token=token,
        expires_at=expires_at,
        user=UserPublic.model_validate(user),
    )


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)) -> UserPublic:
    return UserPublic.model_validate(current_user)
