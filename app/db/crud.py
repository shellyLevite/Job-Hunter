from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from cryptography.fernet import Fernet
from supabase import Client

from app.core.config import settings

logger = logging.getLogger(__name__)


def _fernet() -> Fernet:
    """Return a Fernet instance using the configured encryption key."""
    return Fernet(settings.GMAIL_TOKEN_ENCRYPTION_KEY.encode())


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


def create_google_user(client: Client, email: str) -> Dict[str, Any]:
    """Insert a new user row for a Google-authenticated user (no password)."""
    return create_user(client, email=email, hashed_password="")


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
    """Return the existing job row for this URL, inserting a new one if needed.

    A try/except wraps the INSERT to handle the race condition where two
    concurrent requests both pass the existence check; only one INSERT wins
    the unique URL constraint — the loser fetches and returns the winner's row.
    """
    existing = (
        client.table("jobs").select("*").eq("url", job["url"]).limit(1).execute().data
    )
    if existing:
        return existing[0]
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
    try:
        return client.table("jobs").insert(payload).execute().data[0]
    except Exception:
        # Race condition: a concurrent request inserted the same URL first.
        rows = client.table("jobs").select("*").eq("url", job["url"]).limit(1).execute().data
        if rows:
            return rows[0]
        raise


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


# ---------------------------------------------------------------------------
# Job Matches
# ---------------------------------------------------------------------------

