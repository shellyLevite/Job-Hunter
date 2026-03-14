"""Pydantic response schemas that mirror the Supabase table shapes.

Table DDL should be created directly in the Supabase dashboard or via migrations.

users table (SQL):
  id              uuid primary key default gen_random_uuid()
  email           text unique not null
  hashed_password text not null
  created_at      timestamptz default now()

cvs table (SQL):
  id              uuid primary key default gen_random_uuid()
  user_id         uuid not null references users(id)
  file_path       text not null
  parsed_content  text
  created_at      timestamptz default now()

jobs table (SQL):
  id          uuid primary key default gen_random_uuid()
  title       text not null
  company     text not null
  location    text
  description text
  source      text not null
  url         text unique not null
  created_at  timestamptz default now()

job_matches table (SQL):
  id             uuid primary key default gen_random_uuid()
  user_id        uuid not null references users(id)
  job_id         uuid not null references jobs(id)
  score          float not null
  missing_skills text[]
  created_at     timestamptz default now()
  unique(user_id, job_id)

users table additions (run in Supabase SQL editor):
  ALTER TABLE users ADD COLUMN IF NOT EXISTS google_refresh_token text;

applications table (SQL):
  id               uuid primary key default gen_random_uuid()
  user_id          uuid not null references users(id)
  job_id           uuid not null references jobs(id)
  status           text not null default 'saved'
  notes            text
  applied_at       timestamptz
  created_at       timestamptz default now()
  updated_at       timestamptz default now()
  source           text default 'manual'  -- 'manual' | 'gmail_sync'
  gmail_message_id text                   -- for dedup; null for manual entries
  unique(user_id, job_id)

  -- migration: run in Supabase SQL editor
  ALTER TABLE applications ADD COLUMN IF NOT EXISTS source text DEFAULT 'manual';
  ALTER TABLE applications ADD COLUMN IF NOT EXISTS gmail_message_id text;
  CREATE UNIQUE INDEX IF NOT EXISTS applications_gmail_msg_idx
    ON applications(user_id, gmail_message_id)
    WHERE gmail_message_id IS NOT NULL;
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UserRow(BaseModel):
    id: str
    email: str
    hashed_password: str
    created_at: datetime
    google_refresh_token: Optional[str] = None


class CVRow(BaseModel):
    id: str
    user_id: str
    file_path: str
    parsed_content: Optional[str] = None
    created_at: datetime


class JobRow(BaseModel):
    id: str
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    source: str
    url: str
    created_at: datetime


class JobMatchRow(BaseModel):
    id: str
    user_id: str
    job_id: str
    score: float
    missing_skills: list[str]
    created_at: datetime


class ApplicationRow(BaseModel):
    id: str
    user_id: str
    job_id: str
    status: str  # saved | applied | interview | rejected | offer
    notes: Optional[str] = None
    applied_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    source: str = "manual"  # 'manual' | 'gmail_sync'
    gmail_message_id: Optional[str] = None
