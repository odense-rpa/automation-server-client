import logging
import httpx

from datetime import datetime
from enum import Enum
from typing import Callable, Optional
from pydantic import BaseModel, ConfigDict, Field
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
        response = httpx.get(
            f"{AutomationServerConfig.url}/sessions/{session_id}",
            headers=AutomationServerConfig.auth_headers(),
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
    git_options: Optional[str] = ""
    target_credentials_id: int | None = None
    credentials_id: int | None = None
    workqueue_id: int | None = None
    deleted: bool
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def get_process(process_id):
        """Retrieve a process by ID from the automation server."""
        response = httpx.get(
            f"{AutomationServerConfig.url}/processes/{process_id}",
            headers=AutomationServerConfig.auth_headers(),
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
        response = httpx.post(
            f"{AutomationServerConfig.url}/workqueues/{self.id}/add",
            headers=AutomationServerConfig.auth_headers(),
            json={"data": data, "reference": reference},
        )
        response.raise_for_status()

        return WorkItem.model_validate(response.json())

    @staticmethod
    def get_workqueue(workqueue_id):
        """Retrieve a workqueue by ID from the automation server."""
        response = httpx.get(
            f"{AutomationServerConfig.url}/workqueues/{workqueue_id}",
            headers=AutomationServerConfig.auth_headers(),
        )
        response.raise_for_status()

        return Workqueue.model_validate(response.json())

    @staticmethod
    def get_workqueue_by_name(workqueue_name: str):
        """Retrieve a workqueue by name from the automation server."""
        response = httpx.get(
            f"{AutomationServerConfig.url}/workqueues/by_name/{quote(workqueue_name)}",
            headers=AutomationServerConfig.auth_headers(),
        )
        response.raise_for_status()

        return Workqueue.model_validate(response.json())

    def clear_workqueue(
        self, workitem_status: WorkItemStatus | None = None, days_older_than=None
    ):
        """Clear work items from the workqueue, optionally filtered by status or age."""
        response = httpx.post(
            f"{AutomationServerConfig.url}/workqueues/{self.id}/clear",
            json={
                "workitem_status": workitem_status,
                "days_older_than": days_older_than,
            },
            headers=AutomationServerConfig.auth_headers(),
        )
        response.raise_for_status()

    def get_item_by_reference(
        self, reference: str, status: WorkItemStatus | None = None
    ) -> list["WorkItem"]:
        """Retrieve work items by reference, optionally filtered by status."""

        response = httpx.get(
            f"{AutomationServerConfig.url}/workqueues/{self.id}/by_reference/{quote(reference)}",
            headers=AutomationServerConfig.auth_headers(),
            params={"status": status.value} if status else None,
        )
        response.raise_for_status()

        items = response.json()
        return [WorkItem.model_validate(item) for item in items]

    def __iter__(self):
        return self

    def __next__(self):
        ats_logging_handler.end_workitem()
        response = httpx.get(
            f"{AutomationServerConfig.url}/workqueues/{self.id}/next_item",
            headers=AutomationServerConfig.auth_headers(),
        )

        if response.status_code == 204:
            raise StopIteration

        response.raise_for_status()

        workitem = WorkItem.model_validate(response.json())

        ats_logging_handler.start_workitem(workitem.id)

        return workitem


MAX_MESSAGE_LENGTH = 1000


def _failure_reason(exc_type, exc_value) -> str:
    """Work item failure message shown to operators.

    WorkItemError carries a business message from the automation, so it is used
    as-is. Other exceptions are bugs or system errors, so the exception type is
    included: "KeyError: 'url'" says more than "'url'".
    """
    from ._server import WorkItemError  # avoid a circular import at module load

    message = str(exc_value)
    if not (issubclass(exc_type, WorkItemError) and message):
        message = f"{exc_type.__name__}: {message}" if message else exc_type.__name__
    # Long exception texts (timeouts, HTTP errors) are cut; the full text is in the log
    if len(message) > MAX_MESSAGE_LENGTH:
        message = message[: MAX_MESSAGE_LENGTH - 1] + "…"
    return message


class WorkItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: Optional[int] = None
    # Kept out of repr: work item data can be large and contain personal data
    data: dict = Field(repr=False)
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
        response = httpx.put(
            f"{AutomationServerConfig.url}/workitems/{self.id}",
            headers=AutomationServerConfig.auth_headers(),
            json={"data": data, "reference": self.reference},
        )
        response.raise_for_status()
        self.data = data

    def __enter__(self):
        logger = logging.getLogger("ats")
        logger.debug(f"Processing {self}")

        ats_logging_handler.start_workitem(self.id)

        return self

    def __exit__(self, exc_type, exc_value, traceback):
        logger = logging.getLogger("ats")
        try:
            if exc_type:
                reason = _failure_reason(exc_type, exc_value)
                # exc_info puts the traceback in the audit log's own field
                logger.error(
                    "%s failed: %s",
                    self,
                    reason,
                    exc_info=(exc_type, exc_value, traceback),
                )
                try:
                    self.fail(reason)
                except httpx.HTTPError as e:
                    # Don't let a server problem replace the automation's own error,
                    # which is what the operator needs to see.
                    logger.error("Could not mark %s as failed: %r", self, e)
            elif self.status == "in progress":
                self.complete("Completed")

            logger.debug(f"{'Failed' if exc_type else 'Finished'} processing {self}")
        finally:
            ats_logging_handler.end_workitem()

    def __str__(self) -> str:
        return f"WorkItem(id={self.id}, reference={self.reference})"

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
        response = httpx.put(
            f"{AutomationServerConfig.url}/workitems/{self.id}/status",
            headers=AutomationServerConfig.auth_headers(),
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
    password: Optional[str] = Field(default=None, repr=False)
    deleted: bool
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def get_credential(credential: str) -> "Credential":
        """Retrieve a credential by name from the automation server."""
        response = httpx.get(
            f"{AutomationServerConfig.url}/credentials/by_name/{quote(credential)}",
            headers=AutomationServerConfig.auth_headers(),
        )
        response.raise_for_status()

        return Credential.model_validate(response.json())


class DatastoreConflict(Exception):
    """The datastore was written by someone else since it was read."""


def _datastore_url(name: str) -> str:
    return f"{AutomationServerConfig.url}/datastores/by_name/{quote(name, safe='')}"


class Datastore(BaseModel):
    """A named JSON document for keeping state between runs.

    Reading a datastore that doesn't exist yet gives an empty document with
    version 0; it is created on the first save. Every save is logged, so the
    audit log of a session shows which datastores it changed.
    """

    model_config = ConfigDict(extra="ignore")

    id: Optional[int] = None
    name: str
    description: Optional[str] = ""
    # Kept out of repr: documents can be large
    data: dict = Field(default_factory=dict, repr=False)
    # The version that was read; 0 when the datastore doesn't exist yet
    version: int = 0
    size_bytes: int = 0
    deleted: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @staticmethod
    def get(name: str) -> "Datastore":
        """Read a datastore by name; an empty one if it doesn't exist yet."""
        response = httpx.get(
            _datastore_url(name), headers=AutomationServerConfig.auth_headers()
        )
        if response.status_code == 404:
            return Datastore(name=name)
        response.raise_for_status()

        return Datastore.model_validate(response.json())

    def save(self) -> None:
        """Save ``data``, if nobody else wrote the datastore since it was read.

        Raises DatastoreConflict otherwise: read it again and redo the change,
        or use Datastore.update(), which does that for you.
        """
        saved = Datastore._write(self.name, self.data, self.version)
        for field in Datastore.model_fields:
            setattr(self, field, getattr(saved, field))

    @staticmethod
    def set(name: str, data: dict) -> "Datastore":
        """Overwrite a datastore's document, whatever it holds now.

        Last writer wins: only safe when no other run writes the same
        datastore at the same time. Otherwise use update().
        """
        return Datastore._write(name, data, expected_version=None)

    @staticmethod
    def update(
        name: str, change: Callable[[dict], dict], attempts: int = 5
    ) -> "Datastore":
        """Read, change and save a datastore, retrying if someone else wrote.

        ``change`` gets the current document and returns the new one. It can
        be called more than once, so it must not have side effects.
        """
        for _ in range(attempts):
            datastore = Datastore.get(name)
            datastore.data = change(datastore.data)
            try:
                datastore.save()
                return datastore
            except DatastoreConflict:
                logging.getLogger("ats").debug(
                    "Datastore '%s' was changed by someone else, retrying", name
                )

        raise DatastoreConflict(
            f"Datastore '{name}' kept changing; gave up after {attempts} attempts"
        )

    @staticmethod
    def _write(name: str, data: dict, expected_version: int | None) -> "Datastore":
        body = {"data": data}
        if expected_version is not None:
            # 0: the datastore must not exist yet
            body["expected_version"] = expected_version

        response = httpx.put(
            _datastore_url(name),
            headers=AutomationServerConfig.auth_headers(),
            json=body,
        )
        if response.status_code == 409:
            raise DatastoreConflict(response.json().get("detail", response.text))
        response.raise_for_status()

        saved = Datastore.model_validate(response.json())
        logging.getLogger("ats").info(
            "Datastore '%s' %s (version %d, %d bytes)",
            name,
            "created" if response.status_code == 201 else "saved",
            saved.version,
            saved.size_bytes,
        )
        return saved
