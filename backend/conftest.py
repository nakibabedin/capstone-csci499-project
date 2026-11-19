import os
from unittest.mock import Mock

import pytest

# Tests use isolated storage and mocked Supabase Auth.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_PUBLISHABLE_KEY", "test-key")
# Tests check the real login path even if backend/.env turns it off.
os.environ["DISABLE_SUPABASE"] = "false"

# test_db.py is a manual script that needs a real database.
collect_ignore = ["test_db.py"]


@pytest.fixture(autouse=True)
def fake_supabase_auth(monkeypatch):
    """Accept any bearer token without calling Supabase."""
    import requests

    response = Mock(status_code=200, ok=True)
    response.json.return_value = {"id": "11111111-1111-1111-1111-111111111111", "email": "test@example.com"}
    monkeypatch.setattr(requests, "get", Mock(return_value=response))
