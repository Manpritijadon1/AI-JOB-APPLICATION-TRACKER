from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

EvidenceText = Annotated[str, Field(min_length=1, max_length=1000)]
BoundedText = Annotated[str, Field(min_length=1, max_length=4000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResumeAnalysisRequest(StrictModel):
    """JSON body for POST /ai/analyze-resume."""

    resume_text: str = Field(min_length=1)
    job_description: str = Field(min_length=1)

    @field_validator("resume_text", "job_description")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text must not be blank")
        return value.strip()


class EvidenceClaim(StrictModel):
    claim: BoundedText
    evidence: list[EvidenceText] = Field(min_length=1, max_length=5)


class SkillEvidence(StrictModel):
    skill: Annotated[str, Field(min_length=1, max_length=100)]
    evidence: list[EvidenceText] = Field(min_length=1, max_length=5)


class SkillGap(StrictModel):
    skill: Annotated[str, Field(min_length=1, max_length=100)]
    job_description_evidence: list[EvidenceText] = Field(min_length=1, max_length=5)


class ImprovementSuggestion(StrictModel):
    suggestion: BoundedText
    evidence: list[EvidenceText] = Field(min_length=1, max_length=5)


class ResumeAnalysisResponse(StrictModel):
    resume_summary: BoundedText
    resume_summary_evidence: list[EvidenceText] = Field(min_length=1, max_length=5)
    job_match_summary: BoundedText
    job_match_summary_evidence: list[EvidenceText] = Field(min_length=1, max_length=5)
    matching_skills: list[SkillEvidence] = Field(max_length=50)
    missing_or_underrepresented_skills: list[SkillGap] = Field(max_length=50)
    relevant_experience_highlights: list[EvidenceClaim] = Field(max_length=20)
    actionable_improvement_suggestions: list[ImprovementSuggestion] = Field(
        max_length=20
    )


class ApplicationAssistanceResponse(StrictModel):
    summary: BoundedText
    summary_evidence: list[EvidenceText] = Field(min_length=1, max_length=5)
    next_steps: list[ImprovementSuggestion] = Field(min_length=1, max_length=10)


class AIErrorResponse(StrictModel):
    detail: str
