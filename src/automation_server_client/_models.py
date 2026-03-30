import logging
import requests

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict
from urllib.parse import quote

from ._config import AutomationServerConfig
from ._logging import ats_logging_handler

class Session(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    process_id: int
    resource_id: Optional[int] = None
    dispatched_at: Optional[datetime] = None
    status: str
    stop_requested: bool
    deleted: bool
    parameters: Optional[str] = ""
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def get_session(session_id):
        """Retrieve a session by ID from the automation server."""
        response = requests.get(
            f"{AutomationServerConfig.url}/sessions/{session_id}",
            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
        )
        response.raise_for_status()

        return Session.model_validate(response.json())


class Process(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: Optional[int] = None
    name: str
    description: Optional[str] = ""
    requirements: Optional[str] = ""
    target_type: Optional[str] = None
    target_source: Optional[str] = ""
    target_credentials_id: int | None = None
    credentials_id: int | None = None
    workqueue_id: int | None = None
    deleted: bool
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def get_process(process_id):
        """Retrieve a process by ID from the automation server."""
        response = requests.get(
            f"{AutomationServerConfig.url}/processes/{process_id}",
            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
        )
        response.raise_for_status()

        return Process.model_validate(response.json())


class WorkItemStatus(str, Enum):
    NEW = "new"
    IN_PROGRESS = "in progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING_USER_ACTION = "pending user action"


class Workqueue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    enabled: bool
    deleted: bool
    created_at: datetime
    updated_at: datetime

    def add_item(self, data: dict, reference: str):
        """Add a new work item to the workqueue."""
        response = requests.post(
            f"{AutomationServerConfig.url}/workqueues/{self.id}/add",
            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
            json={"data": data, "reference": reference},
        )
        response.raise_for_status()

        return WorkItem.model_validate(response.json())

    @staticmethod
    def get_workqueue(workqueue_id):
        """Retrieve a workqueue by ID from the automation server."""
        response = requests.get(
            f"{AutomationServerConfig.url}/workqueues/{workqueue_id}",
            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
        )
        response.raise_for_status()

        return Workqueue.model_validate(response.json())

    @staticmethod
    def get_workqueue_by_name(workqueue_name: str):
        """Retrieve a workqueue by name from the automation server."""
        response = requests.get(
            f"{AutomationServerConfig.url}/workqueues/by_name/{quote(workqueue_name)}",

            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
        )
        response.raise_for_status()

        return Workqueue.model_validate(response.json())

    def clear_workqueue(
        self, workitem_status: WorkItemStatus | None = None, days_older_than=None
    ):
        """Clear work items from the workqueue, optionally filtered by status or age."""
        response = requests.post(
            f"{AutomationServerConfig.url}/workqueues/{self.id}/clear",
            json={
                "workitem_status": workitem_status,
                "days_older_than": days_older_than,
            },
            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
        )
        response.raise_for_status()

    def get_item_by_reference(
        self, reference: str, status: WorkItemStatus | None = None
    ) -> list["WorkItem"]:
        """Retrieve work items by reference, optionally filtered by status."""

        response = requests.get(
            f"{AutomationServerConfig.url}/workqueues/{self.id}/by_reference/{quote(reference)}",
            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
            params={"status": status} if status else None,
        )
        response.raise_for_status()

        items = response.json()
        return [WorkItem.model_validate(item) for item in items]

    def __iter__(self):
        return self

    def __next__(self):
        ats_logging_handler.end_workitem()
        response = requests.get(
            f"{AutomationServerConfig.url}/workqueues/{self.id}/next_item",
            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
        )

        if response.status_code == 204:
            raise StopIteration

        response.raise_for_status()

        workitem = WorkItem.model_validate(response.json())

        ats_logging_handler.start_workitem(workitem.id)

        return workitem


class WorkItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: Optional[int] = None
    data: dict
    reference: Optional[str] = ""
    locked: bool
    status: str
    message: str
    workqueue_id: int
    started_at: Optional[datetime] = None
    work_duration_seconds: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    def update(self, data: dict):
        """Update the work item's data on the automation server."""
        response = requests.put(
            f"{AutomationServerConfig.url}/workitems/{self.id}",
            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
            json={"data": data, "reference": self.reference},
        )
        response.raise_for_status()
        self.data = data

    def __enter__(self):
        logger = logging.getLogger("ats")
        logger.debug(f"Processing {self}")

        ats_logging_handler.start_workitem(self.id)

        return self

    def __exit__(self, exc_type, exc_value, _traceback):
        logger = logging.getLogger("ats")
        if exc_type:
            logger.error(f"An error occurred while processing {self}: {exc_value}")
            self.fail(str(exc_value))
        elif self.status == "in progress":
            self.complete("Completed")

        logger.debug(f"{'Failed' if exc_type else 'Finished'} processing {self}")
        ats_logging_handler.end_workitem()

    def __str__(self) -> str:
        return f"WorkItem(id={self.id}, reference={self.reference}, data={self.data})"

    def fail(self, message):
        """Mark the work item as failed."""
        self.update_status("failed", message)

    def complete(self, message):
        """Mark the work item as completed."""
        self.update_status("completed", message)

    def pending_user(self, message):
        """Mark the work item as pending user action."""
        self.update_status("pending user action", message)

    def update_status(self, status, message: str = ""):
        """Update the work item's status and message on the automation server."""
        response = requests.put(
            f"{AutomationServerConfig.url}/workitems/{self.id}/status",
            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
            json={"status": status, "message": message},
        )
        response.raise_for_status()
        self.status = status
        self.message = message


class Credential(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: Optional[int] = None
    name: str
    data: dict
    username: Optional[str] = None
    password: Optional[str] = None
    deleted: bool
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def get_credential(credential: str) -> "Credential":
        """Retrieve a credential by name from the automation server."""
        response = requests.get(
            f"{AutomationServerConfig.url}/credentials/by_name/{quote(credential)}",
            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
        )
        response.raise_for_status()

        return Credential.model_validate(response.json())
