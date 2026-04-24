from pathlib import Path
from typing import Any

from pydantic import field_validator
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
    secret_key: str = "hvac-simulation-secret-key-change-in-production"

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
