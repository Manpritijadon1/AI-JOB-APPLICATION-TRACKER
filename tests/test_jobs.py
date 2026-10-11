from datetime import date

import pytest
from fastapi.testclient import TestClient

from tests.test_auth import LOGIN_URL, REGISTER_URL

JOBS_URL = "/jobs"
PASSWORD = "test-password-123"
DEFAULT_JOB = {
    "company_name": "Acme Systems",
    "job_title": "Backend Engineer",
    "job_url": "https://jobs.example.com/backend",
    "location": "Remote",
    "employment_type": "Full-time",
    "status": "Applied",
    "applied_date": "2026-01-15",
    "notes": "Follow up next week",
}


def create_user_and_token(client: TestClient, email: str) -> str:
    registration = client.post(
        REGISTER_URL,
        json={"name": "Demo User", "email": email, "password": PASSWORD},
    )
    assert registration.status_code == 201
    login = client.post(LOGIN_URL, json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    return login.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_job(client: TestClient, token: str, **overrides: object) -> dict:
    response = client.post(JOBS_URL, json={**DEFAULT_JOB, **overrides}, headers=auth(token))
    assert response.status_code == 201
    return response.json()


def test_create_and_read_job(client: TestClient) -> None:
    token = create_user_and_token(client, "owner@example.com")
    created = create_job(client, token)

    response = client.get(f"{JOBS_URL}/{created['id']}", headers=auth(token))

    assert created["company_name"] == DEFAULT_JOB["company_name"]
    assert created["job_title"] == DEFAULT_JOB["job_title"]
    assert created["status"] == "Applied"
    assert created["applied_date"] == date(2026, 1, 15).isoformat()
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_patch_and_delete_job(client: TestClient) -> None:
    token = create_user_and_token(client, "owner@example.com")
    created = create_job(client, token)

    updated = client.patch(
        f"{JOBS_URL}/{created['id']}",
        json={"status": "Interview", "notes": "Technical round scheduled"},
        headers=auth(token),
    )
    deleted = client.delete(f"{JOBS_URL}/{created['id']}", headers=auth(token))
    after_delete = client.get(f"{JOBS_URL}/{created['id']}", headers=auth(token))

    assert updated.status_code == 200
    assert updated.json()["status"] == "Interview"
    assert updated.json()["notes"] == "Technical round scheduled"
    assert deleted.status_code == 204
    assert after_delete.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"company_name": " ", "job_title": "Engineer"},
        {"company_name": "Acme", "job_title": ""},
        {"company_name": "Acme", "job_title": "Engineer", "status": "Pending"},
        {"company_name": "Acme", "job_title": "Engineer", "job_url": "not-a-url"},
        {"company_name": "Acme", "job_title": "Engineer", "applied_date": "not-a-date"},
    ],
)
def test_invalid_create_input_is_rejected(client: TestClient, payload: dict) -> None:
    token = create_user_and_token(client, "owner@example.com")

    response = client.post(JOBS_URL, json=payload, headers=auth(token))

    assert response.status_code == 422


def test_null_for_required_update_field_is_rejected(client: TestClient) -> None:
    token = create_user_and_token(client, "owner@example.com")
    job = create_job(client, token)

    response = client.patch(
        f"{JOBS_URL}/{job['id']}",
        json={"status": None},
        headers=auth(token),
    )

    assert response.status_code == 422


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"}])
def test_jobs_require_valid_authentication(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    response = client.get(JOBS_URL, headers=headers)

    assert response.status_code == 401


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_other_users_job_is_not_accessible(
    client: TestClient,
    method: str,
) -> None:
    owner_token = create_user_and_token(client, "owner@example.com")
    other_token = create_user_and_token(client, "other@example.com")
    job = create_job(client, owner_token)
    request = getattr(client, method)

    if method == "patch":
        response = request(
            f"{JOBS_URL}/{job['id']}",
            json={"status": "Offer"},
            headers=auth(other_token),
        )
    else:
        response = request(f"{JOBS_URL}/{job['id']}", headers=auth(other_token))

    assert response.status_code == 404
    assert response.json()["detail"] == "Job application not found"


def test_missing_job_returns_404(client: TestClient) -> None:
    token = create_user_and_token(client, "owner@example.com")

    response = client.get(f"{JOBS_URL}/999", headers=auth(token))

    assert response.status_code == 404


def test_list_supports_pagination_search_and_status_filter(client: TestClient) -> None:
    token = create_user_and_token(client, "owner@example.com")
    create_job(client, token, company_name="Acme Systems", job_title="Backend Engineer")
    create_job(
        client,
        token,
        company_name="Acme Labs",
        job_title="Platform Engineer",
        status="Interview",
    )
    create_job(client, token, company_name="Other Company", job_title="Backend Engineer")

    response = client.get(
        JOBS_URL,
        params={
            "search": "acme",
            "status": "Interview",
            "skip": 0,
            "limit": 1,
            "sort_by": "company_name",
            "sort_order": "asc",
        },
        headers=auth(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["company_name"] == "Acme Labs"
    assert body["items"][0]["status"] == "Interview"
    assert body["skip"] == 0
    assert body["limit"] == 1


def test_list_pagination_and_search_only_include_current_users_jobs(
    client: TestClient,
) -> None:
    owner_token = create_user_and_token(client, "owner@example.com")
    other_token = create_user_and_token(client, "other@example.com")
    create_job(client, owner_token, company_name="Acme One")
    create_job(client, owner_token, company_name="Acme Two")
    create_job(client, other_token, company_name="Acme Secret")

    response = client.get(
        JOBS_URL,
        params={
            "search": "Acme",
            "skip": 1,
            "limit": 1,
            "sort_by": "company_name",
            "sort_order": "asc",
        },
        headers=auth(owner_token),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["company_name"] == "Acme Two"


@pytest.mark.parametrize(
    "params",
    [
        {"skip": -1},
        {"limit": 0},
        {"limit": 101},
        {"sort_by": "hashed_password"},
        {"sort_order": "random"},
        {"status": "Pending"},
        {"search": "   "},
    ],
)
def test_invalid_list_parameters_are_rejected(
    client: TestClient,
    params: dict[str, object],
) -> None:
    token = create_user_and_token(client, "owner@example.com")

    response = client.get(JOBS_URL, params=params, headers=auth(token))

    assert response.status_code == 422
