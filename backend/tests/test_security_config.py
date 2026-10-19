import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app


def test_production_requires_a_strong_secret():
    with pytest.raises(ValueError, match="SECRET_KEY is required"):
        Settings(DEBUG=False, SECRET_KEY="", _env_file=None)
    with pytest.raises(ValueError, match="at least 32 bytes"):
        Settings(DEBUG=False, SECRET_KEY="short", _env_file=None)


def test_development_uses_an_ephemeral_secret_and_explicit_origins():
    with pytest.warns(RuntimeWarning, match="ephemeral development secret"):
        first = Settings(DEBUG=True, SECRET_KEY="", _env_file=None)
    with pytest.warns(RuntimeWarning):
        second = Settings(DEBUG=True, SECRET_KEY="", _env_file=None)
    assert len(first.SECRET_KEY.encode("utf-8")) >= 32
    assert first.SECRET_KEY != second.SECRET_KEY
    assert "*" not in first.cors_origins


def test_cors_only_allows_configured_frontend():
    client = TestClient(app)
    allowed = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    denied = client.get("/health", headers={"Origin": "https://example.test"})
    assert "access-control-allow-origin" not in denied.headers
