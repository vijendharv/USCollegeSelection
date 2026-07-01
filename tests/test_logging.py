from __future__ import annotations

import json
import logging

from app.logging_config import JsonFormatter


def test_json_formatter_emits_structured_record() -> None:
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "ready", (), None)

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "test"
    assert payload["message"] == "ready"
    assert "timestamp" in payload
