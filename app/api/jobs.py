from fastapi import APIRouter

router = APIRouter()


@router.get("/matches")
def get_matches():
    """Placeholder endpoint for job matches."""
    return {"matches": []}
