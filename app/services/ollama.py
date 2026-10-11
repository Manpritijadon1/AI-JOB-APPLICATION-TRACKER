from typing import TypeVar

import httpx
from fastapi import HTTPException, status
from pydantic import BaseModel, ValidationError

from app.core.config import Settings

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


def generate_structured_response(
    *,
    settings: Settings,
    system_prompt: str,
    user_prompt: str,
    response_model: type[ResponseModel],
    transport: httpx.BaseTransport | None = None,
) -> ResponseModel:
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "format": "json",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    try:
        with httpx.Client(
            transport=transport,
            timeout=settings.ollama_timeout_seconds,
        ) as client:
            response = client.post(
                f"{settings.ollama_base_url.rstrip('/')}/api/chat",
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Local AI service timed out",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local AI service is unavailable",
        ) from exc

    if response.status_code == status.HTTP_404_NOT_FOUND:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configured local AI model is unavailable",
        )
    if response.is_error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Local AI service returned an error",
        )

    try:
        envelope = response.json()
        content = envelope["message"]["content"]
        if not isinstance(content, str) or len(content) > 65536:
            raise ValueError("Invalid model response content")
        result = response_model.model_validate_json(content)
    except (ValueError, KeyError, TypeError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Local AI service returned an invalid response",
        ) from exc
    return result


def validate_evidence(
    response: BaseModel,
    *,
    resume_text: str,
    job_description: str,
) -> None:
    resume_source = resume_text.casefold()
    job_source = job_description.casefold()

    def require_evidence(evidence: list[str], sources: tuple[str, ...]) -> None:
        if any(
            not any(evidence_item.casefold() in source for source in sources)
            for evidence_item in evidence
        ):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Local AI service returned unsupported evidence",
            )

    if "resume_summary_evidence" in type(response).model_fields:
        require_evidence(response.resume_summary_evidence, (resume_source,))
        require_evidence(response.job_match_summary_evidence, (resume_source, job_source))
        for skill in response.matching_skills:
            require_evidence(skill.evidence, (resume_source,))
            if skill.skill.casefold() not in resume_source:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Local AI service returned an unsupported matching skill",
                )
        for skill in response.missing_or_underrepresented_skills:
            require_evidence(skill.job_description_evidence, (job_source,))
            if skill.skill.casefold() not in job_source:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Local AI service returned an unsupported skill gap",
                )
        for highlight in response.relevant_experience_highlights:
            require_evidence(highlight.evidence, (resume_source,))
        for suggestion in response.actionable_improvement_suggestions:
            require_evidence(suggestion.evidence, (resume_source, job_source))
    elif "summary_evidence" in type(response).model_fields:
        require_evidence(response.summary_evidence, (resume_source,))
        for next_step in response.next_steps:
            require_evidence(next_step.evidence, (resume_source,))
