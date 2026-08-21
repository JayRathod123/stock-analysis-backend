import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Stock Analysis Backend"
    API_V1_STR: str = "/api/v1"

    # Environment
    ENV: str = "development"

    # Database Settings
    # Use SQLite in-memory or file for test/dev fallback
    DATABASE_URL: str = "sqlite:///./test.db"

    # Ollama AI Configuration
    OLLAMA_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "llama3"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
