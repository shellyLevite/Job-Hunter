from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""

    # Scraper config
    SCRAPE_QUERY: str = "software engineer"
    SCRAPE_LOCATION: str = "Tel Aviv"
    SCRAPE_SOURCES: str = "linkedin,indeed"
    SCRAPE_MAX: int = 50

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
