from pydantic import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"


settings = Settings()
