from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session


def get_db(request: Request) -> Generator[Session, None, None]:
    session_factory = request.app.state.db_session_factory
    with session_factory() as session:
        session.info["settings"] = request.app.state.settings
        yield session
