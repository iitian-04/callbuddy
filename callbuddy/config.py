"""All settings in one place, read from the .env file.

Concept: pydantic-settings reads environment variables (and .env) into a typed class.
If a required value is missing, we fail at startup with a clear message instead of
crashing later deep inside the voice pipeline.

API keys are `SecretStr`: printing them shows '**********', so they can't leak into
logs by accident. Use `.get_secret_value()` only at the moment you pass a key to a service.
"""

from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(Exception):
    """Raised when .env is missing something we need."""


class Settings(BaseSettings):
    # extra="ignore": other variables in .env (e.g. Twilio, later phases) don't cause errors.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Required: no default, so startup fails if they're missing.
    deepgram_api_key: SecretStr
    groq_api_key: SecretStr

    # Optional, with defaults.
    # llama-3.3-70b-versatile was shut down by Groq on 16 Aug 2026; gpt-oss-120b replaces it.
    groq_model: str = "openai/gpt-oss-120b"
    # gpt-oss "thinks" before answering; "low" keeps that short so voice replies are fast.
    groq_reasoning_effort: str = "low"
    kokoro_voice: str = "af_heart"
    log_level: str = "INFO"


def load_settings(**overrides) -> Settings:
    """Load settings, turning pydantic's long error into a short, friendly one."""
    try:
        return Settings(**overrides)
    except ValidationError as e:
        missing = [str(err["loc"][0]).upper() for err in e.errors() if err["type"] == "missing"]
        if missing:
            raise ConfigError(
                f"Missing in .env: {', '.join(missing)}. Copy .env.example to .env and fill them in."
            ) from None
        raise ConfigError(f"Invalid setting in .env: {e}") from None
