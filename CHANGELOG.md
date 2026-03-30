# Changelog

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
