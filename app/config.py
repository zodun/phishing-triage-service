from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment / .env (case-insensitive)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM provider: DeepSeek's OpenAI-compatible API.
    deepseek_api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    primary_model: str = "deepseek-chat"

    llm_fake: bool = False
    request_timeout_s: float = 30.0

    max_input_chars: int = 20000
    max_output_tokens: int = 512

    log_level: str = "INFO"
    service_name: str = "phish-triage"


@lru_cache
def get_settings() -> Settings:
    return Settings()
