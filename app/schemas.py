"""Shared Pydantic request / response schemas used across the API layer.

Keeping schemas in one place prevents cross-router imports (e.g. jobs.py
importing UserRead from auth.py) and makes the contract easy to discover.
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, EmailStr, field_validator

# ── Shared types ──────────────────────────────────────────────────────────────

ApplicationStatus = Literal["saved", "applied", "interview", "rejected", "offer"]

# ── Auth ──────────────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


class UserRead(BaseModel):
    email: EmailStr


# ── Applications ──────────────────────────────────────────────────────────────


class ApplicationCreate(BaseModel):
    job_id: str
    status: ApplicationStatus = "saved"
    notes: Optional[str] = None
    applied_at: Optional[str] = None  # ISO datetime string


class ApplicationUpdate(BaseModel):
    status: Optional[ApplicationStatus] = None
    notes: Optional[str] = None
    applied_at: Optional[str] = None
