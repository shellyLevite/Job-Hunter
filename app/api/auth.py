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

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from supabase import Client

from app.core.config import settings
from app.db import crud
from app.db.session import get_supabase
from app.schemas import UserRead

logger = logging.getLogger(__name__)
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

    Note: does NOT fall back to the refresh token.  The refresh cookie is
    path-restricted to /auth/refresh by the browser, so using it here would
    be dead code and would violate the principle of least privilege.
    """
    token = request.cookies.get(_COOKIE_ACCESS)
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            return None
    except JWTError:
        return None
    user = crud.get_user_by_email(client, email)
    return UserRead(email=user["email"]) if user else None


# ── Google OAuth ──────────────────────────────────────────────────────────────

@router.get("/google/login")
def google_login():
    """Redirect the browser to Google's OAuth consent screen."""
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
        "state": state,
    }
    redirect = RedirectResponse(f"{_GOOGLE_AUTH_URL}?{urlencode(params)}")
    redirect.set_cookie(
        key="oauth_state",
        value=state,
        httponly=True,
        secure=settings.SECURE_COOKIES,
        samesite="lax",
        max_age=600,  # 10 minutes — enough to complete the OAuth dance
    )
    return redirect


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    request: Request,
    client: Client = Depends(get_supabase),
):
    """Exchange the authorization code, find/create the user, set cookies, redirect to frontend."""
    stored_state = request.cookies.get("oauth_state")
    if not stored_state or not secrets.compare_digest(stored_state, state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state — possible CSRF attack")

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

    try:
        user = crud.get_user_by_email(client, email)
        if not user:
            user = crud.create_google_user(client, email=email)
    except Exception as exc:
        logger.exception("Unexpected error in google_callback while accessing DB: %s", exc)
        r = RedirectResponse(url=f"{settings.FRONTEND_URL}?auth_error=server_error", status_code=302)
        r.delete_cookie("oauth_state")
        return r

    redirect = RedirectResponse(url=settings.FRONTEND_URL, status_code=302)
    _set_auth_cookies(redirect, email)
    redirect.delete_cookie("oauth_state")
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


# ── Gmail OAuth ────────────────────────────────────────────────────────────

_GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


@router.get("/google/gmail-connect")
def gmail_connect(
    request: Request,
    _: UserRead = Depends(get_current_user),
):
    """Redirect the browser to Google to grant Gmail read-only access.

    Requires the user to be logged in (verified via the access_token cookie).
    """
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_GMAIL_REDIRECT_URI,
        "response_type": "code",
        "scope": _GMAIL_SCOPE,
        "access_type": "offline",
        "prompt": "consent",  # always ask so Google issues a refresh token
        "state": state,
    }
    redirect = RedirectResponse(f"{_GOOGLE_AUTH_URL}?{urlencode(params)}")
    redirect.set_cookie(
        key="gmail_oauth_state",
        value=state,
        httponly=True,
        secure=settings.SECURE_COOKIES,
        samesite="lax",
        max_age=600,
    )
    return redirect


@router.get("/google/gmail-callback")
async def gmail_callback(
    code: str,
    state: str,
    request: Request,
    client: Client = Depends(get_supabase),
):
    """Exchange the Gmail authorization code, store the refresh token, redirect to frontend."""
    stored_state = request.cookies.get("gmail_oauth_state")
    if not stored_state or not secrets.compare_digest(stored_state, state):
        # Do NOT delete the cookie here — this could be a CSRF probe from a third party.
        raise HTTPException(status_code=400, detail="Invalid OAuth state — possible CSRF attack")

    try:
        # Authenticate the user BEFORE touching Google's API to fail fast.
        current_user = get_current_user_optional(request, client)
        if not current_user:
            r = RedirectResponse(url=f"{settings.FRONTEND_URL}?gmail_error=unauthenticated", status_code=302)
            r.delete_cookie("gmail_oauth_state")
            return r

        async with httpx.AsyncClient() as http:
            token_res = await http.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_GMAIL_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            token_data = token_res.json()

        refresh_token_value = token_data.get("refresh_token")
        if not refresh_token_value:
            logger.warning("Gmail OAuth: no refresh_token returned. Google response: %s", token_data)
            r = RedirectResponse(
                url=f"{settings.FRONTEND_URL}?gmail_error=no_refresh_token", status_code=302
            )
            r.delete_cookie("gmail_oauth_state")
            return r

        user = crud.get_user_by_email(client, current_user.email)
        if not user:
            r = RedirectResponse(url=f"{settings.FRONTEND_URL}?gmail_error=user_not_found", status_code=302)
            r.delete_cookie("gmail_oauth_state")
            return r

        crud.update_user_gmail_token(client, user["id"], refresh_token_value)

        redirect = RedirectResponse(
            url=f"{settings.FRONTEND_URL}?gmail_connected=1", status_code=302
        )
        redirect.delete_cookie("gmail_oauth_state")
        return redirect

    except Exception as exc:
        logger.exception("Unexpected error in gmail_callback: %s", exc)
        r = RedirectResponse(
            url=f"{settings.FRONTEND_URL}?gmail_error=server_error", status_code=302
        )
        r.delete_cookie("gmail_oauth_state")
        return r
