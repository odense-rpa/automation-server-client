from automation_server_client import AutomationServerConfig


def test_workqueue_override_type_conversion(monkeypatch):
    """Test that workqueue_override is properly converted from string to int"""
    # Set environment variable as string (how env vars always come in)
    monkeypatch.setenv("ATS_URL", "http://localhost:8000")
    monkeypatch.setenv("ATS_WORKQUEUE_OVERRIDE", "12345")

    AutomationServerConfig.init_from_environment()

    # Should be converted to int
    assert isinstance(AutomationServerConfig.workqueue_override, int)
    assert AutomationServerConfig.workqueue_override == 12345


def test_workqueue_override_none_when_not_set(monkeypatch):
    """Test that workqueue_override is None when environment variable not set"""
    monkeypatch.delenv("ATS_WORKQUEUE_OVERRIDE", raising=False)
    monkeypatch.setenv("ATS_URL", "http://localhost:8000")

    AutomationServerConfig.init_from_environment()

    # Should be None when not set
    assert AutomationServerConfig.workqueue_override is None
