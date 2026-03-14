# Scraper sub-package
from backend.services.scraper.base import BaseJobScraper
from backend.services.scraper.linkedin import LinkedInScraper

__all__ = ["BaseJobScraper", "LinkedInScraper"]
