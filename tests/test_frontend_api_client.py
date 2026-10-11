import httpx
import pytest

from frontend.api_client import APIClient, APIError


def test_api_client_sends_bearer_token_without_exposing_it() -> None:
    token = "test-token-must-not-appear-in-errors"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == f"Bearer {token}"
        return httpx.Response(200, json={"status": "ok"})

    result = APIClient(
        "http://testserver",
        transport=httpx.MockTransport(handler),
    ).request("GET", "/auth/me", token=token)

    assert result == {"status": "ok"}


def test_api_client_sends_registration_without_auth_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "Authorization" not in request.headers
        assert request.read().decode().find("example-password") >= 0
        return httpx.Response(201, json={"id": 1})

    result = APIClient(
        "http://testserver",
        transport=httpx.MockTransport(handler),
    ).request(
        "POST",
        "/auth/register",
        json={
            "name": "Demo",
            "email": "demo@example.com",
            "password": "example-password",
        },
    )

    assert result == {"id": 1}


def test_unauthorized_response_is_sanitized_and_marked_for_logout() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "secret-bearing server detail"})

    with pytest.raises(APIError) as raised:
        APIClient(
            "http://testserver",
            transport=httpx.MockTransport(handler),
        ).request("GET", "/auth/me", token="private-token")

    assert raised.value.authentication_failed
    assert "private-token" not in raised.value.message
    assert "secret-bearing" not in raised.value.message
    assert "sign in again" in raised.value.message


def test_invalid_login_shows_safe_credential_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Incorrect email or password"})

    with pytest.raises(APIError) as raised:
        APIClient(
            "http://testserver",
            transport=httpx.MockTransport(handler),
        ).request("POST", "/auth/login", json={"password": "not-logged"})

    assert raised.value.authentication_failed
    assert raised.value.message == "Incorrect email or password"


def test_validation_error_does_not_surface_submitted_input() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "detail": [
                    {
                        "loc": ["body", "password"],
                        "msg": "String should have at least 8 characters",
                        "input": "sensitive-short-password",
                    }
                ]
            },
        )

    with pytest.raises(APIError) as raised:
        APIClient(
            "http://testserver",
            transport=httpx.MockTransport(handler),
        ).request("POST", "/auth/register", json={"password": "sensitive-short-password"})

    assert "password: String should have at least 8 characters" in raised.value.message
    assert "sensitive-short-password" not in raised.value.message


def test_successful_delete_returns_truthy_completion() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    result = APIClient(
        "http://testserver",
        transport=httpx.MockTransport(handler),
    ).request("DELETE", "/jobs/1", token="private-token")

    assert result is True


def test_connection_failure_has_safe_message() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused with sensitive detail")

    with pytest.raises(APIError) as raised:
        APIClient(
            "http://testserver",
            transport=httpx.MockTransport(handler),
        ).request("GET", "/dashboard/stats", token="private-token")

    assert raised.value.status_code == 0
    assert "Could not connect" in raised.value.message
    assert "sensitive detail" not in raised.value.message
