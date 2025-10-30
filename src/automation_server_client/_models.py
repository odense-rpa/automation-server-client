import logging
import requests
import urllib.parse

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict

from ._config import AutomationServerConfig
from ._logging import ats_logging_handler
from urllib.parse import quote

class Session(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    process_id: int
    resource_id: int
    dispatched_at: datetime
    status: str
    stop_requested: bool
    deleted: bool
    parameters: Optional[str] = ""
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def get_session(session_id):
        response = requests.get(
            f"{AutomationServerConfig.url}/sessions/{session_id}",
            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
        )
        response.raise_for_status()

        return Session.model_validate(response.json())


class Process(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    name: str
    description: str
    requirements: str
    target_type: str
    target_source: str
    target_credentials_id: int | None = None
    credentials_id: int | None = None
    workqueue_id: int | None = None
    deleted: bool
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def get_process(process_id):
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

    id: int
    name: str
    description: str
    enabled: bool
    deleted: bool
    created_at: datetime
    updated_at: datetime

    def add_item(self, data: dict, reference: str):
        response = requests.post(
            f"{AutomationServerConfig.url}/workqueues/{self.id}/add",
            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
            json={"data": data, "reference": reference},
        )
        response.raise_for_status()

        return WorkItem.model_validate(response.json())

    @staticmethod
    def get_workqueue(workqueue_id):
        response = requests.get(
            f"{AutomationServerConfig.url}/workqueues/{workqueue_id}",
            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
        )
        response.raise_for_status()

        return Workqueue.model_validate(response.json())

    @staticmethod
    def get_workqueue_by_name(workqueue_name: str):
        response = requests.get(
            f"{AutomationServerConfig.url}/workqueues/by_name/{quote(workqueue_name)}",

            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
        )
        response.raise_for_status()

        return Workqueue.model_validate(response.json())

    def clear_workqueue(
        self, workitem_status: WorkItemStatus | None = None, days_older_than=None
    ):
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
        """Retrieve work items from the workqueue by their reference identifier.

        This method queries the automation server to find all work items that match
        the specified reference string. The reference is typically used as a unique
        identifier or business key for work items, making this method useful for
        duplicate checking, status verification, or retrieving specific items.

        Args:
            reference (str): The reference identifier to search for. The reference
                will be URL-encoded automatically to handle special characters.
            status (WorkItemStatus, optional): If provided, filters results to only
                include items with the specified status. Defaults to None (no filtering).

        Returns:
            list[WorkItem]: A list of WorkItem objects that match the reference.
                Returns an empty list if no matching items are found.

        Raises:
            requests.HTTPError: If the API request fails (e.g., network error,
                authentication failure, or server error).

        Example:
            >>> workqueue = Workqueue.get_workqueue(123)
            >>> # Find all items with reference "INV-2023-001"
            >>> items = workqueue.get_item_by_reference("INV-2023-001")
            >>>
            >>> # Find only completed items with the reference
            >>> completed_items = workqueue.get_item_by_reference(
            ...     "INV-2023-001",
            ...     WorkItemStatus.COMPLETED
            ... )
            >>>
            >>> # Check for duplicates before adding a new item
            >>> existing = workqueue.get_item_by_reference("new-ref")
            >>> if not existing:
            ...     workqueue.add_item({"data": "value"}, "new-ref")
        """

        response = requests.get(
            f"{AutomationServerConfig.url}/workqueues/{self.id}/by_reference/{quote(reference)}",
            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
            params={"status": status} if status else None,
        )
        response.raise_for_status()

        items = response.json()
        return [WorkItem(**item) for item in items]

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

    id: int
    data: dict
    reference: str
    locked: bool
    status: str
    message: str
    workqueue_id: int
    created_at: datetime
    updated_at: datetime

    def __init__(self, **data):
        super().__init__(**data)

    def update(self, data: dict):
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

        logger.debug(f"Finished processing {self}")
        ats_logging_handler.end_workitem()

        # If we are working on an item that is in progress, we will mark it as completed
        if self.status == "in progress":
            self.complete("Completed")

    def __str__(self) -> str:
        return f"WorkItem(id={self.id}, reference={self.reference}, data={self.data})"

    def fail(self, message):
        self.update_status("failed", message)

    def complete(self, message):
        self.update_status("completed", message)

    def pending_user(self, message):
        self.update_status("pending user action", message)

    def update_status(self, status, message: str = ""):
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

    id: int
    name: str
    data: dict
    username: str
    password: str
    deleted: bool
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def get_credential(credential: str) -> "Credential":
        response = requests.get(
            f"{AutomationServerConfig.url}/credentials/by_name/{urllib.parse.quote(credential)}",
            headers={"Authorization": f"Bearer {AutomationServerConfig.token}"},
        )
        response.raise_for_status()

        return Credential.model_validate(response.json())
