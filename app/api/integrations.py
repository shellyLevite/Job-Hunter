"""Gmail integration endpoints.

GET  /integrations/gmail/status   — is Gmail connected for current user?
GET  /integrations/gmail/preview  — fetch & parse inbox, return preview list (nothing saved)
POST /integrations/gmail/import   — save user-confirmed items as application records
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.api.auth import get_current_user
from app.db import crud
from app.db.session import get_supabase
from app.schemas import GmailImportRequest, GmailPreviewItem, UserRead
from app.services.gmail_parser import fetch_gmail_preview

router = APIRouter()


def _get_user(client: Client, email: str) -> Dict[str, Any]:
    user = crud.get_user_by_email(client, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/gmail/status")
async def gmail_status(
    current_user: UserRead = Depends(get_current_user),
    client: Client = Depends(get_supabase),
):
    """Return whether the current user has Gmail connected.

    Uses the decryption helper so the result is consistent with whether
    the token can actually be used — a token that can't be decrypted
    (e.g. stored before encryption was added) is treated as not connected.
    """
    user = _get_user(client, current_user.email)
    refresh_token = crud.get_user_gmail_refresh_token(client, user["id"])
    return {"connected": bool(refresh_token)}


@router.get("/gmail/preview", response_model=List[GmailPreviewItem])
async def gmail_preview(
    max_results: int = Query(50, ge=1, le=100),
    current_user: UserRead = Depends(get_current_user),
    client: Client = Depends(get_supabase),
):
    """Fetch job-related emails and return a parsed preview list.

    Items already imported are flagged with ``already_imported=true``.
    Nothing is saved — the user reviews and confirms before importing.
    """
    user = _get_user(client, current_user.email)
    refresh_token = crud.get_user_gmail_refresh_token(client, user["id"])
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gmail not connected. Visit /auth/google/gmail-connect first.",
        )

    imported_ids = crud.get_imported_gmail_message_ids(client, user["id"])

    try:
        preview = await fetch_gmail_preview(refresh_token, max_results=max_results)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    for item in preview:
        item["already_imported"] = item["message_id"] in imported_ids

    return preview


@router.post("/gmail/import", status_code=status.HTTP_201_CREATED)
async def gmail_import(
    body: GmailImportRequest,
    current_user: UserRead = Depends(get_current_user),
    client: Client = Depends(get_supabase),
):
    """Save user-confirmed parsed emails as application records.

    Skips items whose ``gmail_message_id`` was already imported (idempotent).
    """
    user = _get_user(client, current_user.email)
    user_id = user["id"]

    imported_ids = crud.get_imported_gmail_message_ids(client, user_id)
    skipped = [it.message_id for it in body.items if it.message_id in imported_ids]

    items_dicts = [
        {
            "message_id": it.message_id,
            "company": it.company,
            "role": it.role,
            "status": it.status,
            "email_date": it.email_date,
        }
        for it in body.items
    ]
    created = crud.bulk_import_gmail_applications(
        client, user_id=user_id, items=items_dicts, skip_message_ids=imported_ids
    )

    return {
        "created": len(created),
        "skipped": len(skipped),
        "application_ids": created,
    }
