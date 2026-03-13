from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.api.auth import get_current_user
from app.db import crud
from app.db.session import get_supabase

router = APIRouter()


@router.get("/")
def list_jobs(
    source: Optional[str] = Query(None, description="Filter by source: linkedin, indeed"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    client: Client = Depends(get_supabase),
):
    """Return paginated job listings."""
    return crud.get_jobs(client, source=source, limit=limit, offset=offset)


@router.get("/matches")
def get_matches(_user=Depends(get_current_user)):
    """Placeholder — job matching engine is implemented in phase 4."""
    return {"matches": []}


@router.get("/{job_id}")
def get_job(
    job_id: str,
    client: Client = Depends(get_supabase),
):
    """Return a single job by ID."""
    job = crud.get_job_by_id(client, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

