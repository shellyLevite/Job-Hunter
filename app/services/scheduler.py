"""Background scheduler — runs scrapers every 10 minutes.

The scheduler reads scrape targets from the central Settings object.
Configure via environment variables / .env file:

  SCRAPE_QUERY    = "software engineer"   (default)
  SCRAPE_LOCATION = "Tel Aviv"            (default)
  SCRAPE_SOURCES  = "linkedin,indeed"     (default: both)
  SCRAPE_MAX      = "50"                  (per source, default)
"""

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.db.session import get_supabase
from app.db import crud
from app.services.scraper.linkedin import LinkedInScraper
from app.services.scraper.indeed import IndeedScraper

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

_SCRAPERS = {
    "linkedin": LinkedInScraper,
    "indeed": IndeedScraper,
}


async def run_scrapers() -> None:
    """Fetch jobs from all configured sources and upsert them into Supabase."""
    query = settings.SCRAPE_QUERY
    location = settings.SCRAPE_LOCATION
    sources = [s.strip() for s in settings.SCRAPE_SOURCES.split(",")]
    max_results = settings.SCRAPE_MAX

    client = get_supabase()
    total = 0

    for source in sources:
        scraper_cls = _SCRAPERS.get(source)
        if scraper_cls is None:
            logger.warning("Unknown scraper source: %s", source)
            continue

        scraper = scraper_cls()
        try:
            jobs = await scraper.scrape(query=query, location=location, max_results=max_results)
        except Exception as exc:  # noqa: BLE001
            logger.error("Scraper %s failed: %s", source, exc)
            continue

        for job in jobs:
            try:
                crud.upsert_job(client, job)
                total += 1
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to upsert job %r: %s", job.get("url"), exc)

    logger.info("Scrape cycle complete — upserted %d jobs", total)


def start_scheduler(interval_minutes: int = 10) -> None:
    """Register the scrape job and start the scheduler."""
    scheduler.add_job(
        run_scrapers,
        trigger="interval",
        minutes=interval_minutes,
        id="scrape_jobs",
        replace_existing=True,
        misfire_grace_time=60,
    )
    scheduler.start()
    logger.info("Job scheduler started — interval=%d min", interval_minutes)


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
