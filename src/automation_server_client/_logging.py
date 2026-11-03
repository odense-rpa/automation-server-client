import json
import logging
import sys
import httpx
import traceback
from contextvars import ContextVar

from typing import Dict, Any
from datetime import datetime
from ._config import AutomationServerConfig

_emitting: ContextVar[bool] = ContextVar('emitting', default=False)


# Custom HTTP Handler for logging
class AutomationServerLoggingHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.workitem_id = None
        self.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))

    def emit(self, record):
        if _emitting.get():
            return

        token = _emitting.set(True)
        try:
            log_record = self._format_log_record(record)

            if AutomationServerConfig.session is None or AutomationServerConfig.url == "":
                return

            # default=str: an extra value that isn't JSON (datetime, objects)
            # must not cost us the whole log record
            response = httpx.post(
                f"{AutomationServerConfig.url}/audit-logs",
                headers={
                    **AutomationServerConfig.auth_headers(),
                    "Content-Type": "application/json",
                },
                content=json.dumps(log_record, default=str),
            )
            response.raise_for_status()

        except Exception as e:
            print(
                f"Failed to send log to {AutomationServerConfig.url}/audit-logs: {e}",
                file=sys.stderr,
            )
        finally:
            _emitting.reset(token)

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

        # exc_info=True outside an except block gives (None, None, None)
        if record.exc_info and record.exc_info[0] is not None:
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


class _SkipOwnRequests(logging.Filter):
    """Drop httpx's "HTTP Request: ..." lines for this library's own calls.

    Only requests to the Automation Server (ATS_URL) are dropped. httpx lines
    for other systems are kept: clients such as kmd-nexus-client rely on them
    as required audit logs of their interactions.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not AutomationServerConfig.url or not record.args or len(record.args) < 2:
            return True
        try:
            base = str(httpx.URL(AutomationServerConfig.url)).rstrip("/")
            target = str(httpx.URL(str(record.args[1])))
        except Exception:
            return True
        return not (target == base or target.startswith(base + "/"))


# A filter on the "httpx" logger itself applies before any handler, so the lines
# disappear from the audit log and the console alike, but only for our requests.
logging.getLogger("httpx").addFilter(_SkipOwnRequests())
