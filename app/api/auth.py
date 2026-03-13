"""Authentication router — Google OAuth 2.0 only.

Flow
────
  1. Browser → GET /auth/google/login
               Redirects to Google's consent screen.
  2. Google  → GET /auth/google/callback?code=...
               Exchanges code for user info, creates/finds user,
               sets httpOnly cookies, redirects to the frontend.

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
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from supabase import Client

from app.core.config import settings
from app.db import crud
from app.db.session import get_supabase
from app.schemas import UserRead

router = APIRouter()

_COOKIE_ACCESS = "access_token"
_COOKIE_REFRESH = "refresh_token"

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


# ── Token helpers ─────────────────────────────────────────────────────────────

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
        path="/auth/refresh",
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


def get_current_user_optional(
    request: Request,
    client: Client = Depends(get_supabase),
) -> Optional[UserRead]:
    """Like get_current_user but returns None instead of raising 401.
    Falls back to the refresh token when the access token is expired,
    so ranking still works after the 30-min access-token window.
    """
    token = request.cookies.get(_COOKIE_ACCESS)
    email: Optional[str] = None

    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            email = payload.get("sub")
        except JWTError:
            pass  # try refresh token below

    # Access token missing or expired — try the refresh token as a fallback
    if email is None:
        refresh = request.cookies.get(_COOKIE_REFRESH)
        if refresh:
            try:
                payload = jwt.decode(refresh, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM])
                email = payload.get("sub")
            except JWTError:
                return None
        else:
            return None

    if email is None:
        return None
    user = crud.get_user_by_email(client, email)
    if user is None:
        return None
    return UserRead(email=user["email"])


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.get("/google/login")
def google_login():
    """Redirect the browser to Google's OAuth consent screen."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    return RedirectResponse(f"{_GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/google/callback")
async def google_callback(
    code: str,
    client: Client = Depends(get_supabase),
):
    """Exchange the authorization code, find/create the user, set cookies, redirect to frontend."""
    async with httpx.AsyncClient() as http:
        token_res = await http.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        token_data = token_res.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Google token exchange failed")

        userinfo_res = await http.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        userinfo = userinfo_res.json()

    email: Optional[str] = userinfo.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Could not retrieve email from Google")

    user = crud.get_user_by_email(client, email)
    if not user:
        user = crud.create_google_user(client, email=email)

    redirect = RedirectResponse(url=settings.FRONTEND_URL, status_code=302)
    _set_auth_cookies(redirect, email)
    return redirect


# ── Common endpoints ──────────────────────────────────────────────────────────

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
