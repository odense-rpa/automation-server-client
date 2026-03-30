import pytest
import os
from dotenv import load_dotenv
from automation_server_client import AutomationServer
import httpx

load_dotenv()


@pytest.fixture(scope="function")
def ats() -> AutomationServer:
    # We assume there is a running target development environment
    os.environ.setdefault("ATS_URL", "http://localhost/api")

    TEST_WORKQUEUE = "Client library test"

    os.environ["ATS_WORKQUEUE_OVERRIDE"] = str(
        _ensure_workqueue(os.environ["ATS_URL"], TEST_WORKQUEUE)
    )

    ats = AutomationServer.from_environment()

    workqueue = ats.workqueue()
    workqueue.clear_workqueue()

    return ats


def _ensure_workqueue(base_url: str, workqueue_name: str) -> int:
    response = httpx.get(f"{base_url}/workqueues").json()
    workqueues = {wq["name"]: wq["id"] for wq in response}

    if workqueue_name not in workqueues:
        response = httpx.post(
            f"{base_url}/workqueues",
            json={
                "name": workqueue_name,
                "description": "Workqueue for testing the client library",
                "enabled": "true",
            },
        )
        response.raise_for_status()
        return response.json()["id"]

    return workqueues[workqueue_name]
