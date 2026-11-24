"""JWTs in query strings (staff WebSocket) must never reach the logs."""

import logging

from app.main import RedactTokenFilter, redact_tokens


def test_redact_tokens():
    assert redact_tokens("/ws/queue?token=eyJ.a.b") == "/ws/queue?token=[REDACTED]"
    assert redact_tokens("/x?a=1&access_token=abc&b=2") == "/x?a=1&access_token=[REDACTED]&b=2"
    assert redact_tokens("/x?mytoken=1") == "/x?mytoken=1"


def test_uvicorn_access_record_is_redacted():
    # Same shape as uvicorn's access log call.
    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:5000", "GET", "/ws/queue?token=eyJhbGciOi.secret.sig", "1.1", 101), None,
    )
    assert RedactTokenFilter().filter(record)
    assert "secret" not in record.getMessage()
    assert "token=[REDACTED]" in record.getMessage()


def test_filters_installed_on_uvicorn_loggers():
    for name in ("uvicorn.access", "uvicorn.error"):
        assert any(isinstance(f, RedactTokenFilter) for f in logging.getLogger(name).filters)
