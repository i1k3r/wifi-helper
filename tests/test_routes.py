"""Automated tests for SUSESI Hotel Wi-Fi Helper routes and probe logic."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.logger import logger
from app.main import app
from app.probe import ProbeResult, check_mikrotik_health
from app.utils import get_client_ip, sanitize_room


@pytest.fixture
def client():
    """Test client fixture with lifespan support."""
    with TestClient(app) as test_client:
        yield test_client


# ============================================================================
# 1. Health & Root Endpoint Tests
# ============================================================================

def test_health_endpoint(client):
    """Test that /health returns a lightweight 200 OK without exposing internals."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_redirect(client):
    """Test that root / redirects to /wifi."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/wifi"


# ============================================================================
# 2. Healthy Gateway Tests: Connect Page vs Auto-Redirect
# ============================================================================

def test_wifi_helper_default_connect_page(client, monkeypatch):
    """
    Test Default / Experimental Flow (AUTO_REDIRECT=False):
    - MikroTik probe returns healthy (200)
    - Helper returns HTTP 200 with connect.html
    - Contains user-initiated button linking to http://10.1.3.1/login
    - No automatic redirect, no JavaScript redirect
    - Anti-caching headers are present
    - No failure logs generated
    """
    mock_probe = AsyncMock(
        return_value=ProbeResult(
            is_healthy=True,
            status_code=200,
            duration_ms=12.5,
            target_url="http://10.1.3.1/login",
        )
    )
    monkeypatch.setattr("app.main.check_mikrotik_health", mock_probe)
    monkeypatch.setattr(settings, "AUTO_REDIRECT", False)

    with patch.object(logger, "error") as mock_logger_error:
        response = client.get("/wifi?room=342", follow_redirects=False)

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "SUSESI LUXURY RESORT" in response.text
        assert "İnternete Bağlan" in response.text
        assert "Connect to Internet" in response.text
        assert "href=\"http://10.1.3.1/login\"" in response.text
        assert "Oda / Room: <span class=\"room-tag\">342</span>" in response.text
        assert "no-store" in response.headers["cache-control"]
        assert "no-cache" in response.headers["cache-control"]

        # Ensure NO failure logs are emitted on success
        mock_logger_error.assert_not_called()


def test_wifi_helper_auto_redirect_true(client, monkeypatch):
    """
    Test Auto-Redirect Flow (AUTO_REDIRECT=True):
    - MikroTik probe returns healthy (200)
    - Helper returns HTTP 302 (NOT 307)
    - Location header points to MIKROTIK_LOGIN_URL
    - Anti-caching headers are present
    - No failure logs are generated
    """
    mock_probe = AsyncMock(
        return_value=ProbeResult(
            is_healthy=True,
            status_code=200,
            duration_ms=12.5,
            target_url="http://10.1.3.1/login",
        )
    )
    monkeypatch.setattr("app.main.check_mikrotik_health", mock_probe)
    monkeypatch.setattr(settings, "AUTO_REDIRECT", True)

    with patch.object(logger, "error") as mock_logger_error:
        response = client.get("/wifi?room=342", follow_redirects=False)

        assert response.status_code == 302
        assert response.headers["location"] == "http://10.1.3.1/login"
        assert "no-store" in response.headers["cache-control"]
        assert "no-cache" in response.headers["cache-control"]
        assert "must-revalidate" in response.headers["cache-control"]
        assert response.headers["pragma"] == "no-cache"
        assert response.headers["expires"] == "0"

        # Ensure NO failure logs are emitted on success
        mock_logger_error.assert_not_called()


def test_wifi_helper_success_with_mikrotik_302(client, monkeypatch):
    """
    Test probe when MikroTik returns a 302 redirect (e.g. to ProSpot).
    Probe must treat 302 as healthy.
    """
    mock_probe = AsyncMock(
        return_value=ProbeResult(
            is_healthy=True,
            status_code=302,
            duration_ms=8.1,
            target_url="http://10.1.3.1/login",
        )
    )
    monkeypatch.setattr("app.main.check_mikrotik_health", mock_probe)
    monkeypatch.setattr(settings, "AUTO_REDIRECT", True)

    response = client.get("/wifi", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "http://10.1.3.1/login"


# ============================================================================
# 3. Failure Path Tests (Timeout, Connection Error, HTTP 5xx)
# ============================================================================

def test_wifi_helper_probe_timeout(client, monkeypatch):
    """Test behavior when MikroTik probe times out."""
    mock_probe = AsyncMock(
        return_value=ProbeResult(
            is_healthy=False,
            status_code=None,
            duration_ms=1501.2,
            error_type="timeout",
            error_message="Probe timed out after 1.5s",
            target_url="http://10.1.3.1/login",
        )
    )
    monkeypatch.setattr("app.main.check_mikrotik_health", mock_probe)

    with patch.object(logger, "error") as mock_logger_error:
        response = client.get("/wifi?room=104", follow_redirects=False)

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "SUSESI LUXURY RESORT" in response.text
        assert "Room: <span class=\"room-tag\">104</span>" in response.text
        assert "Wi-Fi Gateway Connecting" in response.text
        assert "İnternet Girişi Hazırlanıyor" in response.text

        # Verify structured JSON log was emitted
        mock_logger_error.assert_called_once()
        log_json = json.loads(mock_logger_error.call_args[0][0])
        assert log_json["event"] == "mikrotik_probe_failed"
        assert log_json["error_type"] == "timeout"
        assert log_json["room"] == "104"
        assert log_json["status_code"] is None


def test_wifi_helper_probe_connection_failure(client, monkeypatch):
    """Test behavior when MikroTik gateway is unreachable (Connection Refused)."""
    mock_probe = AsyncMock(
        return_value=ProbeResult(
            is_healthy=False,
            status_code=None,
            duration_ms=4.3,
            error_type="connection_error",
            error_message="Failed to connect to MikroTik gateway: Connection refused",
            target_url="http://10.1.3.1/login",
        )
    )
    monkeypatch.setattr("app.main.check_mikrotik_health", mock_probe)

    with patch.object(logger, "error") as mock_logger_error:
        response = client.get("/wifi", follow_redirects=False)

        assert response.status_code == 200
        assert "SUSESI LUXURY RESORT" in response.text
        mock_logger_error.assert_called_once()
        log_json = json.loads(mock_logger_error.call_args[0][0])
        assert log_json["error_type"] == "connection_error"
        assert log_json["room"] is None


def test_wifi_helper_probe_http_5xx(client, monkeypatch):
    """Test behavior when MikroTik gateway returns an HTTP 503 error."""
    mock_probe = AsyncMock(
        return_value=ProbeResult(
            is_healthy=False,
            status_code=503,
            duration_ms=15.0,
            error_type="http_5xx",
            error_message="MikroTik returned server error status HTTP 503",
            target_url="http://10.1.3.1/login",
        )
    )
    monkeypatch.setattr("app.main.check_mikrotik_health", mock_probe)

    with patch.object(logger, "error") as mock_logger_error:
        response = client.get("/wifi?room=501", follow_redirects=False)

        assert response.status_code == 200
        mock_logger_error.assert_called_once()
        log_json = json.loads(mock_logger_error.call_args[0][0])
        assert log_json["error_type"] == "http_5xx"
        assert log_json["status_code"] == 503
        assert log_json["room"] == "501"


# ============================================================================
# 4. Room Sanitization & Untrusted Input Tests
# ============================================================================

@pytest.mark.parametrize(
    "raw_input,expected_output",
    [
        ("342", "342"),
        ("A-102", "A-102"),
        ("suite_99", "suite_99"),
        ("  204  ", "204"),
        ("", None),
        (None, None),
        ("   ", None),
        ("<script>alert(1)</script>", None),
        ("room/../../etc", None),
        ("12345678901234567", None),  # Exceeds 16 characters
        ("room 101", None),          # Contains spaces
        ("room' OR '1'='1", None),    # SQL-like injection attempt
    ],
)
def test_sanitize_room(raw_input, expected_output):
    """Test room parameter sanitization with various valid and malicious inputs."""
    assert sanitize_room(raw_input) == expected_output


def test_wifi_helper_with_malicious_room_param_connect_page(client, monkeypatch):
    """Ensure malformed room query params on connect page are sanitized and safe."""
    mock_probe = AsyncMock(
        return_value=ProbeResult(
            is_healthy=True,
            status_code=200,
            duration_ms=10.0,
            target_url="http://10.1.3.1/login",
        )
    )
    monkeypatch.setattr("app.main.check_mikrotik_health", mock_probe)
    monkeypatch.setattr(settings, "AUTO_REDIRECT", False)

    response = client.get("/wifi?room=<script>alert(1)</script>", follow_redirects=False)
    assert response.status_code == 200
    assert "<script>alert(1)</script>" not in response.text
    assert "SUSESI Guest Wi-Fi Portal" in response.text


# ============================================================================
# 5. Direct Probe Unit Tests (Simulating HTTPX)
# ============================================================================

@pytest.mark.asyncio
async def test_probe_function_healthy_200():
    """Direct test of check_mikrotik_health with mocked httpx 200 response."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = httpx.Response(status_code=200, request=httpx.Request("GET", "http://10.1.3.1/login"))

    result = await check_mikrotik_health(mock_client, "http://10.1.3.1/login", 1.5)
    assert result.is_healthy is True
    assert result.status_code == 200
    assert result.error_type is None


