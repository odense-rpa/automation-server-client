"""Datastore against an in-memory fake of the server's /datastores/by_name API.

The fake applies the same version rules as the server: expected_version must
match the stored version, 0 means "must not exist", and leaving it out
overwrites.
"""

import logging
from urllib.parse import unquote

import httpx
import pytest

from automation_server_client import (
    AutomationServerConfig,
    Datastore,
    DatastoreConflict,
)

URL = "http://ats.invalid"
PREFIX = f"{URL}/datastores/by_name/"


class FakeServer:
    def __init__(self):
        self.stored: dict[str, dict] = {}
        self.writes: list[dict] = []
        # Called before each write is applied, to simulate a concurrent writer
        self.before_write = None

    def _name(self, url: str) -> str:
        assert url.startswith(PREFIX), url
        return unquote(url[len(PREFIX) :])

    def _response(self, method, url, status, body):
        return httpx.Response(status, json=body, request=httpx.Request(method, url))

    def _body(self, name):
        stored = self.stored[name]
        return {
            "id": stored["id"],
            "name": name,
            "description": "",
            "data": stored["data"],
            "version": stored["version"],
            "size_bytes": len(str(stored["data"])),
            "deleted": False,
            "created_at": "2026-11-03T10:00:00",
            "updated_at": "2026-11-03T10:00:00",
        }

    def get(self, url, headers=None):
        name = self._name(url)
        if name not in self.stored:
            return self._response("GET", url, 404, {"detail": "Datastore not found"})
        return self._response("GET", url, 200, self._body(name))

    def put(self, url, headers=None, json=None):
        name = self._name(url)
        self.writes.append(json)
        if self.before_write:
            self.before_write(name)

        expected = json.get("expected_version")
        current = self.stored.get(name)
        if current is None:
            if expected not in (None, 0):
                return self._response("PUT", url, 404, {"detail": "not found"})
            self.write_directly(name, json["data"])
            return self._response("PUT", url, 201, self._body(name))

        if expected is not None and expected != current["version"]:
            return self._response(
                "PUT", url, 409, {"detail": f"Datastore '{name}' was changed"}
            )
        self.write_directly(name, json["data"])
        return self._response("PUT", url, 200, self._body(name))

    def write_directly(self, name, data):
        """A write by someone else (or the server applying one)."""
        current = self.stored.get(name)
        self.stored[name] = {
            "id": current["id"] if current else len(self.stored) + 1,
            "data": data,
            "version": current["version"] + 1 if current else 1,
        }


@pytest.fixture
def server(monkeypatch) -> FakeServer:
    fake = FakeServer()
    monkeypatch.setattr(AutomationServerConfig, "url", URL)
    monkeypatch.setattr(AutomationServerConfig, "token", "")
    monkeypatch.setattr("automation_server_client._models.httpx.get", fake.get)
    monkeypatch.setattr("automation_server_client._models.httpx.put", fake.put)
    return fake


# Reading


def test_get_missing_datastore_is_empty(server):
    datastore = Datastore.get("state")
    assert datastore.name == "state"
    assert datastore.data == {}
    assert datastore.version == 0
    assert datastore.id is None


def test_get_existing_datastore(server):
    server.write_directly("state", {"n": 1})
    datastore = Datastore.get("state")
    assert datastore.data == {"n": 1}
    assert datastore.version == 1


def test_name_is_quoted(server):
    server.write_directly("team a/b?", {"n": 1})
    assert Datastore.get("team a/b?").data == {"n": 1}


def test_repr_leaves_out_data(server):
    server.write_directly("state", {"secret-ish": "x" * 100})
    assert "secret-ish" not in repr(Datastore.get("state"))


# save(): version-checked


def test_save_creates_then_updates(server):
    datastore = Datastore.get("state")
    datastore.data["n"] = 1
    datastore.save()
    # A new datastore must not exist yet when it is first saved
    assert server.writes[-1]["expected_version"] == 0
    assert datastore.version == 1 and datastore.id == 1

    datastore.data["n"] = 2
    datastore.save()
    assert server.writes[-1]["expected_version"] == 1
    assert datastore.version == 2
    assert server.stored["state"]["data"] == {"n": 2}


def test_save_after_someone_else_wrote_is_refused(server):
    server.write_directly("state", {"n": 1})
    datastore = Datastore.get("state")

    server.write_directly("state", {"n": 5})
    datastore.data["n"] = 2
    with pytest.raises(DatastoreConflict, match="was changed"):
        datastore.save()

    assert server.stored["state"]["data"] == {"n": 5}
    assert datastore.version == 1


def test_save_new_datastore_created_meanwhile_is_refused(server):
    datastore = Datastore.get("state")
    server.write_directly("state", {"other": True})

    with pytest.raises(DatastoreConflict):
        datastore.save()


def test_other_errors_raise(server, monkeypatch):
    def too_large(url, headers=None, json=None):
        return httpx.Response(413, request=httpx.Request("PUT", url))

    monkeypatch.setattr("automation_server_client._models.httpx.put", too_large)
    with pytest.raises(httpx.HTTPStatusError):
        Datastore.set("state", {"n": 1})


# set(): last writer wins


def test_set_overwrites_without_version_check(server):
    server.write_directly("state", {"n": 1})
    datastore = Datastore.set("state", {"n": 9})

    assert "expected_version" not in server.writes[-1]
    assert datastore.data == {"n": 9}
    assert datastore.version == 2


# update(): read, change, save, retry


def test_update_creates_missing_datastore(server):
    datastore = Datastore.update("state", lambda data: {**data, "n": 1})
    assert datastore.version == 1
    assert server.stored["state"]["data"] == {"n": 1}


def test_update_retries_after_a_concurrent_write(server):
    server.write_directly("counter", {"count": 1})
    calls = []

    def increment(data):
        calls.append(dict(data))
        return {"count": data["count"] + 1}

    # Another run writes between our first read and save
    def concurrent_write(name):
        server.before_write = None
        server.write_directly(name, {"count": 10})

    server.before_write = concurrent_write

    datastore = Datastore.update("counter", increment)

    # The change was redone on top of the other run's write, not lost
    assert calls == [{"count": 1}, {"count": 10}]
    assert server.stored["counter"]["data"] == {"count": 11}
    assert datastore.version == 3


def test_update_gives_up(server):
    server.write_directly("state", {"n": 1})
    server.before_write = lambda name: server.write_directly(name, {"n": 0})

    with pytest.raises(DatastoreConflict, match="gave up after 3 attempts"):
        Datastore.update("state", lambda data: data, attempts=3)
    assert len(server.writes) == 3


# Logging: writes show up in the session's audit log


def test_writes_are_logged(server, caplog):
    with caplog.at_level(logging.INFO, logger="ats"):
        Datastore.set("state", {"n": 1})
        Datastore.set("state", {"n": 2})

    messages = [r.getMessage() for r in caplog.records if r.name == "ats"]
    assert messages[0].startswith("Datastore 'state' created (version 1")
    assert messages[1].startswith("Datastore 'state' saved (version 2")
    # Only the name and version: documents can hold anything
    assert all("'n'" not in message for message in messages)
