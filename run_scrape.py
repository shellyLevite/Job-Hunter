"""
Real end-to-end scrape runner.
Usage (from project root):  python run_scrape.py
"""
import asyncio

from dotenv import load_dotenv
load_dotenv()

from app.core.config import settings
from app.db.session import get_supabase
from app.db import crud
from app.services.scraper.linkedin import LinkedInScraper
from app.services.scraper.indeed import IndeedScraper

QUERY    = settings.SCRAPE_QUERY
LOCATION = settings.SCRAPE_LOCATION
MAX      = settings.SCRAPE_MAX

DDL = """
-- Run this once in the Supabase SQL Editor (https://supabase.com/dashboard/project/_/sql)

create extension if not exists "pgcrypto";

create table if not exists users (
  id              uuid primary key default gen_random_uuid(),
  email           text unique not null,
  hashed_password text not null,
  created_at      timestamptz default now()
);

create table if not exists cvs (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references users(id),
  file_path       text not null,
  parsed_content  text,
  created_at      timestamptz default now()
);

create table if not exists jobs (
  id          uuid primary key default gen_random_uuid(),
  title       text not null,
  company     text not null,
  location    text,
  description text,
  source      text not null,
  url         text unique not null,
  created_at  timestamptz default now()
);
"""


async def main():
    client = get_supabase()

    # 1 — verify Supabase connection + tables
    print("=== Checking Supabase connection ===")
    try:
        result = client.table("jobs").select("id").limit(1).execute()
        print(f"  ✓ Connected — jobs table reachable ({len(result.data)} rows visible)\n")
    except Exception as e:
        print(f"  ✗ Could not reach 'jobs' table: {e}\n")
        print("  ► Go to: https://supabase.com/dashboard/project/_/sql")
        print("  ► Paste and run the following SQL, then re-run this script:\n")
        print(DDL)
        sys.exit(1)

    # 2 — run scrapers
    scrapers = [
        ("LinkedIn", LinkedInScraper()),
        ("Indeed",   IndeedScraper()),
    ]

    all_jobs = []
    for name, scraper in scrapers:
        print(f"=== Scraping {name} (query={QUERY!r}, location={LOCATION!r}, max={MAX}) ===")
        try:
            jobs = await scraper.scrape(query=QUERY, location=LOCATION, max_results=MAX)
            print(f"  ✓ {name} returned {len(jobs)} jobs")
            for j in jobs[:3]:
                print(f"    • {j['title']} @ {j['company']} — {j['url'][:70]}")
            all_jobs.extend(jobs)
        except Exception as e:
            print(f"  ✗ {name} scraper failed: {e}")
        print()

    if not all_jobs:
        print("No jobs scraped — check scraper logs above.")
        sys.exit(0)

    # 3 — persist to Supabase
    print(f"=== Persisting {len(all_jobs)} jobs to Supabase ===")
    saved = 0
    for job in all_jobs:
        try:
            crud.upsert_job(client, job)
            saved += 1
        except Exception as e:
            print(f"  ✗ Failed to upsert {job.get('url', '?')[:60]}: {e}")
    print(f"  ✓ Upserted {saved}/{len(all_jobs)} jobs\n")

    # 4 — read back from DB to confirm
    print("=== Reading back from Supabase ===")
    rows = crud.get_jobs(client, limit=10)
    print(f"  Latest {len(rows)} jobs in DB:")
    for r in rows:
        print(f"    [{r['source']:8}] {r['title']} @ {r['company']}")


if __name__ == "__main__":
    asyncio.run(main())
