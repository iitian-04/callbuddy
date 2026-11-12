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

    # Required: no default, so startup fails if it's missing.
    groq_api_key: SecretStr
    # Optional: with a Deepgram key, speech-to-text uses Deepgram (streaming, fastest).
    # Without one, it uses Groq's hosted Whisper with the same Groq key (no extra account).
    deepgram_api_key: SecretStr | None = None
    stt_provider: str = "auto"  # auto | deepgram | groq

    # Optional, with defaults.
    # llama-3.3-70b-versatile was shut down by Groq on 16 Aug 2026; gpt-oss-120b replaces it.
    groq_model: str = "openai/gpt-oss-120b"
    # gpt-oss "thinks" before answering; "low" keeps that short so voice replies are fast.
    groq_reasoning_effort: str = "low"
    # Screen mode: the look_at_screen tool sends the screenshot to this model (reads images).
    vision_model: str = "qwen/qwen3.8-27b"
    # S2 memory: small fast text model that rewrites the session notes every few turns.
    memory_model: str = "openai/gpt-oss-20b"
    kokoro_voice: str = "af_heart"
    # Kokoro model file in ~/.cache/pipecat/kokoro-onnx/. The int8 (quantized) model is ~2x
    # faster on the Mac's CPU than the full one (1.6 s vs 3.4 s for 7 s of speech) and 3.5x
    # smaller. Set KOKORO_MODEL=kokoro-v1.0.onnx to go back to the full model.
    kokoro_model: str = "kokoro-v1.0.int8.onnx"
    log_level: str = "INFO"
    # Phase 2: the name the agent says it is calling for, if the task doesn't give one.
    caller_name: str = "the user"

    @property
    def resolved_stt_provider(self) -> str:
        if self.stt_provider != "auto":
            return self.stt_provider
        has_dg = self.deepgram_api_key is not None and self.deepgram_api_key.get_secret_value() != ""
        return "deepgram" if has_dg else "groq"


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
