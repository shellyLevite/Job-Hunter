"""LinkedIn job scraper using the public guest jobs API.

LinkedIn exposes public endpoints used for SEO/indexing that require
NO login, NO cookie, NO browser automation:

  Listings : https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
  Detail   : https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}

Descriptions are fetched concurrently (up to 5 at a time) after the
listing pass completes.  This approach carries no account-ban risk.
"""

import asyncio
import logging
from typing import Any, Dict, List
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from backend.services.scraper.base import BaseJobScraper

logger = logging.getLogger(__name__)

_GUEST_API  = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
_JOB_API    = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
_DESC_CONC  = 5   # max concurrent description requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


class LinkedInScraper(BaseJobScraper):
    source = "linkedin"

    async def _fetch_description(
        self, client: httpx.AsyncClient, job_url: str
    ) -> str:
        """Fetch full job description from LinkedIn's public jobPosting API."""
        try:
            # Job ID is the last hyphen-delimited numeric segment
            job_id = job_url.rstrip("/").split("-")[-1]
            if not job_id.isdigit():
                return ""
            api_url = _JOB_API.format(job_id=job_id)
            resp = await client.get(api_url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            desc_el = (
                soup.find("div", class_="show-more-less-html__markup")
                or soup.find("div", class_="description__text")
            )
            if desc_el:
                return desc_el.get_text(separator=" ", strip=True)
        except Exception as exc:  # noqa: BLE001
            logger.debug("LinkedIn: description fetch error for %s: %s", job_url, exc)
        return ""

    async def scrape(
        self,
        query: str,
        location: str,
        max_results: int = 50,
        posted_within: str | None = None,
    ) -> List[Dict[str, Any]]:
        jobs: List[Dict[str, Any]] = []
        start = 0
        # Default to 7 days if no filter specified
        time_filter = posted_within if posted_within else "r604800"

        async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=30) as client:
            # ── Phase 1: collect job cards ──────────────────────────────────────────────
            while len(jobs) < max_results:
                params: dict = {
                    "keywords": query,
                    "location": location,
                    "start": start,
                }
                if time_filter:
                    params["f_TPR"] = time_filter
                url = f"{_GUEST_API}?{urlencode(params)}"

                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning("LinkedIn guest API error at start=%d: %s", start, exc)
                    break

                soup = BeautifulSoup(resp.text, "lxml")
                cards = soup.find_all("div", class_="base-card")

                if not cards:
                    logger.debug("LinkedIn: no cards found at start=%d — end of results", start)
                    break

                for card in cards:
                    try:
                        title_el   = card.find("h3", class_="base-search-card__title")
                        company_el = card.find("h4", class_="base-search-card__subtitle")
                        loc_el     = card.find("span", class_="job-search-card__location")
                        link_el    = card.find("a", class_="base-card__full-link")

                        title        = title_el.get_text(strip=True)   if title_el   else ""
                        company      = company_el.get_text(strip=True)  if company_el else ""
                        location_txt = loc_el.get_text(strip=True)      if loc_el     else ""
                        job_url      = link_el.get("href", "").split("?")[0] if link_el else ""

                        if not title or not job_url:
                            continue

                        jobs.append({
                            "title":       title,
                            "company":     company,
                            "location":    location_txt,
                            "description": None,
                            "source":      self.source,
                            "url":         job_url,
                        })
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("LinkedIn: card parse error: %s", exc)

                start += 25  # LinkedIn paginates in steps of 25

            # ── Phase 2: fetch descriptions concurrently ─────────────────
            sem = asyncio.Semaphore(_DESC_CONC)

            async def _fetch(job: Dict[str, Any]) -> None:
                async with sem:
                    job["description"] = await self._fetch_description(client, job["url"])
                    await asyncio.sleep(0.3)  # be polite

            logger.info("LinkedIn: fetching descriptions for %d jobs…", len(jobs))
            await asyncio.gather(*[_fetch(j) for j in jobs])

        logger.info("LinkedIn: scraped %d jobs for query=%r location=%r", len(jobs), query, location)
        return jobs[:max_results]