def get_user_cv(client: Client, user_id: str) -> Optional[Dict[str, Any]]:
    """Return the most recent CV for a user, or None."""
    rows = (
        client.table("cvs")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

_VALID_STATUSES = {"saved", "applied", "interview", "rejected", "offer"}


def create_application(
    client: Client,
    user_id: str,
    job_id: str,
    status: str = "saved",
    notes: Optional[str] = None,
    applied_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Add a job to the user's application tracker."""
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "job_id": job_id,
        "status": status if status in _VALID_STATUSES else "saved",
        "notes": notes,
        "applied_at": applied_at,
        "created_at": now,
        "updated_at": now,
    }
    return client.table("applications").insert(payload).execute().data[0]


def get_applications_for_user(
    client: Client,
    user_id: str,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Dict[str, Any]]:
    """Return a user's applications joined with job data, newest first."""
    q = (
        client.table("applications")
        .select("*, jobs(*)")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .range(offset, offset + limit - 1)
    )
    if status:
        q = q.eq("status", status)
    return q.execute().data


def get_application_by_id(
    client: Client,
    application_id: str,
    user_id: str,
) -> Optional[Dict[str, Any]]:
    """Return a single application owned by user_id, or None."""
    rows = (
        client.table("applications")
        .select("*, jobs(*)")
        .eq("id", application_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data
    )
    return rows[0] if rows else None


def update_application(
    client: Client,
    application_id: str,
    user_id: str,
    **fields,
) -> Optional[Dict[str, Any]]:
    """Patch allowed fields on an application; returns updated row or None."""
    allowed = {"status", "notes", "applied_at"}
    patch = {k: v for k, v in fields.items() if k in allowed}
    if not patch:
        return get_application_by_id(client, application_id, user_id)
    patch["updated_at"] = datetime.now(timezone.utc).isoformat()
    rows = (
        client.table("applications")
        .update(patch)
        .eq("id", application_id)
        .eq("user_id", user_id)
        .execute()
        .data
    )
    return rows[0] if rows else None


def delete_application(
    client: Client,
    application_id: str,
    user_id: str,
) -> bool:
    """Delete an application; returns True if a row was deleted."""
    rows = (
        client.table("applications")
        .delete()
        .eq("id", application_id)
        .eq("user_id", user_id)
        .execute()
        .data
    )
    return len(rows) > 0


# ---------------------------------------------------------------------------
# Gmail Integration
# ---------------------------------------------------------------------------


def update_user_gmail_token(client: Client, user_id: str, refresh_token: str) -> None:
    """Encrypt and store the Google OAuth refresh token (Gmail read access) for the user."""
    encrypted = _fernet().encrypt(refresh_token.encode()).decode()
    client.table("users").update(
        {"google_refresh_token": encrypted}
    ).eq("id", user_id).execute()


def clear_user_gmail_token(client: Client, user_id: str) -> None:
    """Clear a user's stored Gmail refresh token."""
    client.table("users").update({"google_refresh_token": None}).eq("id", user_id).execute()


def get_user_gmail_refresh_token(client: Client, user_id: str) -> Optional[str]:
    """Fetch and decrypt the Gmail OAuth refresh token for the user, or None."""
    rows = (
        client.table("users")
        .select("google_refresh_token")
        .eq("id", user_id)
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        return None
    encrypted = rows[0].get("google_refresh_token")
    if not encrypted:
        return None
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except Exception:
        logger.warning("Failed to decrypt Gmail refresh token for user %s", user_id)
        return None


def get_imported_gmail_message_ids(client: Client, user_id: str) -> set:
    """Return the set of Gmail message IDs already imported by this user."""
    rows = (
        client.table("applications")
        .select("gmail_message_id")
        .eq("user_id", user_id)
        .not_.is_("gmail_message_id", "null")
        .execute()
        .data
    )
    return {r["gmail_message_id"] for r in rows if r.get("gmail_message_id")}


def bulk_import_gmail_applications(
    client: Client,
    user_id: str,
    items: List[Dict[str, Any]],
    skip_message_ids: set,
) -> List[str]:
    """Insert jobs + applications for a list of Gmail-parsed items in 3 DB calls.

    Each item must have: message_id, company, role, status, email_date.
    Returns a list of created application IDs.
    """
    to_import = [it for it in items if it["message_id"] not in skip_message_ids]
    if not to_import:
        return []

    now = datetime.now(timezone.utc).isoformat()

    # 1. Find which job URLs already exist (one SELECT)
    urls = [f"gmail-sync://{it['message_id']}" for it in to_import]
    existing_jobs = (
        client.table("jobs").select("id,url").in_("url", urls).execute().data
    )
    existing_by_url = {j["url"]: j["id"] for j in existing_jobs}

    # 2. Insert missing jobs in one bulk INSERT (handle race condition)
    new_job_payloads = [
        {
            "id": str(uuid.uuid4()),
            "title": it["role"],
            "company": it["company"],
            "source": "gmail_sync",
            "url": f"gmail-sync://{it['message_id']}",
            "created_at": now,
        }
        for it in to_import
        if f"gmail-sync://{it['message_id']}" not in existing_by_url
    ]
    if new_job_payloads:
        try:
            inserted = client.table("jobs").insert(new_job_payloads).execute().data
            for j in inserted:
                existing_by_url[j["url"]] = j["id"]
        except Exception:
            # Race condition: a concurrent request inserted one or more of the same URLs.
            # Re-fetch all URLs that were in the batch to recover their IDs.
            conflict_urls = [p["url"] for p in new_job_payloads]
            resolved = (
                client.table("jobs").select("id,url").in_("url", conflict_urls).execute().data
            )
            for j in resolved:
                existing_by_url[j["url"]] = j["id"]

    # 3. Insert all applications in one bulk INSERT
    missing = [
        it for it in to_import
        if f"gmail-sync://{it['message_id']}" not in existing_by_url
    ]
    if missing:
        logger.warning(
            "bulk_import: %d item(s) had no job row after insert — skipping", len(missing)
        )
    app_payloads = [
        {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "job_id": existing_by_url[f"gmail-sync://{it['message_id']}"],
            "status": it["status"] if it["status"] in _VALID_STATUSES else "applied",
            "source": "gmail_sync",
            "gmail_message_id": it["message_id"],
            "applied_at": it.get("email_date"),
            "created_at": now,
            "updated_at": now,
        }
        for it in to_import
        if f"gmail-sync://{it['message_id']}" in existing_by_url
    ]
    if not app_payloads:
        return []
    inserted_apps = client.table("applications").insert(app_payloads).execute().data
    return [a["id"] for a in inserted_apps]




