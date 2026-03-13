from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth, cv, jobs
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="JobHunter AI", lifespan=lifespan)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(cv.router, prefix="/cv", tags=["cv"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])


@app.get("/healthz")
def health_check():
    return {"status": "ok"}


@app.get("/healthz")
def health_check():
    return {"status": "ok"}
