from datetime import datetime

from automation_server_client import Session, WorkItem, Credential


def test_session_forward_compatibility():
    """Test that Session model ignores unknown fields from API response"""
    # Mock response data with extra fields that don't exist in current model
    api_response_data = {
        "id": 1,
        "process_id": 100,
        "resource_id": 200,
        "dispatched_at": "2023-01-01T10:00:00Z",
        "status": "running",
        "stop_requested": False,
        "deleted": False,
        "parameters": "{}",
        "created_at": "2023-01-01T09:00:00Z",
        "updated_at": "2023-01-01T10:00:00Z",
        # These fields don't exist in current model but should be ignored
        "new_field_added_by_server": "some_value",
        "another_future_field": {"nested": "data"},
        "version": "2.0",
    }

    # Should not raise an exception even with extra fields
    session = Session.model_validate(api_response_data)

    # Verify known fields are still accessible
    assert session.id == 1
    assert session.process_id == 100
    assert session.status == "running"
    assert isinstance(session.dispatched_at, datetime)


def test_workitem_forward_compatibility():
    """Test that WorkItem model ignores unknown fields from API response"""
    api_response_data = {
        "id": 1,
        "data": {"key": "value"},
        "reference": "test-item",
        "locked": False,
        "status": "pending",
        "message": "",
        "workqueue_id": 10,
        "created_at": "2023-01-01T09:00:00Z",
        "updated_at": "2023-01-01T10:00:00Z",
        # Future fields
        "priority": "high",
        "assigned_to": "user123",
        "metadata": {"extra": "info"},
    }

    work_item = WorkItem.model_validate(api_response_data)

    assert work_item.id == 1
    assert work_item.data == {"key": "value"}
    assert work_item.reference == "test-item"
    assert work_item.status == "pending"


def test_credential_datetime_conversion():
    """Test that datetime fields are properly converted from strings"""
    api_response_data = {
        "id": 1,
        "name": "test_cred",
        "data": {},
        "username": "testuser",
        "password": "testpass",
        "deleted": False,
        "created_at": "2023-01-01T09:00:00Z",
        "updated_at": "2023-01-01T10:00:00Z",
    }

    credential = Credential.model_validate(api_response_data)

    assert isinstance(credential.created_at, datetime)
    assert isinstance(credential.updated_at, datetime)
    assert credential.created_at.year == 2023


def test_pydantic_validation_errors():
    """Test that invalid data still raises appropriate validation errors"""
    invalid_data = {
        "id": "not_an_int",  # Should be int
        "process_id": 100,
        "resource_id": 200,
        # Missing required fields
    }

    try:
        Session.model_validate(invalid_data)
        assert False, "Should have raised validation error"
    except Exception as e:
        # Should get pydantic validation error
        assert "validation error" in str(
            e
        ).lower() or "Input should be a valid integer" in str(e)


def test_backward_compatibility_with_minimal_data():
    """Test that models work with minimal required data"""
    minimal_session_data = {
        "id": 1,
        "process_id": 100,
        "resource_id": 200,
        "dispatched_at": "2023-01-01T10:00:00Z",
        "status": "running",
        "stop_requested": False,
        "deleted": False,
        "parameters": "{}",
        "created_at": "2023-01-01T09:00:00Z",
        "updated_at": "2023-01-01T10:00:00Z",
    }

    session = Session.model_validate(minimal_session_data)
    assert session.id == 1
    assert session.status == "running"

def test_session_with_null_parameters():
    """Test that models work with minimal required data"""
    minimal_session_data = {
        "id": 1,
        "process_id": 100,
        "resource_id": 200,
        "dispatched_at": "2023-01-01T10:00:00Z",
        "status": "running",
        "stop_requested": False,
        "deleted": False,
        "parameters": None,
        "created_at": "2023-01-01T09:00:00Z",
        "updated_at": "2023-01-01T10:00:00Z",
    }

    session = Session.model_validate(minimal_session_data)
    assert session.id == 1
    assert session.status == "running"
    assert session.parameters is None

    minimal_session_data["parameters"] = ""
    session = Session.model_validate(minimal_session_data)
    assert session.parameters == ""

