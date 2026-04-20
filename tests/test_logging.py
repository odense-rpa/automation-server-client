from datetime import datetime
from logging import LogRecord
import logging
from unittest.mock import patch
from automation_server_client._config import AutomationServerConfig
from automation_server_client._logging import ats_logging_handler, _emitting
import httpx

from automation_server_client._server import AutomationServer


def test_basic_create_log_entry(ats: AutomationServer):
    log_data = {
        "event_timestamp": datetime.now().isoformat(),
        "message": "Test log entry - basic call with no extra data",
        "level": "INFO",
        "logger_name": "test_logger",
    }

    with httpx.Client() as client:
        response = client.post(
            f"{AutomationServerConfig.url}/audit-logs", json=log_data
        )

    assert response.status_code == 204


def test_format_log_record():
    # Need to get a record from the logging system
    record = LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="tests/test_logging.py",
        lineno=42,
        msg="This is a test log message",
        args=(),
        exc_info=None,
    )

    formatted_log = ats_logging_handler._format_log_record(record)

    assert isinstance(formatted_log, dict)
    assert "event_timestamp" in formatted_log
    assert "message" in formatted_log
    assert formatted_log["message"] == "This is a test log message"
    assert formatted_log["level"] == "INFO"
    assert formatted_log["logger_name"] == "test_logger"
    assert "structured_data" in formatted_log
    assert formatted_log["structured_data"] is None


def test_server_accepts_record(ats: AutomationServer):
    # Need to get a record from the logging system
    record = LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="tests/test_logging.py",
        lineno=42,
        msg="This is a test log message",
        args=(),
        exc_info=None,
    )

    formatted_log = ats_logging_handler._format_log_record(record)

    with httpx.Client() as client:
        response = client.post(
            f"{AutomationServerConfig.url}/audit-logs", json=formatted_log
        )

    assert response.status_code == 204


def test_emit_guard_prevents_reentry():
    token = _emitting.set(True)
    try:
        with patch("automation_server_client._logging.httpx.post") as mock_post:
            record = LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="should be blocked", args=(), exc_info=None,
            )
            ats_logging_handler.emit(record)
        mock_post.assert_not_called()
    finally:
        _emitting.reset(token)
