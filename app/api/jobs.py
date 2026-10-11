from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import AnyHttpUrl
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.dependencies import get_db
from app.models import JobApplication, JobStatus, User
from app.schemas.jobs import (
    JobApplicationCreate,
    JobApplicationPage,
    JobApplicationResponse,
    JobApplicationUpdate,
)

router = APIRouter(prefix="/jobs", tags=["job applications"])
DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
SortField = Literal["created_at", "applied_date", "company_name", "job_title", "status"]
SortOrder = Literal["asc", "desc"]


def get_owned_job(db: Session, user_id: int, job_id: int) -> JobApplication:
    job = db.scalar(
        select(JobApplication).where(
            JobApplication.id == job_id,
            JobApplication.user_id == user_id,
        )
    )
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job application not found",
        )
    return job


@router.post(
    "",
    response_model=JobApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a job application",
)
def create_job(
    payload: JobApplicationCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> JobApplication:
    values = payload.model_dump()
    if isinstance(values["job_url"], AnyHttpUrl):
        values["job_url"] = str(values["job_url"])
    job = JobApplication(user_id=current_user.id, **values)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.get(
    "",
    response_model=JobApplicationPage,
    summary="List the authenticated user's job applications",
)
def list_jobs(
    db: DbSession,
    current_user: CurrentUser,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[JobStatus | None, Query(alias="status")] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    sort_by: Annotated[SortField, Query()] = "created_at",
    sort_order: Annotated[SortOrder, Query()] = "desc",
) -> JobApplicationPage:
    filters = [JobApplication.user_id == current_user.id]
    if status_filter is not None:
        filters.append(JobApplication.status == status_filter)
    if search is not None:
        normalized_search = search.strip()
        if not normalized_search:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Search must not be blank",
            )
        term = f"%{normalized_search}%"
        filters.append(
            or_(
                JobApplication.company_name.ilike(term),
                JobApplication.job_title.ilike(term),
            )
        )

    total = db.scalar(select(func.count()).select_from(JobApplication).where(*filters)) or 0
    sort_column = getattr(JobApplication, sort_by)
    ordering = sort_column.asc() if sort_order == "asc" else sort_column.desc()
    jobs = db.scalars(
        select(JobApplication)
        .where(*filters)
        .order_by(ordering, JobApplication.id.asc())
        .offset(skip)
        .limit(limit)
    ).all()
    return JobApplicationPage(items=list(jobs), total=total, skip=skip, limit=limit)


@router.get(
    "/{job_id}",
    response_model=JobApplicationResponse,
    summary="Get one of the authenticated user's job applications",
)
def read_job(job_id: int, db: DbSession, current_user: CurrentUser) -> JobApplication:
    return get_owned_job(db, current_user.id, job_id)


@router.patch(
    "/{job_id}",
    response_model=JobApplicationResponse,
    summary="Update one of the authenticated user's job applications",
)
def update_job(
    job_id: int,
    payload: JobApplicationUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> JobApplication:
    job = get_owned_job(db, current_user.id, job_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if isinstance(value, AnyHttpUrl):
            value = str(value)
        setattr(job, field, value)
    db.commit()
    db.refresh(job)
    return job


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one of the authenticated user's job applications",
)
def delete_job(job_id: int, db: DbSession, current_user: CurrentUser) -> Response:
    job = get_owned_job(db, current_user.id, job_id)
    db.delete(job)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
