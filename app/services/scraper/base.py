from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseJobScraper(ABC):
    """All job scrapers must implement this interface."""

    source: str  # e.g. "linkedin", "indeed"

    @abstractmethod
    async def scrape(
        self,
        query: str,
        location: str,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """Scrape jobs and return a list of normalised job dicts.

        Each dict must contain at minimum:
            title    (str)
            company  (str)
            url      (str)
            source   (str)
        And optionally:
            location    (str)
            description (str)
        """
        ...
