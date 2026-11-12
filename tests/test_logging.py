from loguru import logger

from callbuddy.logging_setup import redact, setup_logging


def test_redacts_known_secrets_and_key_shapes():
    text = "keys: my-deepgram-value gsk_abcdefghijklmnop " + "a" * 40
    out = redact(text, ["my-deepgram-value"])
    assert "my-deepgram-value" not in out
    assert "gsk_abcdefghijklmnop" not in out
    assert "a" * 40 not in out
    assert out.count("[REDACTED]") == 3


def test_log_lines_are_redacted(capsys):
    setup_logging("INFO", secrets=["super-secret"])
    logger.info("the key is super-secret")
    err = capsys.readouterr().err
    assert "super-secret" not in err and "[REDACTED]" in err