@pytest.mark.asyncio
async def test_probe_function_healthy_302():
    """Direct test of check_mikrotik_health with mocked httpx 302 response."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = httpx.Response(
        status_code=302,
        headers={"Location": "http://login.prospot.online/"},
        request=httpx.Request("GET", "http://10.1.3.1/login")
    )

    result = await check_mikrotik_health(mock_client, "http://10.1.3.1/login", 1.5)
    assert result.is_healthy is True
    assert result.status_code == 302


@pytest.mark.asyncio
async def test_probe_function_timeout():
    """Direct test of check_mikrotik_health timeout handling."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.TimeoutException("Read timed out")

    result = await check_mikrotik_health(mock_client, "http://10.1.3.1/login", 1.5)
    assert result.is_healthy is False
    assert result.error_type == "timeout"
    assert result.status_code is None


@pytest.mark.asyncio
async def test_probe_function_connect_error():
    """Direct test of check_mikrotik_health connection error handling."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")

    result = await check_mikrotik_health(mock_client, "http://10.1.3.1/login", 1.5)
    assert result.is_healthy is False
    assert result.error_type == "connection_error"


@pytest.mark.asyncio
async def test_probe_function_503_error():
    """Direct test of check_mikrotik_health 503 error handling."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = httpx.Response(status_code=503, request=httpx.Request("GET", "http://10.1.3.1/login"))

    result = await check_mikrotik_health(mock_client, "http://10.1.3.1/login", 1.5)
    assert result.is_healthy is False
    assert result.error_type == "http_5xx"
    assert result.status_code == 503
