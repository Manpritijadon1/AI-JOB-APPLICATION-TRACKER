from fastapi.testclient import TestClient

from tests.test_jobs import (
    DEFAULT_JOB,
    JOBS_URL,
    auth,
    create_user_and_token,
)

DASHBOARD_URL = "/dashboard/stats"


def test_dashboard_requires_authentication(client: TestClient) -> None:
    unauthenticated = client.get(DASHBOARD_URL)
    invalid_token = client.get(
        DASHBOARD_URL,
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert unauthenticated.status_code == 401
    assert invalid_token.status_code == 401


def test_empty_dashboard_returns_zero_counts_and_rates(client: TestClient) -> None:
    token = create_user_and_token(client, "owner@example.com")

    response = client.get(DASHBOARD_URL, headers=auth(token))

    assert response.status_code == 200
    assert response.json() == {
        "total_applications": 0,
        "applications_by_status": [
            {"status": "Applied", "count": 0},
            {"status": "Interview", "count": 0},
            {"status": "Offer", "count": 0},
            {"status": "Rejected", "count": 0},
            {"status": "Withdrawn", "count": 0},
        ],
        "applications_by_employment_type": [],
        "applications_by_location": [],
        "applications_over_time": [],
        "interview_count": 0,
        "offer_count": 0,
        "rejection_count": 0,
        "interview_conversion_rate": 0.0,
        "offer_conversion_rate": 0.0,
    }


def test_dashboard_aggregates_only_the_authenticated_users_jobs(
    client: TestClient,
) -> None:
    owner_token = create_user_and_token(client, "owner@example.com")
    other_token = create_user_and_token(client, "other@example.com")

    first = client.post(
        JOBS_URL,
        json={
            **DEFAULT_JOB,
            "company_name": "Example One",
            "status": "Interview",
            "applied_date": "2026-02-01",
        },
        headers=auth(owner_token),
    )
    second = client.post(
        JOBS_URL,
        json={
            **DEFAULT_JOB,
            "company_name": "Example Two",
            "status": "Offer",
            "employment_type": "Contract",
            "location": "New York",
            "applied_date": "2026-02-01",
        },
        headers=auth(owner_token),
    )
    rejected = client.post(
        JOBS_URL,
        json={
            **DEFAULT_JOB,
            "company_name": "Example Three",
            "status": "Rejected",
            "employment_type": None,
            "location": None,
            "applied_date": "2026-02-03",
        },
        headers=auth(owner_token),
    )
    other_job = client.post(
        JOBS_URL,
        json={**DEFAULT_JOB, "status": "Offer"},
        headers=auth(other_token),
    )
    assert all(
        response.status_code == 201
        for response in (first, second, rejected, other_job)
    )

    response = client.get(DASHBOARD_URL, headers=auth(owner_token))

    assert response.status_code == 200
    assert response.json() == {
        "total_applications": 3,
        "applications_by_status": [
            {"status": "Applied", "count": 0},
            {"status": "Interview", "count": 1},
            {"status": "Offer", "count": 1},
            {"status": "Rejected", "count": 1},
            {"status": "Withdrawn", "count": 0},
        ],
        "applications_by_employment_type": [
            {"category": None, "count": 1},
            {"category": "Contract", "count": 1},
            {"category": "Full-time", "count": 1},
        ],
        "applications_by_location": [
            {"category": None, "count": 1},
            {"category": "New York", "count": 1},
            {"category": "Remote", "count": 1},
        ],
        "applications_over_time": [
            {"applied_date": "2026-02-01", "count": 2},
            {"applied_date": "2026-02-03", "count": 1},
        ],
        "interview_count": 1,
        "offer_count": 1,
        "rejection_count": 1,
        "interview_conversion_rate": 33.33,
        "offer_conversion_rate": 33.33,
    }
