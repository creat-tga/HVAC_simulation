from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "HVAC仿真平台"
    debug: bool = True

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
