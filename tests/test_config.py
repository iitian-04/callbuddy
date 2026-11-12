import pytest

from callbuddy.config import ConfigError, load_settings


def test_missing_keys_give_a_clear_error(monkeypatch, tmp_path):
    # Run in an empty folder (no .env) with no keys in the environment.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="GROQ_API_KEY"):
        load_settings()


def test_keys_are_hidden_when_printed(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    s = load_settings(deepgram_api_key="dg-secret", groq_api_key="gsk_secret")
    assert "dg-secret" not in str(s) and "gsk_secret" not in repr(s)
    assert s.groq_api_key.get_secret_value() == "gsk_secret"


def test_defaults(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for var in ["GROQ_MODEL", "KOKORO_VOICE", "LOG_LEVEL", "GROQ_REASONING_EFFORT"]:
        monkeypatch.delenv(var, raising=False)
    s = load_settings(deepgram_api_key="a", groq_api_key="b")
    assert s.groq_model == "openai/gpt-oss-120b"
    assert s.kokoro_voice == "af_heart"


def test_reads_dotenv_file(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    (tmp_path / ".env").write_text("DEEPGRAM_API_KEY=x\nGROQ_API_KEY=y\nGROQ_MODEL=m\n")
    assert load_settings().groq_model == "m"


def test_stt_falls_back_to_groq_without_deepgram_key(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("STT_PROVIDER", raising=False)
    assert load_settings(groq_api_key="g").resolved_stt_provider == "groq"
    assert load_settings(groq_api_key="g", deepgram_api_key="d").resolved_stt_provider == "deepgram"
    assert load_settings(groq_api_key="g", deepgram_api_key="").resolved_stt_provider == "groq"
