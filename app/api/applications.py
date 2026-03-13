"""Application Tracking API.

Endpoints:
  POST   /applications            — add a job to tracking (status defaults to "saved")
  GET    /applications            — list all tracked applications for current user
  GET    /applications/{id}       — single application detail
  PATCH  /applications/{id}       — update status / notes / applied_at
  DELETE /applications/{id}       — remove from tracker
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.api.auth import get_current_user
from app.db import crud
from app.db.session import get_supabase
from app.schemas import ApplicationCreate, ApplicationStatus, ApplicationUpdate, UserRead

router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_user_id(client: Client, email: str) -> str:
    user = crud.get_user_by_email(client, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user["id"]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_application(
    body: ApplicationCreate,
    current_user: UserRead = Depends(get_current_user),
    client: Client = Depends(get_supabase),
):
    """Track a new job application."""
    user_id = _get_user_id(client, current_user.email)
    try:
        return crud.create_application(
            client,
            user_id=user_id,
            job_id=body.job_id,
            status=body.status,
            notes=body.notes,
            applied_at=body.applied_at,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/", response_model=List[Dict[str, Any]])
async def list_applications(
    status_filter: Optional[ApplicationStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: UserRead = Depends(get_current_user),
    client: Client = Depends(get_supabase),
):
    """List all tracked applications for the current user."""
    user_id = _get_user_id(client, current_user.email)
    return crud.get_applications_for_user(
        client, user_id=user_id, status=status_filter, limit=limit, offset=offset
    )


@router.get("/{application_id}", response_model=Dict[str, Any])
async def get_application(
    application_id: str,
    current_user: UserRead = Depends(get_current_user),
    client: Client = Depends(get_supabase),
):
    user_id = _get_user_id(client, current_user.email)
    app = crud.get_application_by_id(client, application_id, user_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@router.patch("/{application_id}", response_model=Dict[str, Any])
async def update_application(
    application_id: str,
    body: ApplicationUpdate,
    current_user: UserRead = Depends(get_current_user),
    client: Client = Depends(get_supabase),
):
    """Update status, notes, or applied_at of an application."""
    user_id = _get_user_id(client, current_user.email)
    updated = crud.update_application(
        client,
        application_id=application_id,
        user_id=user_id,
        **body.model_dump(exclude_unset=True),
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Application not found")
    return updated


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: str,
    current_user: UserRead = Depends(get_current_user),
    client: Client = Depends(get_supabase),
):
    user_id = _get_user_id(client, current_user.email)
    deleted = crud.delete_application(client, application_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Application not found")
