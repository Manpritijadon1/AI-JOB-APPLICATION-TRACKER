from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_jwt_secret,
    hash_password,
    verify_password,
)
from app.db.dependencies import get_db
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    RegistrationRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
bearer_scheme = HTTPBearer(auto_error=False)
DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    settings: Settings = db.info["settings"]
    user_id = decode_access_token(credentials.credentials, settings)
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user",
)
def register_user(payload: RegistrationRequest, db: DbSession) -> User:
    get_jwt_secret(db.info["settings"])
    user = User(
        name=payload.name,
        email=str(payload.email).lower(),
        hashed_password=hash_password(payload.password.get_secret_value()),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from exc
    db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and receive a bearer token",
)
def login_user(payload: LoginRequest, db: DbSession) -> TokenResponse:
    settings: Settings = db.info["settings"]
    get_jwt_secret(settings)
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user is None or not verify_password(
        payload.password.get_secret_value(),
        user.hashed_password if user is not None else _INVALID_PASSWORD_HASH,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=create_access_token(user.id, settings))


_INVALID_PASSWORD_HASH = hash_password("invalid-password-placeholder")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the authenticated user",
)
def read_current_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user
