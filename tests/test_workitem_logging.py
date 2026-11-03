import logging
from datetime import datetime
from unittest.mock import patch

import pytest

from automation_server_client import Credential, WorkItem, WorkItemError


def make_item(**overrides) -> WorkItem:
    fields = {
        "id": 39,
        "data": {"citizen": {"name": "Testperson Testesen"}, "secret": "x" * 1000},
        "reference": "ref-39",
        "locked": True,
        "status": "in progress",
        "message": "",
        "workqueue_id": 1,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    return WorkItem(**(fields | overrides))


def test_str_and_repr_exclude_data():
    item = make_item()
    assert str(item) == "WorkItem(id=39, reference=ref-39)"
    assert "Testperson" not in repr(item)
    assert "data=" not in repr(item)


def test_credential_repr_excludes_password():
    cred = Credential(
        name="system",
        data={"url": "https://example.invalid"},
        username="robot",
        password="hunter2",
        deleted=False,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    assert "hunter2" not in repr(cred)
    assert cred.password == "hunter2"


@pytest.mark.parametrize(
    "exc, expected",
    [
        (KeyError("url"), "KeyError: 'url'"),
        (ValueError(), "ValueError"),
        (WorkItemError("Citizen not found in system"), "Citizen not found in system"),
        (WorkItemError(), "WorkItemError"),
    ],
)
def test_failure_logs_reason_with_traceback_and_no_data(caplog, exc, expected):
    item = make_item()

    with patch.object(WorkItem, "update_status") as update_status:
        with caplog.at_level(logging.ERROR, logger="ats"):
            with pytest.raises(type(exc)):
                with item:
                    raise exc

    update_status.assert_called_once_with("failed", expected)

    [record] = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert (
        record.getMessage() == f"WorkItem(id=39, reference=ref-39) failed: {expected}"
    )
    assert record.exc_info is not None and record.exc_info[0] is type(exc)
    assert "Testperson" not in record.getMessage()


def test_success_completes_without_error_log(caplog):
    item = make_item()

    with patch.object(WorkItem, "update_status") as update_status:
        with caplog.at_level(logging.DEBUG, logger="ats"):
            with item:
                pass

    update_status.assert_called_once_with("completed", "Completed")
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
