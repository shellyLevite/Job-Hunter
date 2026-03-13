"""Indeed job scraper using Playwright.

Scrapes the public Indeed job search results page.
Note: Indeed may require CAPTCHA solving in production — consider
integrating a CAPTCHA service (e.g. 2captcha) or using their
official Publisher API if available in your region.
"""

import asyncio
import logging
from typing import Any, Dict, List
from urllib.parse import urlencode

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from app.services.scraper.base import BaseJobScraper

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.indeed.com/jobs"


class IndeedScraper(BaseJobScraper):
    source = "indeed"

    def __init__(self, headless: bool = True):
        self._headless = headless

    async def scrape(
        self,
        query: str,
        location: str,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        jobs: List[Dict[str, Any]] = []
        start = 0

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self._headless)
            try:
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/122.0.0.0 Safari/537.36"
                    )
                )
                page = await context.new_page()

                while len(jobs) < max_results:
                    params = {"q": query, "l": location, "start": start}
                    url = f"{_BASE_URL}?{urlencode(params)}"

                    try:
                        await page.goto(url, timeout=30_000)
                        await page.wait_for_selector("div#mosaic-provider-jobcards", timeout=15_000)
                    except PlaywrightTimeout:
                        logger.warning("Indeed: timed out — page may be blocked or CAPTCHA triggered")
                        break

                    cards = await page.query_selector_all("div.job_seen_beacon")
                    if not cards:
                        break

                    for card in cards:
                        try:
                            title_el    = await card.query_selector("h2.jobTitle span[title]")
                            company_el  = await card.query_selector("span[data-testid='company-name']")
                            location_el = await card.query_selector("div[data-testid='text-location']")
                            link_el     = await card.query_selector("a.jcs-JobTitle")

                            title        = await title_el.get_attribute("title") if title_el else ""
                            company      = (await company_el.inner_text()).strip()  if company_el  else ""
                            location_text= (await location_el.inner_text()).strip() if location_el else ""
                            href = await link_el.get_attribute("href") if link_el else ""
                            # Strip tracking params — keep only the jk identifier path
                            base_href = href.split("&")[0] if href else ""
                            job_url = f"https://www.indeed.com{base_href}" if base_href.startswith("/") else base_href

                            if not title or not job_url:
                                continue

                            # Fetch description from right-side panel
                            description = ""
                            try:
                                if link_el:
                                    await link_el.click()
                                    await page.wait_for_selector(
                                        "div#jobDescriptionText", timeout=6_000
                                    )
                                    desc_el = await page.query_selector("div#jobDescriptionText")
                                    if desc_el:
                                        description = (await desc_el.inner_text()).strip()
                            except Exception:  # noqa: BLE001
                                pass  # description stays empty — matching falls back to title

                            jobs.append(
                                {
                                    "title": title,
                                    "company": company,
                                    "location": location_text,
                                    "description": description or None,
                                    "source": self.source,
                                    "url": job_url,
                                }
                            )
                        except Exception as exc:  # noqa: BLE001
                            logger.debug("Indeed: error parsing card: %s", exc)

                    start += 10
                    await asyncio.sleep(2)
            finally:
                await browser.close()

        logger.info("Indeed: scraped %d jobs for query=%r location=%r", len(jobs), query, location)
        return jobs[:max_results]
