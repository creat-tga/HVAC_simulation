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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
