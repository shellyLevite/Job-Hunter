# Scraper sub-package
from app.services.scraper.base import BaseJobScraper
from app.services.scraper.linkedin import LinkedInScraper

__all__ = ["BaseJobScraper", "LinkedInScraper"]
