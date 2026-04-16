import pytest
from auth import login_user

def test_login_success():
    assert login_user("admin", "admin123") == "JWT-TOKEN-123"

def test_login_service_account():
    # Simulates a service account login where the username is not provided via basic auth correctly
    # This should fail because of our bug in auth.py
    assert login_user(None, "service-token") == "JWT-TOKEN-123"
