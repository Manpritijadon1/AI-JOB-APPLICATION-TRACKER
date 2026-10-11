from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.dependencies import get_db
from app.models import JobApplication, JobStatus, User
from app.schemas.dashboard import (
    ApplicationsOverTime,
    CategoryCount,
    DashboardStatsResponse,
    StatusCount,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    summary="Get statistics for the authenticated user's applications",
)
def read_dashboard_stats(
    db: DbSession,
    current_user: CurrentUser,
) -> DashboardStatsResponse:
    user_filter = JobApplication.user_id == current_user.id
    total_applications = db.scalar(
        select(func.count(JobApplication.id)).where(user_filter)
    ) or 0

    status_rows = db.execute(
        select(JobApplication.status, func.count(JobApplication.id))
        .where(user_filter)
        .group_by(JobApplication.status)
    ).all()
    status_counts_by_value = {
        status_value: count for status_value, count in status_rows
    }
    applications_by_status = [
        StatusCount(
            status=job_status,
            count=status_counts_by_value.get(job_status, 0),
        )
        for job_status in JobStatus
    ]

    employment_rows = db.execute(
        select(JobApplication.employment_type, func.count(JobApplication.id))
        .where(user_filter)
        .group_by(JobApplication.employment_type)
        .order_by(JobApplication.employment_type.asc())
    ).all()
    applications_by_employment_type = [
        CategoryCount(category=category, count=count)
        for category, count in employment_rows
    ]

    location_rows = db.execute(
        select(JobApplication.location, func.count(JobApplication.id))
        .where(user_filter)
        .group_by(JobApplication.location)
        .order_by(JobApplication.location.asc())
    ).all()
    applications_by_location = [
        CategoryCount(category=category, count=count)
        for category, count in location_rows
    ]

    time_rows = db.execute(
        select(JobApplication.applied_date, func.count(JobApplication.id))
        .where(user_filter)
        .group_by(JobApplication.applied_date)
        .order_by(JobApplication.applied_date.asc())
    ).all()
    applications_over_time = [
        ApplicationsOverTime(applied_date=applied_date, count=count)
        for applied_date, count in time_rows
    ]

    count_by_status = {
        row.status: row.count for row in applications_by_status
    }
    interview_count = count_by_status[JobStatus.INTERVIEW]
    offer_count = count_by_status[JobStatus.OFFER]
    rejection_count = count_by_status[JobStatus.REJECTED]

    return DashboardStatsResponse(
        total_applications=total_applications,
        applications_by_status=applications_by_status,
        applications_by_employment_type=applications_by_employment_type,
        applications_by_location=applications_by_location,
        applications_over_time=applications_over_time,
        interview_count=interview_count,
        offer_count=offer_count,
        rejection_count=rejection_count,
        interview_conversion_rate=(
            round(interview_count / total_applications * 100, 2)
            if total_applications
            else 0.0
        ),
        offer_conversion_rate=(
            round(offer_count / total_applications * 100, 2)
            if total_applications
            else 0.0
        ),
    )
