# Automation Server Client

This is the automation server package that allows you to interface with the automation-server API.

## Installation

You can install the package using uv:

```bash
uv add "git+https://github.com/odense-rpa/automation-server-client.git"
```

## Usage
Here is a basic example of how to use the package:

```python
    # Set up configuration
    ats = AutomationServer.from_environment()    
    
    workqueue = ats.workqueue()   
```

For a more complete implementation see the [process-template](https://github.com/odense-rpa/process-template).

### Processing work items

```python
for item in workqueue:
    with item:
        ...  # do the work
```

- When the block finishes, the item is marked **completed**.
- When an exception leaves the block, the item is marked **failed**, with the reason as its message. The exception is then re-raised, which ends the loop and the run. This is deliberate: an error the automation didn't handle means something is wrong, and the process should stop.
  - A `WorkItemError("...")` message is stored as-is, so use it for business failures (e.g. "Citizen not found").
  - Other exceptions are stored with their type, e.g. `KeyError: 'url'`.
  - Messages are cut at 1,000 characters. The full traceback is always in the audit log.
- To fail one item and continue with the next, handle the error yourself, e.g. `item.fail("Citizen not found")` inside the block.

### Configuration

Configuration comes from `ATS_*` environment variables. When the Automation Server worker runs your process, it sets all of them (including `ATS_SESSION`), and a `.env` file is **not** read. That way a leftover `.env` can't override the worker's configuration. Outside the worker, for example when developing locally, a `.env` file is loaded if present.

## Features

* Interface with the automation-server API
* Retrieve process and workqueue status
* Retrieve work items for processing
* Logging actions and workitems

## Migrating from 0.3.x to 0.4.0

No code changes are needed for most automations. Behaviour to be aware of:

- `str(item)` and `repr(item)` no longer include the work item's `data`. Use `item.data` if you need it.
- Failed items get messages like `KeyError: 'url'` (type plus text). `WorkItemError` messages are stored as-is.
- `.env` isn't read when running under the worker.
- httpx request lines for the library's own calls to the Automation Server are no longer logged. Lines for other systems are unchanged.

Coming from 0.2.x, also read the 0.3.0 notes below. See the [changelog](CHANGELOG.md) for details.

## Migrating from 0.2.x to 0.3.0

The HTTP client was changed from `requests` to `httpx`. If your code catches `requests.HTTPError` from this library, update those to `httpx.HTTPStatusError`. See the [changelog](CHANGELOG.md) for the full list of changes.


## Development

Tests run with `uv run pytest`. Most are offline. The live tests need an Automation Server, either your dev stack (`ATS_URL`/`ATS_TOKEN` in `.env`) or the same throwaway server CI uses:

```bash
ATS_SERVER_TAG=0.8.1 ATS_PORT=8001 docker compose -f tests/ci/compose.yml up -d --wait
TOKEN=$(curl -s -X POST localhost:8001/accesstokens -H 'Content-Type: application/json' \
  -d '{"identifier":"local"}' | jq -r .access_token)
ATS_URL=http://localhost:8001 ATS_TOKEN=$TOKEN uv run pytest
docker compose -f tests/ci/compose.yml down -v
```

CI (`.github/workflows/ci.yml`) runs lint and the full suite against the latest automation-server release (required) and the nightly image (early warning), on pull requests, on main and every night.

### Releasing

1. Bump `version` in `pyproject.toml`, run `uv lock`, and add a `## [X.Y.Z] - date` section to `CHANGELOG.md`.
2. Merge to main, then tag and push: `git tag -a vX.Y.Z -m "Release vX.Y.Z" && git push origin vX.Y.Z`.
3. The release workflow runs CI on the tag and publishes the GitHub Release with the changelog section as notes.

## License
This project is licensed under the MIT License - see the LICENSE file for details.

## Contact
If you have any questions or feedback, please open a discussion or an issue.

