from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    database_url: Optional[str] = None
    database_hostname: Optional[str] = None
    database_port: Optional[str] = "5432"
    database_password: Optional[str] = None
    database_name: Optional[str] = None
    database_username: Optional[str] = None
    redis_host: Optional[str] = None
    redis_port: Optional[int] = 6379
    groq_api_key: Optional[str] = None
    groq_api_keys: Optional[str] = None
    tavily_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

