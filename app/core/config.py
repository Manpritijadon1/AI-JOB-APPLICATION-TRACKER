import ipaddress
from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI-Powered Job Application Tracker"
    database_url: str = "sqlite:///./job_tracker.db"
    jwt_secret_key: str | None = None
    access_token_expire_minutes: int = Field(default=30, gt=0)
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout_seconds: float = Field(default=60.0, gt=0)
    ai_max_request_bytes: int = Field(default=65536, gt=0)
    ai_max_input_characters: int = Field(default=20000, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("ollama_base_url")
    @classmethod
    def require_local_ollama_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        try:
            is_loopback = hostname is not None and ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            is_loopback = hostname is not None and hostname.lower() == "localhost"

        if (
            parsed.scheme != "http"
            or not is_loopback
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Ollama must use a local HTTP service URL")
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
