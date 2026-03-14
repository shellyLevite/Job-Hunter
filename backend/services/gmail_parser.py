"""Gmail parsing service.

Pipeline
────────
1. Gmail API search (server-side filter) — fetches only emails whose subject
   matches job-related keywords.
2. Single batched LLM call — all fetched emails are sent to Groq in one
   request.  The model returns a JSON array with one object per email
   (company, role, status).  Emails where the LLM returns no valid status
   are dropped.
3. Deduplication — keep the highest-priority status per (company, role) pair.

Nothing is written to the database here.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from groq import AsyncGroq

from backend.core.config import settings

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GMAIL_MESSAGES_URL = "https://www.googleapis.com/gmail/v1/users/me/messages"
_GMAIL_MESSAGE_URL = "https://www.googleapis.com/gmail/v1/users/me/messages/{id}"

# Gmail server-side filter — narrow the inbox before we touch anything
_SEARCH_QUERY = (
    'subject:("thank you for applying" OR "we received your application" '
    'OR "application received" OR "interview invitation" OR "interview request" '
    "OR \"we'd like to schedule\" OR \"unfortunately\" OR \"offer letter\" "
    'OR "job offer" OR "we are pleased to offer" OR "your application" '
    'OR "not moving forward" OR "application update" '
    'OR "offer accepted" OR "post offer" OR "pre-hire" OR "pre hire" '
    'OR "welcome to" OR "your start date" OR "starting soon" '
    'OR "excited to have you join" OR "complete your pre")'
)

_VALID_STATUSES = {"applied", "interview", "offer", "rejected"}
_STATUS_PRIORITY = {"offer": 0, "interview": 1, "rejected": 2, "applied": 3}

# ── LLM prompt ────────────────────────────────────────────────────────────────

_BATCH_PROMPT = """\
You will receive a numbered list of job-application emails.
For EACH email return a JSON object with exactly these keys:
  "company"  - the hiring company name (string, or null if unknown)
  "role"     - the job title / position (string, or null if unknown)
  "status"   - one of: "applied", "interview", "offer", "rejected" (or null if unclear)

Rules:
- Return ONLY a JSON array, one object per email, in the same order, no extra text.
- If the email is in a non-English language, still return the fields in English.
- "company" must be the employer name, NOT a person's name, NOT an ATS vendor \
(Greenhouse, Workday, Lever, iCIMS, etc.).
- If you cannot determine a field with reasonable confidence, use null.

Emails:
{emails_block}
"""


# ── Internal helpers ──────────────────────────────────────────────────────────


async def _exchange_refresh_token(refresh_token: str) -> Optional[str]:
    async with httpx.AsyncClient() as client:
        res = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if res.status_code != 200:
            logger.warning(
                "Gmail token refresh failed: HTTP %s — %s",
                res.status_code,
                res.text[:200],
            )
            return None
        return res.json().get("access_token")


def _decode_b64(data: str) -> str:
    padding = "=" * (4 - len(data) % 4)
    try:
        return base64.urlsafe_b64decode(data + padding).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_body(payload: Dict[str, Any]) -> str:
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        return _decode_b64(payload.get("body", {}).get("data", ""))
    if mime.startswith("multipart/"):
        return "".join(_extract_body(p) for p in payload.get("parts", []))
    return ""


def _get_header(headers: List[Dict[str, str]], name: str) -> str:
    name_lower = name.lower()
    return next(
        (h["value"] for h in headers if h.get("name", "").lower() == name_lower), ""
    )


def _ms_to_iso(ms: str) -> str:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


async def _llm_extract_batch(emails: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Send all emails in ONE Groq call; return a list of {company, role, status}.

    Falls back to a list of empty dicts on any failure so callers can
    gracefully use the regex_status instead.
    """
    emails_block = "\n\n".join(
        f"[{e['index']}]\nFrom: {e['sender']}\nSubject: {e['subject']}\n{e['snippet']}"
        for e in emails
    )
    groq = AsyncGroq(api_key=settings.GROQ_API_KEY)
    try:
        resp = await groq.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": _BATCH_PROMPT.format(emails_block=emails_block)}],
            temperature=0,
            max_tokens=8192,
            timeout=60,
        )
        raw = resp.choices[0].message.content.strip()
        # Strip markdown code fences if the model wraps output in ```json … ```
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
    except Exception as exc:
        logger.warning("LLM batch extraction failed: %s", exc)

    return [{}] * len(emails)


