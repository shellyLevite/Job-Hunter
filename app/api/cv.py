from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from supabase import Client

from app.api.auth import get_current_user
from app.db import crud
from app.db.session import get_supabase

router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
def upload_cv(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    client: Client = Depends(get_supabase),
):
    """Save a user's CV to disk and persist a record in Supabase."""
    filename = f"{user.email}-{file.filename}"
    filepath = UPLOAD_DIR / filename

    try:
        content = file.file.read()
        filepath.write_bytes(content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {exc}")
    finally:
        file.file.close()

    # Fetch user id from Supabase to store the relation
    stored_user = crud.get_user_by_email(client, user.email)
    if stored_user:
        crud.create_cv_record(client, user_id=stored_user["id"], file_path=str(filepath))

    return JSONResponse({"file_path": str(filepath)})
