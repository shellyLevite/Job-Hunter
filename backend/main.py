from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import auth, cv, jobs, applications, integrations
from backend.core.config import settings

app = FastAPI(title="JobHunter AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(cv.router, prefix="/cv", tags=["cv"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
app.include_router(applications.router, prefix="/applications", tags=["applications"])
app.include_router(integrations.router, prefix="/integrations", tags=["integrations"])


@app.get("/healthz")
def health_check():
    return {"status": "ok"}
