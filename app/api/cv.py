import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from supabase import Client

from app.api.auth import get_current_user
from app.core.config import settings
from app.db import crud
from app.db.session import get_supabase

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

CONTENT_TYPES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".txt": "text/plain",
}


def _safe_filename(email: str, original: str) -> str:
    """Return a safe storage path segment: <safe_email>/<safe_filename>."""
    base = Path(original).name
    safe = re.sub(r"[^\w.\-]", "_", base)
    safe_email = re.sub(r"[^\w.\-]", "_", email)
    return f"{safe_email}/{safe}"


@router.post("/upload")
def upload_cv(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    client: Client = Depends(get_supabase),
):
    """Upload a user's CV to Supabase Storage and persist a record."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{suffix}' not allowed. Accepted: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    try:
        content = file.file.read(MAX_FILE_SIZE + 1)
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File exceeds 5 MB limit.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {exc}")
    finally:
        file.file.close()

    storage_path = _safe_filename(user.email, file.filename or "cv")
    content_type = CONTENT_TYPES.get(suffix, "application/octet-stream")

    try:
        client.storage.from_(settings.STORAGE_BUCKET).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": content_type, "upsert": "true"},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Storage upload failed: {exc}")

    # Build a signed URL valid for 1 hour so the caller can verify the upload
    try:
        signed = client.storage.from_(settings.STORAGE_BUCKET).create_signed_url(
            storage_path, expires_in=3600
        )
        signed_url = signed.get("signedURL") or signed.get("signedUrl", "")
    except Exception:
        signed_url = ""

    stored_user = crud.get_user_by_email(client, user.email)
    if stored_user:
        crud.create_cv_record(
            client,
            user_id=stored_user["id"],
            file_path=storage_path,
        )

    return JSONResponse({"storage_path": storage_path, "signed_url": signed_url})


@router.get("/latest")
def get_latest_cv(
    user=Depends(get_current_user),
    client: Client = Depends(get_supabase),
):
    """Return the user's most recently uploaded CV with a fresh signed URL."""
    stored_user = crud.get_user_by_email(client, user.email)
    if not stored_user:
        raise HTTPException(status_code=404, detail="User not found.")

    cv_record = crud.get_user_cv(client, stored_user["id"])
    if not cv_record:
        raise HTTPException(status_code=404, detail="No CV uploaded yet.")

    storage_path = cv_record["file_path"]
    filename = Path(storage_path).name

    try:
        signed = client.storage.from_(settings.STORAGE_BUCKET).create_signed_url(
            storage_path, expires_in=3600
        )
        signed_url = signed.get("signedURL") or signed.get("signedUrl", "")
    except Exception:
        signed_url = ""

    return {
        "storage_path": storage_path,
        "filename": filename,
        "signed_url": signed_url,
        "created_at": cv_record.get("created_at"),
    }
