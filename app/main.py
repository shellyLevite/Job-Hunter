from fastapi import FastAPI

from app.api import auth, jobs

app = FastAPI(title="JobHunter AI")

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])


@app.get("/healthz")
def health_check():
    return {"status": "ok"}
