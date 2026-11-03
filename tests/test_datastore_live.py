"""Datastore against a real Automation Server (the dev stack or tests/ci).

Skipped when the server predates datastores (before 0.8.2).
"""

import os
import uuid

import httpx
import pytest

from automation_server_client import (
    AutomationServerConfig,
    Datastore,
    DatastoreConflict,
)


@pytest.fixture
def name(monkeypatch):
    """A fresh datastore name; the datastore is deleted afterwards."""
    monkeypatch.setenv("ATS_URL", os.environ.get("ATS_URL", "http://localhost/api"))
    AutomationServerConfig.init_from_environment()
    url = AutomationServerConfig.url
    headers = AutomationServerConfig.auth_headers()

    response = httpx.get(f"{url}/datastores", headers=headers)
    if response.status_code == 404:
        pytest.skip("server has no datastores (needs automation-server 0.8.2+)")
    response.raise_for_status()

    name = f"client-test-{uuid.uuid4().hex[:8]}"
    yield name

    response = httpx.get(f"{url}/datastores/by_name/{name}", headers=headers)
    if response.status_code == 200:
        httpx.delete(f"{url}/datastores/{response.json()['id']}", headers=headers)


def test_get_save_and_conflict(name):
    datastore = Datastore.get(name)
    assert datastore.version == 0 and datastore.data == {}

    datastore.data = {"teams": {"A": 1}}
    datastore.save()
    assert datastore.version == 1
    assert datastore.id is not None

    stale = Datastore.get(name)
    datastore.data["teams"]["B"] = 2
    datastore.save()
    assert datastore.version == 2

    stale.data = {"teams": {}}
    with pytest.raises(DatastoreConflict):
        stale.save()
    assert Datastore.get(name).data == {"teams": {"A": 1, "B": 2}}


def test_set_and_update(name):
    Datastore.set(name, {"count": 1})
    Datastore.set(name, {"count": 5})

    datastore = Datastore.update(name, lambda data: {"count": data["count"] + 1})
    assert datastore.data == {"count": 6}
    assert datastore.version == 3


def test_server_errors_raise(name):
    # Names with "/" are refused by the server
    with pytest.raises(httpx.HTTPStatusError):
        Datastore.set(f"{name}/x", {})
