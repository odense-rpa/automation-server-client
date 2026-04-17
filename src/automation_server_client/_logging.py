import logging
import httpx
import traceback
from contextvars import ContextVar

from typing import Dict, Any
from datetime import datetime
from ._config import AutomationServerConfig


# Custom HTTP Handler for logging
class AutomationServerLoggingHandler(logging.Handler):
    # Prevent recursive logging if httpx triggers logging at INFO level or below
    _emitting: ContextVar[bool] = ContextVar('emitting', default=False)

    def __init__(self):
        super().__init__()
        self.workitem_id = None
        self.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))

    def emit(self, record):
        if self._emitting.get():
            return

        log_record = self._format_log_record(record)

        if AutomationServerConfig.session is None or AutomationServerConfig.url == "":
            return

        token = self._emitting.set(True)
        try:
            response = httpx.post(
                f"{AutomationServerConfig.url}/audit-logs",
                headers=AutomationServerConfig.auth_headers(),
                json=log_record,
            )
            response.raise_for_status()

        except Exception as e:
            # Handle any exceptions that occur when sending the log
            print(
                f"Failed to send log to {AutomationServerConfig.url}/audit-logs: {e}"
            )
        finally:
            self._emitting.reset(token)

    def start_workitem(self, workitem_id: int):
        self.workitem_id = workitem_id

    def end_workitem(self):
        self.workitem_id = None

    def _format_log_record(self, record: logging.LogRecord) -> Dict[str, Any]:
        """
        Convert LogRecord to api format.
        """
        # Extract structured data from record.__dict__ (from extra parameter)
        structured_data = {}

        # Get all extra fields (anything not in standard LogRecord attributes)
        standard_attrs = {
            "asctime",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "lineno",
            "funcName",
            "name",
            "created",
            "msecs",
            "relativeCreated",
            "taskName",
            "thread",
            "threadName",
            "processName",
            "process",
            "exc_info",
            "exc_text",
            "stack_info",
            "message",
        }

        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                structured_data[key] = value

        # Handle exception information
        exception_type = None
        exception_message = None
        traceback_text = None

        if record.exc_info:
            exception_type = record.exc_info[0].__name__
            exception_message = str(record.exc_info[1])
            traceback_text = "".join(traceback.format_exception(*record.exc_info))

        return {
            "session_id": AutomationServerConfig.session,
            "workitem_id": self.workitem_id,  # Now uses instance variable
            "message": record.getMessage(),
            "level": record.levelname,
            "logger_name": record.name,
            "module": record.module if hasattr(record, "module") else record.filename,
            "function_name": record.funcName,
            "line_number": record.lineno,
            "exception_type": exception_type,
            "exception_message": exception_message,
            "traceback": traceback_text,
            "structured_data": structured_data if structured_data else None,
            "event_timestamp": datetime.fromtimestamp(record.created).isoformat(),
        }


ats_logging_handler = AutomationServerLoggingHandler()
