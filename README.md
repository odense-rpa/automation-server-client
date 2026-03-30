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

## Features

* Interface with the automation-server API
* Retrieve process and workqueue status
* Retrieve work items for processing
* Logging actions and workitems

## Migrating from 0.2.x to 0.3.0

The HTTP client was changed from `requests` to `httpx`. If your code catches `requests.HTTPError` from this library, update those to `httpx.HTTPStatusError`. See the [changelog](CHANGELOG.md) for the full list of changes.


## License
This project is licensed under the MIT License - see the LICENSE file for details.

## Contact
If you have any questions or feedback, please open a discussion or an issue.

