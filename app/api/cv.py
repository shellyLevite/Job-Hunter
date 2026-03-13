import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from supabase import Client

from app.api.auth import get_current_user
from app.db import crud
from app.db.session import get_supabase

router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def _safe_filename(email: str, original: str) -> str:
    """Return a safe filename that cannot escape the upload directory."""
    # Strip path separators, keep only the base filename
    base = Path(original).name
    # Remove any characters that are not alphanumeric, dash, underscore, or dot
    safe = re.sub(r"[^\w.\-]", "_", base)
    # Normalize the email for use in filename
    safe_email = re.sub(r"[^\w.\-]", "_", email)
    return f"{safe_email}-{safe}"


@router.post("/upload")
def upload_cv(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    client: Client = Depends(get_supabase),
):
    """Save a user's CV to disk and persist a record in Supabase."""
    # Validate file extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{suffix}' not allowed. Accepted: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    filename = _safe_filename(user.email, file.filename or "cv")
    filepath = UPLOAD_DIR / filename

    try:
        content = file.file.read(MAX_FILE_SIZE + 1)
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File exceeds 5 MB limit.")
        filepath.write_bytes(content)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")
    finally:
        file.file.close()

    stored_user = crud.get_user_by_email(client, user.email)
    if stored_user:
        crud.create_cv_record(client, user_id=stored_user["id"], file_path=str(filepath))

    return JSONResponse({"file_path": str(filepath)})
