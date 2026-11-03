import json
import logging
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from automation_server_client import AutomationServerConfig, WorkItem, WorkItemError
from automation_server_client._logging import ats_logging_handler
from automation_server_client._models import MAX_MESSAGE_LENGTH, _failure_reason


def make_item() -> WorkItem:
    return WorkItem(
        id=5,
        data={"a": 1},
        reference="ref-5",
        locked=True,
        status="in progress",
        message="",
        workqueue_id=1,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )


@pytest.fixture
def session_config(monkeypatch):
    """Pretend we run inside a session so the handler sends records."""
    monkeypatch.setattr(AutomationServerConfig, "session", "1")
    monkeypatch.setattr(AutomationServerConfig, "url", "http://ats.invalid")


def send(record_kwargs: dict) -> dict:
    """Emit one record through the handler and return the JSON body it posted."""
    record = logging.getLogger("t").makeRecord(
        "t", logging.INFO, "f.py", 1, **record_kwargs
    )
    with patch("automation_server_client._logging.httpx.post") as post:
        post.return_value = MagicMock(status_code=204)
        ats_logging_handler.emit(record)
    assert post.call_count == 1, "record was dropped"
    return json.loads(post.call_args.kwargs["content"])


# High 1: records must never be dropped


def test_non_json_extra_value_is_sent_as_string(session_config):
    body = send(
        {
            "msg": "Sent",
            "args": (),
            "exc_info": None,
            "extra": {"sent_at": datetime(2026, 11, 3, 9, 0)},
        }
    )
    assert body["message"] == "Sent"
    assert body["structured_data"]["sent_at"] == "2026-11-03 09:00:00"


def test_exc_info_without_active_exception_is_sent(session_config):
    body = send({"msg": "Oops", "args": (), "exc_info": (None, None, None)})
    assert body["message"] == "Oops"
    assert body["exception_type"] is None and body["traceback"] is None


def test_failure_traceback_reaches_audit_fields(session_config):
    try:
        {}["url"]
    except KeyError as e:
        exc_info = (type(e), e, e.__traceback__)
    body = send({"msg": "WorkItem failed", "args": (), "exc_info": exc_info})
    assert body["exception_type"] == "KeyError"
    assert "KeyError: 'url'" in body["traceback"]
    assert "Traceback" not in body["message"]


# High 2: a status update failure must not hide the automation's error or leave
# the handler attached to the item


def test_fail_status_error_keeps_original_exception():
    item = make_item()
    ats_logging_handler.start_workitem(item.id)
    with patch.object(
        WorkItem, "update_status", side_effect=httpx.ConnectError("down")
    ):
        with pytest.raises(KeyError):
            with item:
                raise KeyError("url")
    assert ats_logging_handler.workitem_id is None


def test_complete_status_error_still_raises_and_detaches():
    item = make_item()
    with patch.object(
        WorkItem, "update_status", side_effect=httpx.ConnectError("down")
    ):
        with pytest.raises(httpx.ConnectError):
            with item:
                pass
    assert ats_logging_handler.workitem_id is None


# Failure message length


def test_long_failure_message_is_capped():
    message = _failure_reason(TimeoutError, TimeoutError("x" * 5000))
    assert len(message) == MAX_MESSAGE_LENGTH
    assert message.startswith("TimeoutError: ") and message.endswith("…")


def test_business_message_is_kept_when_short():
    assert (
        _failure_reason(WorkItemError, WorkItemError("Citizen not found"))
        == "Citizen not found"
    )


# Medium 5: no .env under the worker


def test_dotenv_not_loaded_under_worker(monkeypatch):
    monkeypatch.setenv("ATS_SESSION", "42")
    monkeypatch.setenv("ATS_URL", "http://ats.invalid")
    with patch("automation_server_client._config.load_dotenv") as load:
        AutomationServerConfig.init_from_environment()
    load.assert_not_called()


def test_dotenv_loaded_outside_worker(monkeypatch):
    monkeypatch.delenv("ATS_SESSION", raising=False)
    monkeypatch.setenv("ATS_URL", os.environ.get("ATS_URL", "http://ats.invalid"))
    with patch("automation_server_client._config.load_dotenv") as load:
        AutomationServerConfig.init_from_environment()
    load.assert_called_once()


# Low 7: drop httpx request lines for our own server only


@pytest.mark.parametrize(
    "ats_url, request_url, kept",
    [
        ("http://api:8000", "http://api:8000/workqueues/1/next_item", False),
        ("http://localhost:80/api/", "http://localhost/api//workitems/5/status", False),
        ("http://localhost/api", "http://localhost/api", False),
        (
            "http://localhost/api",
            "https://nexus.example.invalid/api/patients/123",
            True,
        ),
        ("http://localhost/api", "http://localhost/apix/other", True),
        ("", "http://api:8000/workqueues/1", True),
    ],
)
def test_httpx_filter_only_drops_own_requests(monkeypatch, ats_url, request_url, kept):
    from automation_server_client._logging import _SkipOwnRequests

    monkeypatch.setattr(AutomationServerConfig, "url", ats_url)
    record = logging.getLogger("httpx").makeRecord(
        "httpx",
        logging.INFO,
        "f.py",
        1,
        'HTTP Request: %s %s "%s %d %s"',
        ("GET", httpx.URL(request_url), "HTTP/1.1", 200, "OK"),
        None,
    )
    assert _SkipOwnRequests().filter(record) is kept


def test_httpx_filter_is_installed_on_httpx_logger():
    from automation_server_client._logging import _SkipOwnRequests

    assert any(
        isinstance(f, _SkipOwnRequests) for f in logging.getLogger("httpx").filters
    )


# Low 8: str(AutomationServer) shows IDs and names only


def test_automation_server_str_has_no_process_details():
    from types import SimpleNamespace

    from automation_server_client import AutomationServer

    ats = AutomationServer.__new__(AutomationServer)
    ats.url = "http://api:8000"
    ats.session = SimpleNamespace(id=8)
    ats.process = SimpleNamespace(
        name="Test-process",
        target_source="https://robot:ghp_secret@github.com/org/repo.git",
        git_options="--branch=dev",
    )
    ats.workqueue_id = 1

    assert (
        str(ats)
        == "AutomationServer(url=http://api:8000, session=8, process=Test-process, workqueue_id=1)"
    )

    ats.session = ats.process = None
    assert "session=None, process=None" in str(ats)
