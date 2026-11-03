# Changelog

## [0.4.0] - 2026-11-03

### Fixed
- Failed work items no longer dump their `data` into the log. `WorkItem.__str__` and `repr()` leave out `data`, which could be very large and contain personal data (a nested test item produced a 31 KB audit log entry, repeated again in the automation's stderr).
- Work item failures are logged with `exc_info`, so the exception type and traceback reach the audit log's own fields instead of being lost.
- The failure message stored on the work item now includes the exception type for unexpected errors (`KeyError: 'url'` instead of `'url'`). `WorkItemError` messages are kept as-is, since they are business messages from the automation.
- Logging handler: infinite recursion when httpx logs at INFO level during an emit.
- Logging handler: a record is no longer dropped when an `extra=` value isn't JSON serializable (e.g. a `datetime`; it's sent as a string), or when `exc_info=True` is used outside an `except` block. Send failures are printed to stderr instead of stdout.
- If the server can't be reached when a work item is marked failed, the automation's own exception is still the one raised (the status error is logged next to it). The logging handler is always detached from the item, even when a status update fails.
- Failure messages stored on work items are capped at 1,000 characters.

### Changed
- httpx's `HTTP Request: ...` INFO lines are no longer logged for this library's own calls to the Automation Server (otherwise every fetch and status update became an audit log entry, and `get_item_by_reference` put references in the log). httpx lines for other systems are unaffected, so clients like kmd-nexus-client keep their audit logging.
- `.env` is no longer read when running under the worker (when `ATS_SESSION` is set), so a stray `.env` can't override the worker's configuration.

### Added
- `Process.git_options` field.

### Security
- Dependency security: minimum versions raised so automations that update to 0.4.0 also get the fixes, even with an older lock file of their own:
  - `certifi>=2026.10.18`: drops the compromised emSign root CAs (GHSA-6q48-6c7w-9gw2, critical). certifi provides httpx's CA bundle.
  - `anyio>=4.14.2`: TLS certificate spoofing via IDNA host name encoding (CVE-2026-63374, critical) and a process-pool hang (CVE-2026-64847).
  - `python-dotenv>=1.2.2`: symlink file overwrite in `set_key()`/`unset_key()` (CVE-2026-28684; the library only uses `load_dotenv()`, but the floor costs nothing).
  - Lock file also updated: idna 3.20 (CVE-2026-45409), pytest 9.2.0 (dev, CVE-2025-71176). `pip-audit` and Trivy report no known vulnerabilities.
- `str(AutomationServer)` shows only IDs and names (`session=8, process=Test-process`) instead of the full `Session` and `Process`, which included the repo URL and git options.
- `Credential.password` is left out of `repr()`, so logging a credential object no longer prints the password. Note that `model_dump()` and `model_dump_json()` still include it.

### Internal
- Tests send the `ATS_TOKEN` when talking to the dev server, so the live tests also run against servers that require authentication.

---

## [0.3.0] - 2026-03-30

### Added
- `Workqueue.get_workqueue_by_name()` — look up a workqueue by name
- `WorkItem` fields: `started_at`, `work_duration_seconds`
- `AutomationServerConfig.auth_headers()` — shared helper that omits the `Authorization` header when no token is configured

### Changed
- Replaced `requests` with `httpx` as the HTTP client
- All models: fields that may be absent in API responses are now `Optional` (`Session.resource_id`, `Session.dispatched_at`, `Session.parameters`, `Process.id`, `Process.description`, `Process.requirements`, `Process.target_type`, `Process.target_source`, `Workqueue.id`, `Workqueue.description`, `WorkItem.id`, `WorkItem.reference`, `Credential.id`, `Credential.username`, `Credential.password`)
- All public methods now have concise docstrings

### Fixed
- `AutomationServer.__init__` was silently discarding `session_id` due to a no-op assignment
- Logging error message referenced stale API endpoint (`/sessions/{id}/log` → `/audit-logs`)
- Two malformed attribute names in the logging handler's `standard_attrs` set (`asctimename`, `taskNamethread`) caused standard log fields to leak into `structured_data`
- `WorkItem.__exit__` called `complete()` even after a failure if the preceding `fail()` had not updated the status fast enough

---

## [0.2.1] - 2025-10-30

### Added
- `WorkItemStatus` enum (`new`, `in progress`, `completed`, `failed`, `pending user action`) — exported from the package
- `Workqueue.get_item_by_reference()` — retrieve work items by reference string, with optional status filter
- `Workqueue.clear_workqueue()` now typed with `WorkItemStatus`

---

## [0.2.0] - 2025-04-10

### Added
- `AutomationServer.from_environment()` — static factory that initializes config and logging in one call
- Custom structured logging handler (`AutomationServerLoggingHandler`) that posts log records to the audit-logs endpoint
- Workitem context tracking in the logging handler; log records automatically include the current `workitem_id`
- Pydantic forward-compatibility test suite

### Changed
- `WorkItem.data` is now `dict` instead of a raw JSON string
- Logging setup centralised; workitem tracking removed from `AutomationServerConfig`
- `Process` optional fields (`target_credentials_id`, `credentials_id`, `workqueue_id`) now properly typed as `int | None`

### Fixed
- `workqueue_id` check in `AutomationServer.__init__` incorrectly rejected `None` values

---

## [0.1.0] - 2025-04-03

Initial release. Core client library extracted from the automation-server repository.

### Added
- `AutomationServer` — main entry point with session, process, and workqueue management
- `AutomationServerConfig` — environment-based configuration (`ATS_URL`, `ATS_TOKEN`, `ATS_SESSION`, `ATS_RESOURCE`, `ATS_PROCESS`, `ATS_WORKQUEUE_OVERRIDE`)
- Pydantic models for all API entities: `Session`, `Process`, `Workqueue`, `WorkItem`, `Credential`
- `WorkItem` context manager for automatic status handling (completed/failed on exit)
- `Workqueue` iterator protocol for sequential work item processing
- `Credential.get_credential()` — retrieve credentials by name
- All models use `extra="ignore"` for forward compatibility with new API fields
