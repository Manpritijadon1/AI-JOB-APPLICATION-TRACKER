from datetime import date, datetime
from typing import Annotated

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.job_application import JobStatus

NonBlankText = Annotated[str, Field(min_length=1, max_length=200)]


def normalize_required_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("This field must not be blank")
    return normalized


class JobApplicationCreate(BaseModel):
    """JSON body for POST /jobs."""

    company_name: NonBlankText
    job_title: NonBlankText
    job_url: AnyHttpUrl | None = None
    location: str | None = Field(default=None, max_length=200)
    employment_type: str | None = Field(default=None, max_length=100)
    status: JobStatus = JobStatus.APPLIED
    applied_date: date = Field(default_factory=date.today)
    notes: str | None = None

    @field_validator("company_name", "job_title")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("location", "employment_type")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class JobApplicationUpdate(BaseModel):
    """Partial JSON body for PATCH /jobs/{job_id}; omitted fields are unchanged."""

    company_name: NonBlankText | None = None
    job_title: NonBlankText | None = None
    job_url: AnyHttpUrl | None = None
    location: str | None = Field(default=None, max_length=200)
    employment_type: str | None = Field(default=None, max_length=100)
    status: JobStatus | None = None
    applied_date: date | None = None
    notes: str | None = None

    @field_validator("company_name", "job_title")
    @classmethod
    def validate_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return normalize_required_text(value)

    @field_validator("location", "employment_type")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None

    @model_validator(mode="after")
    def reject_null_for_required_fields(self) -> "JobApplicationUpdate":
        for field in ("company_name", "job_title", "status", "applied_date"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class JobApplicationResponse(BaseModel):
    """Public job-application fields returned by the job endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    company_name: str
    job_title: str
    job_url: str | None
    location: str | None
    employment_type: str | None
    status: JobStatus
    applied_date: date
    notes: str | None
    created_at: datetime
    updated_at: datetime


class JobApplicationPage(BaseModel):
    """Paginated response from GET /jobs."""

    items: list[JobApplicationResponse]
    total: int
    skip: int
    limit: int
