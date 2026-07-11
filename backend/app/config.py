import secrets
from pathlib import Path
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Application
    app_name: str = "HVAC仿真平台"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./hvac_simulation.db"

    # CORS
    cors_origins: list[str] = ["http://localhost:5173"]

    # EnergyPlus
    energyplus_path: str = ""

    # Auth
    secret_key: str = ""
    bootstrap_admin_username: str = ""
    bootstrap_admin_password: str = ""

    # External calculation engine. Run multiSystem on a different port from
    # this platform API (the platform defaults to 8000).
    multisystem_base_url: str = "http://127.0.0.1:8010"
    multisystem_timeout_seconds: float = 60.0
    multisystem_poll_interval_seconds: float = 2.0
    multisystem_api_key: str = ""

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    celery_worker_concurrency: int = 2

    # SQL debug logging (separate from app debug)
    sql_echo: bool = False

    # Equipment data sync: when True, on backend startup the equipment library
    # will be (re)seeded from JSON files under <repo_root>/data/equipment/
    # (pump.json, cooling_tower.json or tower.json, chiller.json,
    # air_cooled_module.json). Existing models are upserted by (equipment_type, model_no).
    seed_equipment_from_data: bool = False
    # Optional override for the data directory (absolute path). If empty,
    # defaults to <repo_root>/data/equipment.
    equipment_data_dir: str = ""

    @field_validator("debug", mode="before")
    @classmethod
    def _parse_debug(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on", "debug", "development", "dev"}:
            return True
        if text in {"0", "false", "no", "off", "release", "production", "prod"}:
            return False
        return bool(value)

    @field_validator("database_url", mode="before")
    @classmethod
    def _resolve_database_url(cls, value: Any) -> str:
        url = str(value or "sqlite+aiosqlite:///./hvac_simulation.db").strip()
        prefix = "sqlite+aiosqlite:///"
        if not url.startswith(prefix):
            return url

        raw_path = url[len(prefix):]
        if raw_path in {":memory:", ""}:
            return url

        db_path = Path(raw_path)
        if db_path.is_absolute():
            return url

        resolved = (BACKEND_DIR / db_path).resolve()
        return f"{prefix}{resolved.as_posix()}"

    @model_validator(mode="after")
    def _validate_security_settings(self) -> "Settings":
        key = self.secret_key.strip()
        known_defaults = {
            "hvac-simulation-secret-key-change-in-production",
            "replace-with-at-least-32-random-characters",
        }
        if len(key) < 32 or key in known_defaults:
            if not self.debug:
                raise ValueError("SECRET_KEY must contain at least 32 characters in production")
            self.secret_key = secrets.token_urlsafe(48)

        username = self.bootstrap_admin_username.strip()
        password = self.bootstrap_admin_password
        if bool(username) != bool(password):
            raise ValueError("BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD must be configured together")
        if password and len(password) < 12:
            raise ValueError("BOOTSTRAP_ADMIN_PASSWORD must contain at least 12 characters")
        return self

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
