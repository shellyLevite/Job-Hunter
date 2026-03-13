from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from supabase import Client


def get_user_by_email(client: Client, email: str) -> Optional[Dict[str, Any]]:
    """Return the first user row matching *email*, or None."""
    response = (
        client.table("users")
        .select("*")
        .eq("email", email)
        .limit(1)
        .execute()
    )
    rows = response.data
    return rows[0] if rows else None


def create_user(client: Client, email: str, hashed_password: str) -> Dict[str, Any]:
    """Insert a new user row and return it."""
    payload = {
        "id": str(uuid.uuid4()),
        "email": email,
        "hashed_password": hashed_password,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    response = client.table("users").insert(payload).execute()
    return response.data[0]


def create_cv_record(
    client: Client,
    user_id: str,
    file_path: str,
    parsed_content: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert a CV row and return it."""
    payload = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "file_path": file_path,
        "parsed_content": parsed_content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    response = client.table("cvs").insert(payload).execute()
    return response.data[0]


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def upsert_job(client: Client, job: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a job or update it if the URL already exists."""
    payload = {
        "id": str(uuid.uuid4()),
        "title": job["title"],
        "company": job["company"],
        "location": job.get("location"),
        "description": job.get("description"),
        "source": job["source"],
        "url": job["url"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    response = (
        client.table("jobs")
        .upsert(payload, on_conflict="url")
        .execute()
    )
    return response.data[0]


def get_jobs(
    client: Client,
    source: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Dict[str, Any]]:
    """Return a paginated list of jobs, optionally filtered by source."""
    query = client.table("jobs").select("*").order("created_at", desc=True).range(offset, offset + limit - 1)
    if source:
        query = query.eq("source", source)
    return query.execute().data


def get_job_by_id(client: Client, job_id: str) -> Optional[Dict[str, Any]]:
    """Return a single job row or None."""
    rows = client.table("jobs").select("*").eq("id", job_id).limit(1).execute().data
    return rows[0] if rows else None

