import pytest
import os
from dotenv import load_dotenv
from automation_server_client import AutomationServer, AutomationServerConfig
import httpx

load_dotenv()

_CONFIG_ATTRS = ("token", "url", "session", "resource", "process", "workqueue_override")


@pytest.fixture(autouse=True)
def _restore_config():
    """AutomationServerConfig is global state; reset it after every test."""
    saved = {name: getattr(AutomationServerConfig, name) for name in _CONFIG_ATTRS}
    yield
    for name, value in saved.items():
        setattr(AutomationServerConfig, name, value)


@pytest.fixture(scope="function")
def ats(monkeypatch) -> AutomationServer:
    # Needs a running server: the dev stack, or the CI compose in tests/ci/
    monkeypatch.setenv("ATS_URL", os.environ.get("ATS_URL", "http://localhost/api"))

    TEST_WORKQUEUE = "Client library test"

    monkeypatch.setenv(
        "ATS_WORKQUEUE_OVERRIDE",
        str(_ensure_workqueue(os.environ["ATS_URL"], TEST_WORKQUEUE)),
    )

    ats = AutomationServer.from_environment()

    workqueue = ats.workqueue()
    workqueue.clear_workqueue()

    return ats


def _auth_headers() -> dict:
    token = os.environ.get("ATS_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _ensure_workqueue(base_url: str, workqueue_name: str) -> int:
    response = httpx.get(f"{base_url}/workqueues", headers=_auth_headers())
    response.raise_for_status()
    response = response.json()
    workqueues = {wq["name"]: wq["id"] for wq in response}

    if workqueue_name not in workqueues:
        response = httpx.post(
            f"{base_url}/workqueues",
            headers=_auth_headers(),
            json={
                "name": workqueue_name,
                "description": "Workqueue for testing the client library",
                "enabled": "true",
            },
        )
        response.raise_for_status()
        return response.json()["id"]

    return workqueues[workqueue_name]
