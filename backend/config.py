"""Configuración global — leída de .env vía pydantic-settings."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-7"

    edgar_user_agent: str = "BORJA Investment System contact@i-314.com"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "contact@i-314.com"
    smtp_to: str = "juan.brana@gmail.com"

    app_env: str = "dev"
    log_level: str = "INFO"
    db_path: str = "./data/borja.db"
    admin_user: str = "admin"
    admin_password_hash: str = ""
    base_url: str = "http://localhost:8111"
    app_port: int = 8111
    scheduler_autostart: bool = False

    # Seguridad para exposición pública (VM detrás de HTTPS / Cloudflare):
    cookie_secure: bool = False      # True cuando hay HTTPS delante → la cookie sólo viaja por TLS
    api_require_auth: bool = False   # True → /api/* también exige el password (recomendado si es público)

    fmp_api_key: str = ""
    polygon_api_key: str = ""
    benzinga_api_key: str = ""

    @property
    def db_url(self) -> str:
        path = (PROJECT_ROOT / self.db_path).resolve() if not Path(self.db_path).is_absolute() else Path(self.db_path)
        return f"sqlite:///{path}"

    @property
    def fase_2_enabled(self) -> bool:
        return bool(self.fmp_api_key or self.polygon_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
