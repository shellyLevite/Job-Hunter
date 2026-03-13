"""LinkedIn job scraper using the public guest jobs API.

LinkedIn exposes a public endpoint used for SEO/indexing that requires
NO login, NO cookie, NO browser automation:

  https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search

It returns lightweight HTML fragments — parsed here with BeautifulSoup.
This approach carries no account-ban risk.
"""

import logging
from typing import Any, Dict, List
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup

from app.services.scraper.base import BaseJobScraper

logger = logging.getLogger(__name__)

_GUEST_API = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

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

    async def scrape(
        self,
        query: str,
        location: str,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        jobs: List[Dict[str, Any]] = []
        start = 0

        async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=30) as client:
            while len(jobs) < max_results:
                params = {
                    "keywords": query,
                    "location": location,
                    "f_TPR": "r86400",  # posted in last 24 hours
                    "start": start,
                }
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
                        job_url      = link_el["href"].split("?")[0]    if link_el    else ""

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

        logger.info("LinkedIn: scraped %d jobs for query=%r location=%r", len(jobs), query, location)
        return jobs[:max_results]
