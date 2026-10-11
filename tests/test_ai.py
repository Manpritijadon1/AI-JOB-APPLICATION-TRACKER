import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings
from tests.test_jobs import (
    DEFAULT_JOB,
    JOBS_URL,
    auth,
    create_user_and_token,
)

ANALYZE_URL = "/ai/analyze-resume"
RESUME_TEXT = "Backend engineer with experience building Python APIs and PostgreSQL services."
JOB_DESCRIPTION = "Seeking a backend engineer skilled in Python, PostgreSQL, and Docker."
ANALYSIS = {
    "resume_summary": "Backend engineer experienced with Python APIs and PostgreSQL.",
    "resume_summary_evidence": ["building Python APIs", "PostgreSQL services"],
    "job_match_summary": "The resume matches Python and PostgreSQL requirements.",
    "job_match_summary_evidence": ["Python APIs", "Python, PostgreSQL"],
    "matching_skills": [
        {"skill": "Python", "evidence": ["Python APIs"]},
        {"skill": "PostgreSQL", "evidence": ["PostgreSQL services"]},
    ],
    "missing_or_underrepresented_skills": [
        {
            "skill": "Docker",
            "job_description_evidence": ["Docker"],
        }
    ],
    "relevant_experience_highlights": [
        {
            "claim": "Experience building backend APIs.",
            "evidence": ["building Python APIs"],
        }
    ],
    "actionable_improvement_suggestions": [
        {
            "suggestion": "Add Docker experience if applicable.",
            "evidence": ["Docker"],
        }
    ],
}


def mock_ollama(client: TestClient, content: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        payload = json.loads(request.content)
        assert payload["model"] == "qwen2.5:3b"
        assert payload["stream"] is False
        return httpx.Response(
            200,
            json={"message": {"content": content}},
        )

    client.app.state.ollama_transport = httpx.MockTransport(handler)


def test_resume_analysis_requires_authentication(client: TestClient) -> None:
    response = client.post(
        ANALYZE_URL,
        json={"resume_text": RESUME_TEXT, "job_description": JOB_DESCRIPTION},
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "url",
    [
        "https://ollama.example.com",
        "http://192.0.2.10:11434",
        "http://user:password@127.0.0.1:11434",
    ],
)
def test_ollama_url_must_be_local_and_credential_free(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ollama_base_url=url)


def test_resume_analysis_returns_validated_structured_result(
    client: TestClient,
) -> None:
    token = create_user_and_token(client, "ai-user@example.com")
    mock_ollama(client, json.dumps(ANALYSIS))

    response = client.post(
        ANALYZE_URL,
        json={"resume_text": RESUME_TEXT, "job_description": JOB_DESCRIPTION},
        headers=auth(token),
    )

    assert response.status_code == 200
    assert response.json() == ANALYSIS


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        json.dumps({"unknown_field": "invalid schema"}),
        json.dumps(
            {
                **ANALYSIS,
                "matching_skills": [
                    {"skill": "Go", "evidence": ["not present in the resume"]}
                ],
            }
        ),
    ],
    ids=["malformed-json", "invalid-schema", "unsupported-evidence"],
)
def test_invalid_model_response_returns_gateway_error(
    client: TestClient,
    content: str,
) -> None:
    token = create_user_and_token(client, "ai-user@example.com")
    mock_ollama(client, content)

    response = client.post(
        ANALYZE_URL,
        json={"resume_text": RESUME_TEXT, "job_description": JOB_DESCRIPTION},
        headers=auth(token),
    )

    assert response.status_code == 502
    assert response.json()["detail"].startswith("Local AI service returned")


