"""Authentication router.

Tokens are issued as httpOnly cookies so they are never accessible from
JavaScript, eliminating the XSS-based token-theft vector.

Cookie layout
─────────────
  access_token   Short-lived (ACCESS_TOKEN_EXPIRE_MINUTES).  Sent on every request.
  refresh_token  Long-lived  (REFRESH_TOKEN_EXPIRE_DAYS).    Sent only to /auth/refresh.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from supabase import Client

from app.core.config import settings
from app.db import crud
from app.db.session import get_supabase
from app.schemas import UserCreate, UserRead

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_COOKIE_ACCESS = "access_token"
_COOKIE_REFRESH = "refresh_token"


# ── Token helpers ─────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_access_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": email, "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _create_refresh_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": email, "exp": expire}, settings.REFRESH_SECRET_KEY, algorithm=settings.ALGORITHM)


def _set_auth_cookies(response: Response, email: str) -> None:
    """Write both access and refresh cookies on the response."""
    response.set_cookie(
        key=_COOKIE_ACCESS,
        value=_create_access_token(email),
        httponly=True,
        secure=settings.SECURE_COOKIES,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key=_COOKIE_REFRESH,
        value=_create_refresh_token(email),
        httponly=True,
        secure=settings.SECURE_COOKIES,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86_400,
        path="/auth/refresh",  # browser only sends this cookie to /auth/refresh
    )


# ── Dependency ────────────────────────────────────────────────────────────────

def get_current_user(
    request: Request,
    client: Client = Depends(get_supabase),
) -> UserRead:
    """Read the access-token cookie and return the authenticated user."""
    token = request.cookies.get(_COOKIE_ACCESS)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = crud.get_user_by_email(client, email)
    if user is None:
        raise credentials_exception
    return UserRead(email=user["email"])


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, response: Response, client: Client = Depends(get_supabase)):
    if crud.get_user_by_email(client, user.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    hashed_password = _hash_password(user.password)
    created = crud.create_user(client, email=user.email, hashed_password=hashed_password)
    _set_auth_cookies(response, created["email"])
    return UserRead(email=created["email"])


@router.post("/login", response_model=UserRead)
def login(user: UserCreate, response: Response, client: Client = Depends(get_supabase)):
    stored = crud.get_user_by_email(client, user.email)
    if not stored or not _verify_password(user.password, stored["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    _set_auth_cookies(response, stored["email"])
    return UserRead(email=stored["email"])


@router.get("/me", response_model=UserRead)
def me(current_user: UserRead = Depends(get_current_user)):
    """Return the currently authenticated user (used to verify session on page load)."""
    return current_user


@router.post("/refresh", response_model=UserRead)
def refresh_token(request: Request, response: Response, client: Client = Depends(get_supabase)):
    """Issue a new access-token cookie using the long-lived refresh-token cookie."""
    token = request.cookies.get(_COOKIE_REFRESH)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token. Please log in again.",
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = crud.get_user_by_email(client, email)
    if not user:
        raise credentials_exception

    _set_auth_cookies(response, email)
    return UserRead(email=email)


@router.post("/logout")
def logout(response: Response):
    """Clear both auth cookies."""
    response.delete_cookie(_COOKIE_ACCESS)
    response.delete_cookie(_COOKIE_REFRESH, path="/auth/refresh")
    return {"message": "Logged out"}
