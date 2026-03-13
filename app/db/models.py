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
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UserRow(BaseModel):
    id: str
    email: str
    hashed_password: str
    created_at: datetime


class CVRow(BaseModel):
    id: str
    user_id: str
    file_path: str
    parsed_content: Optional[str] = None
    created_at: datetime
