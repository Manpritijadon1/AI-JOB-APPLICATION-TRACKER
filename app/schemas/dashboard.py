from datetime import date

from pydantic import BaseModel

from app.models.job_application import JobStatus


class StatusCount(BaseModel):
    status: JobStatus
    count: int


class CategoryCount(BaseModel):
    category: str | None
    count: int


class ApplicationsOverTime(BaseModel):
    applied_date: date
    count: int


class DashboardStatsResponse(BaseModel):
    total_applications: int
    applications_by_status: list[StatusCount]
    applications_by_employment_type: list[CategoryCount]
    applications_by_location: list[CategoryCount]
    applications_over_time: list[ApplicationsOverTime]
    interview_count: int
    offer_count: int
    rejection_count: int
    interview_conversion_rate: float
    offer_conversion_rate: float
