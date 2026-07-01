from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    project_name: str = "TokenGuard"
    version: str = "0.1.0"
    database_url: str = "postgresql://tokenguard:tokenguard_dev@localhost:5432/tokenguard"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret-change-in-production"
    sendgrid_api_key: str = ""
    stripe_secret_key: str = ""
    proxy_host: str = "0.0.0.0"
    proxy_port: int = 8001
    default_retention_days: int = 30
    free_plan_max_members: int = 3

@lru_cache()
def get_settings() -> Settings:
    return Settings()
