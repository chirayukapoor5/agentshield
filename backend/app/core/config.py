from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "AgentShield"
    APP_ENV: str = "development"
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DATABASE_URL: str = "sqlite:///./agentshield.db"
    REDIS_URL: str = "redis://localhost:6379/0"
    CORS_ORIGINS: str = "http://localhost:3000"
    SCAN_TIMEOUT_SECONDS: int = 15
    MAX_REDIRECTS: int = 3
    MAX_RESPONSE_BYTES: int = 200000
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