def test_unavailable_model_returns_service_unavailable(client: TestClient) -> None:
    token = create_user_and_token(client, "ai-user@example.com")

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model not found"})

    client.app.state.ollama_transport = httpx.MockTransport(handler)
    response = client.post(
        ANALYZE_URL,
        json={"resume_text": RESUME_TEXT, "job_description": JOB_DESCRIPTION},
        headers=auth(token),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Configured local AI model is unavailable"


def test_ollama_timeout_returns_gateway_timeout(client: TestClient) -> None:
    token = create_user_and_token(client, "ai-user@example.com")

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("test timeout")

    client.app.state.ollama_transport = httpx.MockTransport(handler)
    response = client.post(
        ANALYZE_URL,
        json={"resume_text": RESUME_TEXT, "job_description": JOB_DESCRIPTION},
        headers=auth(token),
    )

    assert response.status_code == 504
    assert response.json()["detail"] == "Local AI service timed out"


def test_ollama_connection_error_returns_service_unavailable(
    client: TestClient,
) -> None:
    token = create_user_and_token(client, "ai-user@example.com")

    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("test unavailable")

    client.app.state.ollama_transport = httpx.MockTransport(handler)
    response = client.post(
        ANALYZE_URL,
        json={"resume_text": RESUME_TEXT, "job_description": JOB_DESCRIPTION},
        headers=auth(token),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Local AI service is unavailable"


@pytest.mark.parametrize(
    "payload",
    [
        {"resume_text": " ", "job_description": JOB_DESCRIPTION},
        {"resume_text": RESUME_TEXT, "job_description": ""},
    ],
)
def test_blank_ai_input_is_rejected(client: TestClient, payload: dict) -> None:
    token = create_user_and_token(client, "ai-user@example.com")

    response = client.post(ANALYZE_URL, json=payload, headers=auth(token))

    assert response.status_code == 422


def test_configured_character_limit_is_enforced(client: TestClient) -> None:
    token = create_user_and_token(client, "ai-user@example.com")
    client.app.state.settings.ai_max_input_characters = 20

    response = client.post(
        ANALYZE_URL,
        json={"resume_text": RESUME_TEXT, "job_description": JOB_DESCRIPTION},
        headers=auth(token),
    )

    assert response.status_code == 413


def test_oversized_request_body_is_rejected(client: TestClient) -> None:
    token = create_user_and_token(client, "ai-user@example.com")

    response = client.post(
        ANALYZE_URL,
        json={
            "resume_text": "resume",
            "job_description": "description",
            "extra_data": "x" * 65536,
        },
        headers=auth(token),
    )

    assert response.status_code == 413


def test_application_assistance_summarizes_only_an_owned_job(
    client: TestClient,
) -> None:
    token = create_user_and_token(client, "ai-user@example.com")
    job_response = client.post(JOBS_URL, json=DEFAULT_JOB, headers=auth(token))
    assert job_response.status_code == 201
    application_source = json.dumps(
        {
            "company_name": DEFAULT_JOB["company_name"],
            "job_title": DEFAULT_JOB["job_title"],
            "status": DEFAULT_JOB["status"],
            "applied_date": DEFAULT_JOB["applied_date"],
            "location": DEFAULT_JOB["location"],
            "employment_type": DEFAULT_JOB["employment_type"],
            "notes": DEFAULT_JOB["notes"],
        },
        ensure_ascii=False,
    )
    result = {
        "summary": "Backend Engineer application at Acme Systems is Applied.",
        "summary_evidence": [
            DEFAULT_JOB["job_title"],
            DEFAULT_JOB["company_name"],
            '"status": "Applied"',
        ],
        "next_steps": [
            {
                "suggestion": "Follow up based on the saved note.",
                "evidence": ["Follow up next week"],
            }
        ],
    }

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": json.dumps(result)}})

    client.app.state.ollama_transport = httpx.MockTransport(handler)
    response = client.post(
        f"/ai/jobs/{job_response.json()['id']}/assistance",
        headers=auth(token),
    )

    assert "Acme Systems" in application_source
    assert response.status_code == 200
    assert response.json() == result


def test_application_assistance_hides_another_users_job(
    client: TestClient,
) -> None:
    owner_token = create_user_and_token(client, "owner@example.com")
    other_token = create_user_and_token(client, "other@example.com")
    job = client.post(JOBS_URL, json=DEFAULT_JOB, headers=auth(owner_token))
    assert job.status_code == 201

    def unexpected_call(_: httpx.Request) -> httpx.Response:
        pytest.fail("Ollama must not be called for another user's application")

    client.app.state.ollama_transport = httpx.MockTransport(unexpected_call)
    response = client.post(
        f"/ai/jobs/{job.json()['id']}/assistance",
        headers=auth(other_token),
    )

    assert response.status_code == 404


def test_application_assistance_requires_authentication(client: TestClient) -> None:
    response = client.post("/ai/jobs/1/assistance")

    assert response.status_code == 401
