# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## For you

You are a developer-assistant who is an expert in Python, API integration, and automation systems.

**Important:** Be professional and direct. Provide critical but constructive feedback. Focus on code quality, patterns, and best practices.

## Project Overview

This is an **Automation Server Client** library that provides Python classes and utilities for interfacing with the Automation Server API (https://github.com/odense-rpa/automation-server).

### Architecture

The library consists of several core components:

- **AutomationServer** (`_server.py`): Main entry point class that manages sessions, processes, and workqueues
- **Configuration** (`_config.py`): Environment-based configuration management using `AutomationServerConfig`
- **Data Models** (`_models.py`): Pydantic models representing API entities (Session, Process, Workqueue, WorkItem, Credential)
- **Logging** (`_logging.py`): Custom logging handler that transmits logs to the automation server
- **Client Integration**: RESTful API client using requests library with Bearer token authentication

### Data Flow

1. **Initialization**: `AutomationServer.from_environment()` loads configuration and sets up logging
2. **Session Management**: Optionally associate with a specific automation session
3. **Workqueue Processing**: Iterate through work items using the workqueue iterator pattern  
4. **Work Item Lifecycle**: Use context manager pattern for automatic status management
5. **Logging Integration**: All logs automatically transmitted to automation server when session is active

### Key Patterns

- **Environment Configuration**: All settings loaded from environment variables (ATS_*)
- **Context Managers**: WorkItem uses `__enter__`/`__exit__` for automatic status handling
- **Iterator Protocol**: Workqueue implements `__iter__`/`__next__` for seamless work item processing
- **Pydantic Models**: All API entities represented as Pydantic models with automatic validation and forward compatibility

## Development Setup & Environment

### Requirements

- **Python**: Requires Python 3.13+ (specified in `pyproject.toml`)
- **Package Manager**: Uses `uv` for dependency management
- **Dependencies**: `python-dotenv`, `requests`, `pydantic` (see `pyproject.toml`)

### Development Commands

#### Package Management (uv)
```bash
# Install dependencies
uv sync

# Add new dependency
uv add package-name

# Add development dependency  
uv add --dev package-name

# Run commands in virtual environment
uv run <command>
```

#### Testing
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_config.py

# Run with verbose output
uv run pytest -v

# Run specific test function
uv run pytest tests/test_config.py::test_AutomationServerConfig_env
```

### Environment Configuration

The library uses environment variables for configuration. Copy `.env.example` to `.env` and configure:

#### Required Environment Variables
```bash
ATS_URL=http://localhost:8000  # Automation server base URL
```

#### Optional Environment Variables
```bash
ATS_TOKEN=your_bearer_token           # Authentication token
ATS_SESSION=session_id                # Specific session to associate with
ATS_RESOURCE=resource_id              # Resource identifier
ATS_PROCESS=process_id                # Process identifier  
ATS_WORKQUEUE_OVERRIDE=workqueue_id   # Override workqueue ID
```

**Note**: `ATS_URL` is required and will raise `ValueError` if not set. Other variables are optional and will default to `None` or empty string.

## Core Classes & Usage Patterns

### AutomationServer (Main Entry Point)

**Location**: `src/automation_server_client/_server.py:8`

```python
from automation_server_client import AutomationServer

# Initialize from environment variables
ats = AutomationServer.from_environment()

# Access workqueue
workqueue = ats.workqueue()
```

**Key Methods**:
- `from_environment()` - Static factory method that loads config and sets up logging
- `workqueue()` - Returns associated Workqueue instance

### Workqueue (Work Item Management)

**Location**: `src/automation_server_client/_models.py:56`

```python
# Iterate through work items
for work_item in workqueue:
    with work_item:
        # Process the work item
        print(f"Processing: {work_item.reference}")
        # Work item automatically marked as completed on successful exit
```

**Key Methods**:
- `add_item(data: dict, reference: str)` - Add new work item to queue
- `clear_workqueue(workitem_status=None, days_older_than=None)` - Clear items from queue
- Implements iterator protocol for seamless processing

### WorkItem (Task Processing)

**Location**: `src/automation_server_client/_models.py:115`

WorkItem uses context manager pattern for automatic status handling:

```python
# Context manager automatically handles status
with work_item:
    # Item marked as "in progress" on entry
    work_item.update({"processed": True})
    # Item marked as "completed" on successful exit
    # Item marked as "failed" if exception occurs
```

**Manual Status Management**:
```python
work_item.complete("Processing finished successfully")
work_item.fail("Error occurred during processing")
work_item.pending_user("Waiting for user approval")
```

**Key Properties**:
- `id`, `data`, `reference`, `status`, `message`
- `data` contains the actual work item payload as dict
- `reference` is a human-readable identifier

### Credential (Authentication Data)

**Location**: `src/automation_server_client/_models.py:178`

```python
from automation_server_client import Credential

# Retrieve credential by name
cred = Credential.get_credential("my_system_login")
print(f"Username: {cred.username}")
print(f"Password: {cred.password}")
print(f"Additional data: {cred.data}")
```

### Datastore (State Between Runs)

**Location**: `src/automation_server_client/_models.py` (`Datastore`, `DatastoreConflict`)

```python
from automation_server_client import Datastore

Datastore.update("my-state", lambda data: {**data, "count": data.get("count", 0) + 1})
```

`get()` returns an empty document (version 0) when the datastore doesn't exist; `save()` sends the version that was read as `expected_version` and raises `DatastoreConflict` on 409; `update()` retries; `set()` overwrites. Writes are logged on the `ats` logger.

### Configuration Management

**Location**: `src/automation_server_client/_config.py:5`

```python
from automation_server_client import AutomationServerConfig

# Initialize from environment
AutomationServerConfig.init_from_environment()

# Access configuration
print(f"Server URL: {AutomationServerConfig.url}")
print(f"Current session: {AutomationServerConfig.session}")
print(f"Current work item: {AutomationServerConfig.workitem_id}")
```

**Important**: Configuration is global state shared across all instances.

## Testing & Quality Assurance

### Test Structure

Tests are located in `tests/` directory using pytest framework:
- `test_config.py` - Configuration and environment variable tests

### Running Tests

```bash
# Run all tests  
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_config.py

# Run specific test function
uv run pytest tests/test_config.py::test_AutomationServerConfig_no_env
```

### Test Patterns

**Environment Variable Testing**:
```python
def test_AutomationServerConfig_env():
    os.environ["ATS_URL"] = "http://localhost:8000"
    AutomationServerConfig.init_from_environment()
    assert AutomationServerConfig.url == "http://localhost:8000"
```

**Exception Testing**:
```python
def test_AutomationServerConfig_no_env():
    try:
        AutomationServerConfig.init_from_environment()
    except ValueError as e:
        assert str(e) == "ATS_URL is not set in the environment"
```

## API Integration Patterns

### Authentication

All API requests use Bearer token authentication:
```python
headers = {"Authorization": f"Bearer {AutomationServerConfig.token}"}
```

### Status Management

WorkItem status values:
- `"pending"` - Waiting to be processed
- `"in progress"` - Currently being processed  
- `"completed"` - Successfully finished
- `"failed"` - Processing failed
- `"pending user action"` - Waiting for user intervention

### Error Handling

All API calls use `response.raise_for_status()` to ensure HTTP errors are raised as exceptions. Handle these appropriately in your automation processes.

### API Endpoints

Key endpoints used by the client:
- `GET /sessions/{session_id}` - Retrieve session details
- `GET /processes/{process_id}` - Retrieve process details  
- `GET /workqueues/{workqueue_id}` - Retrieve workqueue details
- `GET /workqueues/{workqueue_id}/next_item` - Get next work item (204 if empty)
- `POST /workqueues/{workqueue_id}/add` - Add work item to queue
- `POST /workqueues/{workqueue_id}/clear` - Clear work items from queue
- `PUT /workitems/{workitem_id}` - Update work item data
- `PUT /workitems/{workitem_id}/status` - Update work item status
- `GET /credentials/by_name/{credential_name}` - Get credential by name
- `POST /sessions/{session_id}/log` - Send log entry to server

## Logging System

### Custom Logging Handler

**Location**: `src/automation_server_client/_logging.py:7`

The library includes a custom logging handler that automatically transmits logs to the automation server:

```python
class AutomationServerLoggingHandler(logging.Handler)
```

### Automatic Setup

When using `AutomationServer.from_environment()`, logging is automatically configured:

```python
ats = AutomationServer.from_environment()
# Logging is now set up and will transmit to server
```

**Default Configuration**:
- Log level: `INFO`
- Format: `"[%(levelname)s] %(name)s: %(message)s"`
- External package levels: `httpx` and `httpcore` set to `WARNING`

### Log Transmission

Logs are sent to the automation server when:
1. **Session is active** (`AutomationServerConfig.session` is set)
2. **Server URL is configured** (`AutomationServerConfig.url` is not empty)

**Log Payload**:
```json
{
  "workitem_id": 123,  // Current work item ID or null
  "message": "[INFO] my_module: Processing complete"
}
```

### Work Item Context

Logs automatically include work item context:
- When processing within a WorkItem context manager, `workitem_id` is included
- Outside of work item processing, `workitem_id` is `null`

### Error Handling

If log transmission fails, errors are printed to console but don't interrupt the process:
```python
print(f"Failed to send log to {self.url}: {e}")
```

### Usage Examples

```python
import logging

# Get logger for your module
logger = logging.getLogger(__name__)

# These logs will be transmitted to the server
logger.info("Starting process")
logger.warning("Potential issue detected")
logger.error("Process failed")

# Work item context automatically included
with work_item:
    logger.info("Processing work item")  # Includes work_item.id
```

## Code Standards & Patterns

### Code Organization

- **Pydantic Models**: All data models use Pydantic `BaseModel` for validation, type conversion, and forward compatibility
- **Static Methods**: Factory methods and utilities use `@staticmethod` decorator
- **Private Modules**: Internal modules prefixed with underscore (e.g., `_config.py`, `_models.py`)
- **Type Annotations**: Use `py.typed` marker file for type checking support

### Design Patterns

**Context Manager Pattern** - WorkItem lifecycle:
```python
def __enter__(self):
    # Set up processing context
    AutomationServerConfig.workitem_id = self.id
    
def __exit__(self, exc_type, exc_value, traceback):
    # Clean up and handle completion/failure
    if exc_type:
        self.fail(str(exc_value))
    elif self.status == "in progress":
        self.complete("Completed")
```

**Iterator Pattern** - Workqueue processing:
```python
def __iter__(self):
    return self

def __next__(self):
    # GET next item from API
    # Raise StopIteration if empty (204 status)
    # Return WorkItem instance
```

**Factory Pattern** - AutomationServer initialization:
```python
@staticmethod
def from_environment():
    # Initialize configuration from environment
    # Set up logging
    # Return configured instance
```

### Error Handling Conventions

**HTTP Error Propagation**:
```python
response = requests.get(url, headers=headers)
response.raise_for_status()  # Let HTTP errors bubble up
return Model(**response.json())
```

**Configuration Validation**:
```python
if AutomationServerConfig.url == "":
    raise ValueError("ATS_URL is not set in the environment")
```

**Graceful Logging Failures**:
```python
try:
    # Send log to server
    response.raise_for_status()
except Exception as e:
    print(f"Failed to send log: {e}")  # Don't interrupt process
```

### Naming Conventions

- **Environment Variables**: `ATS_` prefix (e.g., `ATS_URL`, `ATS_TOKEN`)
- **Class Names**: PascalCase (e.g., `AutomationServer`, `WorkItem`)
- **Method Names**: snake_case (e.g., `get_workqueue`, `add_item`)
- **Instance Variables**: snake_case (e.g., `session_id`, `workqueue_id`)

### Global State Management

**Configuration Singleton**:
- `AutomationServerConfig` uses class variables for shared state
- Thread-unsafe by design (single-process automation focus)
- `workitem_id` tracks current processing context globally

### API Response Handling

**Standard Pattern**:
1. Make HTTP request with authentication headers
2. Call `response.raise_for_status()` for error checking  
3. Validate JSON response into Pydantic model using `.model_validate(response.json())`
4. Return typed instance with automatic field validation and unknown field handling

### Forward Compatibility

**Pydantic Model Benefits**:
- **Unknown Field Handling**: Models ignore extra fields from API responses (`extra='ignore'` configuration)
- **Automatic Type Conversion**: String dates converted to `datetime` objects automatically
- **Validation**: Built-in validation with clear error messages for malformed data
- **API Evolution**: Follows REST "be liberal in what you accept" principle

**Example - Forward Compatible API Response**:
```python
# Server response with new fields added in future version
api_response = {
    "id": 123,
    "status": "completed",
    "created_at": "2023-01-01T10:00:00Z",
    # New fields added by server - safely ignored
    "priority": "high", 
    "assigned_to": "user123",
    "metadata": {"version": "2.0"}
}

# Client handles gracefully without code changes
work_item = WorkItem.model_validate(api_response)  # Works!
```

This prevents the classic API evolution problem where new server fields break existing clients.

## Environment Configuration Reference

### Complete Environment Variable List

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ATS_URL` | ✅ | - | Base URL of automation server (e.g., `http://localhost:8000`) |
| `ATS_TOKEN` | ❌ | `""` | Bearer token for API authentication |
| `ATS_SESSION` | ❌ | `None` | Session ID to associate with (enables logging transmission) |
| `ATS_RESOURCE` | ❌ | `None` | Resource identifier for the automation process |  
| `ATS_PROCESS` | ❌ | `None` | Process identifier for the automation process |
| `ATS_WORKQUEUE_OVERRIDE` | ❌ | `None` | Override workqueue ID (bypasses process-based queue) |

### Configuration Loading

```python
# Environment variables loaded via python-dotenv
from dotenv import load_dotenv
load_dotenv()  # Loads .env file if present

# Access via AutomationServerConfig
AutomationServerConfig.init_from_environment()
```

### Environment File Template

Create `.env` from `.env.example`:
```bash
# Required - Automation server base URL
ATS_URL=http://localhost:8000

# Optional - Authentication and context
ATS_TOKEN=your_bearer_token_here
ATS_SESSION=12345
ATS_RESOURCE=resource_001
ATS_PROCESS=process_001  
ATS_WORKQUEUE_OVERRIDE=queue_override_id
```

### Development vs Production

**Development**:
- Use local server URL (e.g., `http://localhost:8000`)
- Optional authentication for testing
- Session may be omitted for basic testing

**Production**:
- Use production server URL with HTTPS
- Authentication token required
- Session ID provided by automation server
- All context variables properly configured

## Development Notes

### Package Management
- Always use `uv sync` after cloning or pulling changes
- Use `uv add package-name` for new dependencies
- Development dependencies go in `[dependency-groups]` in `pyproject.toml`

### Code Quality
- Follow existing patterns for consistency
- Use Pydantic models for API entities with forward compatibility
- Implement appropriate error handling
- Test environment variable scenarios and forward compatibility
- Mock external API calls in tests

### Debugging
- Check environment variables are loaded correctly
- Verify API authentication and connectivity
- Monitor log transmission to automation server
- Use context managers properly for WorkItem processing