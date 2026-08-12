"""Application configuration. Reads from environment variables; .env loaded once at startup."""
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
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
    # Iter 30h — CSRF double-submit cookie enforcement. When True, the
    # server issues a non-HttpOnly `ifpi_csrf` cookie on login/refresh
    # and requires it (mirrored in the `X-CSRF-Token` header) on every
    # mutating request that authenticates via cookie. Bearer-header
    # requests (API tokens, mobile) are exempt.
    csrf_enabled: bool = False
    # Origins allowed to make credentialed browser requests.
    # Env: CORS_ORIGINS is the deployment-surface name (per Emergent
    # deploy support). ALLOWED_ORIGINS is kept as a legacy alias so
    # preview .env files don't have to be renamed. Deploy secret wins.
    cors_origins_env: str = Field(default="", validation_alias="CORS_ORIGINS")
    allowed_origins: str = "*"      # legacy ALLOWED_ORIGINS

    emergent_llm_key: str = ""
    ai_builder_model: str = "gpt-4o-mini"
    ai_builder_provider: str = "openai"

    # Iter 23 — Source-grounded tutor: RAG embeddings + Q&A model
    tutor_llm_provider: str = "openai"
    tutor_llm_model: str = "gpt-4o-mini"
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"

    # Iter 24 — Deep research via Tavily (user-supplied key required)
    tavily_api_key: str = ""

    # ERP360 integration switches (off in v1 — flip to enable)
    billing_live_mode: bool = False
    erp360_base_url: str = ""
    erp360_sso_shared_secret: str = ""
    erp360_billing_webhook_secret: str = ""
    sso_enabled: bool = False

    # Public-facing base URL (used in emails, cert verify links).
    # Optional — if empty, request.base_url is used. Set this in production
    # so that links survive the k8s ingress (which sets the upstream host
    # header to the internal cluster name).
    public_base_url: str = ""

    # File storage backend — mirrors ERP360's storage_service abstraction.
    # local: write to STORAGE_PATH on the container's disk (default).
    # s3:    Amazon S3 — requires S3_BUCKET (+ AWS creds in env).
    # gcs:   Google Cloud Storage — requires GCS_BUCKET (+ GCP creds).
    storage_backend: str = "local"
    storage_path: str = "./uploads"
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    gcs_bucket: str = ""
    gcs_project: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def test_bypass_enabled(self) -> bool:
        """Test-only affordances (X-Return-Token, X-Test-Client-Ip,
        /_test endpoints). Requires the explicit opt-in env var AND a
        non-production environment — double-locked for deploys."""
        import os
        return (os.environ.get("ALLOW_TEST_TOKEN_HEADER", "").lower() == "true"
                and not self.is_production)

    @property
    def cors_origins(self) -> list[str]:
        # Deployment secret CORS_ORIGINS wins if set (per Emergent deploy
        # support). Falls back to legacy ALLOWED_ORIGINS for preview.
        raw = (self.cors_origins_env or self.allowed_origins or "").strip()
        if not raw or raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
