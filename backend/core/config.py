"""Application configuration. Reads from environment variables; .env loaded once at startup."""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT_DIR / ".env"), extra="ignore")

    database_url: str = "sqlite:///./ifpi_lms.db"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60
    refresh_token_days: int = 30
    environment: str = "development"

    auth_cookie_mode: str = "dual"     # off | dual | on
    auth_cookie_samesite: str = "lax"  # lax | none | strict
    auth_cookie_secure: bool = False
    allowed_origins: str = "*"

    emergent_llm_key: str = ""
    ai_builder_model: str = "gpt-4o-mini"
    ai_builder_provider: str = "openai"

    # ERP360 integration switches (off in v1 — flip to enable)
    billing_live_mode: bool = False
    erp360_base_url: str = ""
    erp360_sso_shared_secret: str = ""
    erp360_billing_webhook_secret: str = ""
    sso_enabled: bool = False

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def cors_origins(self) -> list[str]:
        if not self.allowed_origins or self.allowed_origins == "*":
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
