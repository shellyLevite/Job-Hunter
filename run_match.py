"""
End-to-end matching smoke test.
Requires:
  - jobs table populated (run run_scrape.py first)
  - A user with a parsed CV in the DB
  - OPENAI_API_KEY in .env

Usage:
  .venv/Scripts/python.exe run_match.py --email you@example.com

Supabase SQL to create job_matches table (run once in dashboard):

  create table if not exists job_matches (
    id             uuid primary key default gen_random_uuid(),
    user_id        uuid not null references users(id),
    job_id         uuid not null references jobs(id),
    score          float not null,
    missing_skills text[] default '{}',
    created_at     timestamptz default now(),
    unique(user_id, job_id)
  );
"""
import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

from app.db.session import get_supabase
from app.db import crud
from app.core.config import settings
from app.services.matcher import get_matching_engine


async def main(email: str, limit: int):
    client = get_supabase()

    # 1 — get user
    print(f"=== Looking up user: {email} ===")
    user = crud.get_user_by_email(client, email)
    if not user:
        print(f"  ✗ User not found. Register first via POST /auth/register")
        sys.exit(1)
    user_id = user["id"]
    print(f"  ✓ Found user_id={user_id}\n")

    # 2 — get CV
    print("=== Fetching CV ===")
    cv = crud.get_user_cv(client, user_id)
    if not cv:
        print("  ✗ No CV found. Upload one via POST /cv/upload")
        sys.exit(1)
    cv_text = cv.get("parsed_content") or ""
    if not cv_text:
        # Use file_path as a fallback preview label
        print(f"  ⚠ CV exists ({cv['file_path']}) but has no parsed_content yet.")
        print("  Using filename as a mock CV text for this smoke test.\n")
        cv_text = f"CV file: {cv['file_path']}\nSkills: Python, FastAPI, SQL, Docker, REST APIs, Git"
    else:
        print(f"  ✓ CV text: {cv_text[:120]}...\n")

    # 3 — fetch jobs
    print(f"=== Fetching up to {limit} jobs ===")
    jobs = crud.get_jobs(client, limit=limit)
    print(f"  ✓ Loaded {len(jobs)} jobs\n")

    if not jobs:
        print("  No jobs in DB — run run_scrape.py first.")
        sys.exit(0)

    # 4 — run matching engine
    engine = get_matching_engine()
    results = []
    print(f"=== Running matcher (threshold={settings.MATCH_THRESHOLD}) ===")

    for job in jobs:
        score, missing = await engine.match(cv_text=cv_text, job=job)
        results.append((score, missing, job))
        print(f"  {score:.0%}  {job['title']} @ {job['company']} | missing: {missing[:3]}")

    # 5 — persist matches above threshold
    saved = 0
    for score, missing, job in results:
        if score >= settings.MATCH_THRESHOLD:
            crud.upsert_job_match(client, user_id=user_id, job_id=job["id"], score=score, missing_skills=missing)
            saved += 1

    print(f"\n  ✓ Saved {saved}/{len(results)} matches above threshold {settings.MATCH_THRESHOLD:.0%}\n")

    # 6 — read back top matches
    print("=== Top matches from DB ===")
    matches = crud.get_matches_for_user(client, user_id=user_id, limit=10)
    for m in matches:
        job = m.get("jobs") or {}
        print(f"  {m['score']:.0%}  {job.get('title')} @ {job.get('company')}  missing={m['missing_skills'][:3]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True, help="Registered user email")
    parser.add_argument("--limit", type=int, default=20, help="Max jobs to evaluate")
    args = parser.parse_args()
    asyncio.run(main(args.email, args.limit))
