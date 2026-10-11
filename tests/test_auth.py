from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.main import create_app
from app.models import User
from tests.conftest import TEST_JWT_SECRET

REGISTER_URL = "/auth/register"
LOGIN_URL = "/auth/login"
ME_URL = "/auth/me"
REGISTRATION = {
    "name": "Demo User",
    "email": "demo@example.com",
    "password": "test-password-123",
}


def register(client: TestClient) -> dict:
    response = client.post(REGISTER_URL, json=REGISTRATION)
    assert response.status_code == 201
    return response.json()


def test_successful_registration_returns_public_user(client: TestClient) -> None:
    response = client.post(
        REGISTER_URL,
        json={**REGISTRATION, "email": "  DEMO@example.com  "},
    )

    assert response.status_code == 201
    assert response.json()["name"] == REGISTRATION["name"]
    assert response.json()["email"] == REGISTRATION["email"]
    assert "hashed_password" not in response.json()
    assert "password" not in response.json()
    with client.app.state.db_session_factory() as session:
        user = session.scalar(select(User).where(User.email == REGISTRATION["email"]))
        assert user is not None
        assert user.hashed_password != REGISTRATION["password"]
        assert user.hashed_password.startswith("$argon2")


def test_registration_requires_configured_jwt_secret(tmp_path) -> None:
    database_path = tmp_path / "unconfigured.db"
    application = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite:///{database_path.as_posix()}",
            jwt_secret_key=None,
        )
    )

    with TestClient(application) as unconfigured_client:
        response = unconfigured_client.post(REGISTER_URL, json=REGISTRATION)

    application.state.db_engine.dispose()
    assert response.status_code == 503


def test_duplicate_email_is_rejected_after_normalization(client: TestClient) -> None:
    register(client)

    response = client.post(
        REGISTER_URL,
        json={**REGISTRATION, "email": "  DEMO@EXAMPLE.COM  "},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "An account with this email already exists"


def test_successful_login_returns_bearer_token(client: TestClient) -> None:
    register(client)

    response = client.post(
        LOGIN_URL,
        json={"email": " DEMO@EXAMPLE.COM ", "password": REGISTRATION["password"]},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_incorrect_password_is_rejected(client: TestClient) -> None:
    register(client)

    response = client.post(
        LOGIN_URL,
        json={"email": REGISTRATION["email"], "password": "incorrect-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


@pytest.mark.parametrize(
    "token",
    [
        "not-a-valid-jwt",
        jwt.encode(
            {
                "sub": "1",
                "iat": datetime.now(timezone.utc) - timedelta(minutes=2),
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            TEST_JWT_SECRET,
            algorithm="HS256",
        ),
    ],
    ids=["invalid", "expired"],
)
def test_invalid_or_expired_token_is_rejected(
    client: TestClient,
    token: str,
) -> None:
    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_authenticated_me_returns_current_user(client: TestClient) -> None:
    user = register(client)
    login_response = client.post(
        LOGIN_URL,
        json={"email": REGISTRATION["email"], "password": REGISTRATION["password"]},
    )
    token = login_response.json()["access_token"]

    response = client.get(ME_URL, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["id"] == user["id"]
    assert response.json()["email"] == REGISTRATION["email"]


def test_unauthenticated_me_is_rejected(client: TestClient) -> None:
    response = client.get(ME_URL)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
