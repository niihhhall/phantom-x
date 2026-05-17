from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: str
    REDIS_URL: str
    ANTHROPIC_API_KEY: Optional[str] = None
    DECODO_USERNAME: Optional[str] = None
    DECODO_PASSWORD: Optional[str] = None
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    SLACK_WEBHOOK_URL: Optional[str] = None
    LINKEDIN_EMAIL: Optional[str] = None
    LINKEDIN_PASSWORD: Optional[str] = None
    APOLLO_API_KEY: Optional[str] = None
    HUNTER_API_KEY: Optional[str] = None
    PROFILE_STORAGE_PATH: str = "app/profiles"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
