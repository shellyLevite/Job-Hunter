"""Jobs router.

POST /jobs/search  -- scrape on demand, optionally rank by CV match, cache 15 min
POST /jobs/action  -- persist job to DB + create application (save / apply)
GET  /jobs/{job_id} -- fetch a single stored job (used by Kanban detail view)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client

from backend.api.auth import get_current_user, get_current_user_optional
from backend.core.config import settings
from backend.db import crud
from backend.db.session import get_supabase
from backend.schemas import UserRead
from backend.api.cv import _extract_text  # TODO: relocate to app.services once cv_parser is extracted
from backend.services.matcher import get_matching_engine
from backend.services.scraper.linkedin import LinkedInScraper

router = APIRouter()
logger = logging.getLogger(__name__)

_SCRAPERS = {
    "linkedin": LinkedInScraper,
}

# -- In-memory search result cache --------------------------------------------
_SEARCH_CACHE: dict[str, dict] = {}
_SEARCH_TTL = 900   # 15 minutes
_CACHE_MAX = 256    # max entries; evict the soonest-to-expire entry on overflow


# -- Request schemas ----------------------------------------------------------

class SearchRequest(BaseModel):
    query: str
    location: str
    sources: list[str] = ["linkedin"]
    max_results: int = 25
    posted_within: Optional[str] = None  # LinkedIn f_TPR value e.g. "r86400"


class JobPayload(BaseModel):
    title: str
    company: str
    url: str
    source: str
    location: Optional[str] = None
    description: Optional[str] = None


class ActionRequest(BaseModel):
    action: str  # "save" | "apply"
    job: JobPayload
    notes: Optional[str] = None


# -- Helpers ------------------------------------------------------------------

def _cache_key(req: SearchRequest) -> str:
    raw = f"{req.query.lower()}|{req.location.lower()}|{'_'.join(sorted(req.sources))}|{req.max_results}|{req.posted_within or ''}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(key: str) -> Optional[list]:
    entry = _SEARCH_CACHE.get(key)
    if entry and entry["expires"] > time.monotonic():
        return entry["jobs"]
    return None


def _set_cache(key: str, jobs: list) -> None:
    if len(_SEARCH_CACHE) >= _CACHE_MAX:
        oldest = min(_SEARCH_CACHE, key=lambda k: _SEARCH_CACHE[k]["expires"])
        del _SEARCH_CACHE[oldest]
    _SEARCH_CACHE[key] = {"jobs": jobs, "expires": time.monotonic() + _SEARCH_TTL}


def _get_user_id(client: Client, email: str) -> str:
    user_row = crud.get_user_by_email(client, email)
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")
    return user_row["id"]


# -- Endpoints ----------------------------------------------------------------

@router.post("/search")
async def search_jobs(
    req: SearchRequest,
    client: Client = Depends(get_supabase),
    user: Optional[UserRead] = Depends(get_current_user_optional),
):
    """
    Scrape jobs for the given filters (results cached 15 min).
    If the requesting user has a parsed CV, results are ranked by match score
    and each job is tagged with score / strong_match / missing_skills.
    Without a CV the list is returned unranked and cv_missing=True.
    """
    key = _cache_key(req)
    raw_jobs = _get_cached(key)
    was_cached = raw_jobs is not None

    if raw_jobs is None:
        valid_sources = [s for s in req.sources if s in _SCRAPERS]
        if not valid_sources:
            return {"jobs": [], "cv_missing": True, "cached": False, "total": 0}

        scrapers = [_SCRAPERS[s]() for s in valid_sources]
        scrape_results = await asyncio.gather(
            *[
                asyncio.wait_for(
                    s.scrape(
                        query=req.query,
                        location=req.location,
                        max_results=req.max_results,
                        posted_within=req.posted_within,
                    ),
                    timeout=25,
                )
                for s in scrapers
            ],
            return_exceptions=True,
        )
        raw_jobs = []
        scraper_errors = []
        for source, r in zip(valid_sources, scrape_results):
            if isinstance(r, list):
                raw_jobs.extend(r)
            else:
                scraper_errors.append(f"{source}: {r}")
                logger.error("Scraper %s failed: %s", source, r)

        # Only cache if we actually got results — don't lock in an empty response
        if raw_jobs:
            _set_cache(key, raw_jobs)
        elif scraper_errors:
            raise HTTPException(
                status_code=502,
                detail=f"All scrapers failed: {'; '.join(scraper_errors)}",
            )

    cv_missing = True
    jobs_out = raw_jobs

    if user:
        user_id = _get_user_id(client, user.email)
        cv = crud.get_user_cv(client, user_id=user_id)
        if cv:
            cv_missing = False  # user has a CV row — stop showing the upload banner
            parsed = cv.get("parsed_content")
            # CV row exists but was uploaded before parsing was supported —
            # download from storage and parse now, then backfill the DB row.
            if not parsed and cv.get("file_path"):
                try:
                    file_bytes = client.storage.from_(settings.STORAGE_BUCKET).download(cv["file_path"])
                    suffix = Path(cv["file_path"]).suffix.lower()
                    parsed = _extract_text(file_bytes, suffix) or None
                    if parsed:
                        client.table("cvs").update({"parsed_content": parsed}).eq("id", cv["id"]).execute()
                        logger.info("Backfilled parsed_content for cv %s", cv["id"])
                except Exception as exc:
                    logger.warning("Could not backfill CV text: %s", exc)
            if parsed:
                engine = get_matching_engine()
                cv_skills = await engine.get_cv_skills(cv["id"], parsed)
                jobs_out = await engine.rank_jobs(
                    cv_skills, raw_jobs, threshold=settings.MATCH_THRESHOLD
                )

    return {
        "jobs": jobs_out,
        "cv_missing": cv_missing,
        "cached": was_cached,
        "total": len(jobs_out),
    }


@router.post("/action")
async def job_action(
    req: ActionRequest,
    user: UserRead = Depends(get_current_user),
    client: Client = Depends(get_supabase),
):
    """
    Upsert a job into the DB (by URL) then create an application record.
    Called when the user saves or marks a job as applied from search results.
    """
    if req.action not in ("save", "apply"):
        raise HTTPException(status_code=400, detail="action must be \'save\' or \'apply\'")

    user_id = _get_user_id(client, user.email)
    job_row = crud.upsert_job(client, req.job.model_dump())
    job_status = "saved" if req.action == "save" else "applied"
    try:
        application = crud.create_application(
            client,
            user_id=user_id,
            job_id=job_row["id"],
            status=job_status,
            notes=req.notes,
        )
    except Exception as exc:
        raise HTTPException(status_code=409, detail="This job is already tracked.") from exc
    return application


@router.get("/{job_id}")
def get_job(
    job_id: str,
    client: Client = Depends(get_supabase),
):
    """Return a single stored job by ID (used by the Kanban detail view)."""
    job = crud.get_job_by_id(client, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
