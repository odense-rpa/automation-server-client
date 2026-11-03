from unittest.mock import patch

import pytest

from automation_server_client import AutomationServerConfig


def test_AutomationServerConfig_no_env(monkeypatch):
    monkeypatch.delenv("ATS_URL", raising=False)
    monkeypatch.delenv("ATS_SESSION", raising=False)

    # Don't let a local .env supply ATS_URL
    with patch("automation_server_client._config.load_dotenv"):
        with pytest.raises(ValueError, match="ATS_URL is not set in the environment"):
            AutomationServerConfig.init_from_environment()


def test_AutomationServerConfig_env(monkeypatch):
    monkeypatch.setenv("ATS_URL", "http://localhost:8000")

    AutomationServerConfig.init_from_environment()

    assert AutomationServerConfig.url == "http://localhost:8000"