# ── Public API ────────────────────────────────────────────────────────────────


async def fetch_gmail_preview(
    refresh_token: str,
    max_results: int = 50,
) -> List[Dict[str, Any]]:
    """Fetch job-related emails and return a structured preview list.

    Each item: message_id, company, role, status, email_date, subject.
    Nothing is written to the database.
    Raises RuntimeError if the Gmail token refresh fails.
    """
    access_token = await _exchange_refresh_token(refresh_token)
    if not access_token:
        raise RuntimeError("Gmail token refresh failed — please reconnect Gmail")

    auth_headers = {"Authorization": f"Bearer {access_token}"}

    # 1. Fetch message IDs matching the search query
    async with httpx.AsyncClient(timeout=30) as http:
        list_res = await http.get(
            _GMAIL_MESSAGES_URL,
            headers=auth_headers,
            params={"q": _SEARCH_QUERY, "maxResults": max_results},
        )
        message_ids = [m["id"] for m in list_res.json().get("messages", [])]

        # Fetch all message details concurrently, capped to avoid rate limits
        _sem = asyncio.Semaphore(10)

        async def _fetch_one(msg_id: str) -> Dict[str, Any]:
            async with _sem:
                r = await http.get(
                    _GMAIL_MESSAGE_URL.format(id=msg_id),
                    headers=auth_headers,
                    params={"format": "full"},
                )
                return r.json()

        raw_messages = await asyncio.gather(*[_fetch_one(mid) for mid in message_ids])

    # 2. Build candidates list from all fetched messages
    candidates: List[Dict[str, Any]] = []
    for data in raw_messages:
        payload = data.get("payload", {})
        hdr = payload.get("headers", [])
        subject = _get_header(hdr, "Subject")
        sender = _get_header(hdr, "From")
        body = _extract_body(payload) or data.get("snippet", "")
        candidates.append({
            "message_id": data.get("id", ""),
            "subject": subject,
            "sender": sender,
            "snippet": body[:600],
            "email_date": _ms_to_iso(data.get("internalDate", "0")),
        })

    if not candidates:
        return []

    # 3. Single batched LLM call for all candidates
    llm_inputs = [
        {"index": i, "subject": c["subject"], "sender": c["sender"], "snippet": c["snippet"]}
        for i, c in enumerate(candidates)
    ]
    llm_results = await _llm_extract_batch(llm_inputs)

    # 4. Merge: LLM wins on company/role; regex_status is the fallback for status
    results: List[Dict[str, Any]] = []
    for i, candidate in enumerate(candidates):
        llm = llm_results[i] if i < len(llm_results) else {}
        status = llm.get("status")
        if status not in _VALID_STATUSES:
            continue
        company = (llm.get("company") or "").strip() or "Unknown Company"
        role = (llm.get("role") or "").strip() or "Unknown Role"
        results.append({
            "message_id": candidate["message_id"],
            "company": company,
            "role": role,
            "status": status,
            "email_date": candidate["email_date"],
            "subject": candidate["subject"],
        })

    # 5. Deduplicate by (company, role) — keep the highest-priority status
    best: Dict[tuple, Dict[str, Any]] = {}
    for item in results:
        key = (item["company"].lower(), item["role"].lower())
        existing = best.get(key)
        if existing is None or (
            _STATUS_PRIORITY.get(item["status"], 99)
            < _STATUS_PRIORITY.get(existing["status"], 99)
        ):
            best[key] = item

    return list(best.values())
