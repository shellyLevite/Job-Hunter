from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY: str = "change-me"
    REFRESH_SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # Set to True in production (requires HTTPS)
    SECURE_COOKIES: bool = False

    SUPABASE_URL: str = ""
    SUPABASE_KEY: str = ""
    STORAGE_BUCKET: str = "CVS"

    # AI / matching
    GROQ_API_KEY: str = ""
    MATCH_THRESHOLD: float = 0.10  # minimum score to persist a match

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"
    FRONTEND_URL: str = "http://localhost:5174"

    # CORS — comma-separated list of allowed origins
    CORS_ORIGINS: str = "http://localhost:5174"

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_not_be_default(cls, v: str) -> str:
        if v == "change-me":
            raise ValueError(
                "SECRET_KEY must be set to a secure random value. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    @field_validator("REFRESH_SECRET_KEY")
    @classmethod
    def refresh_secret_key_must_be_set(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "REFRESH_SECRET_KEY must be set. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
