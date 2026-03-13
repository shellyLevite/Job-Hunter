import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from supabase import Client

from app.api.auth import get_current_user
from app.core.config import settings
from app.db import crud
from app.db.session import get_supabase
from app.schemas import UserRead
from app.services.matcher import get_matching_engine

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


@router.post("/matches/run")
async def run_matching(
    user: UserRead = Depends(get_current_user),
    client: Client = Depends(get_supabase),
):
    """Trigger the matching engine for the current user against all recent jobs."""
    user_id = _get_user_id(client, user.email)
    cv = crud.get_user_cv(client, user_id=user_id)
    if not cv or not cv.get("parsed_content"):
        raise HTTPException(status_code=400, detail="No parsed CV found. Upload a CV first.")

    jobs = crud.get_jobs(client, limit=100)
    if not jobs:
        return {"matched": 0}

    engine = get_matching_engine()
    saved = 0

    for job in jobs:
        score, missing = await engine.match(cv_text=cv["parsed_content"], job=job)
        if score >= settings.MATCH_THRESHOLD:
            crud.upsert_job_match(client, user_id=user_id, job_id=job["id"], score=score, missing_skills=missing)
            saved += 1

    return {"matched": saved, "total_jobs_evaluated": len(jobs), "threshold": settings.MATCH_THRESHOLD}


@router.get("/matches")
def get_matches(
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: UserRead = Depends(get_current_user),
    client: Client = Depends(get_supabase),
):
    """Return this user's job matches, ordered by score descending."""
    user_id = _get_user_id(client, user.email)
    return crud.get_matches_for_user(client, user_id=user_id, min_score=min_score, limit=limit, offset=offset)


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_user_id(client: Client, email: str) -> str:
    user_row = crud.get_user_by_email(client, email)
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    return user_row["id"]

