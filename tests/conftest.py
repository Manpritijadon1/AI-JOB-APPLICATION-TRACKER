from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

TEST_JWT_SECRET = "test-only-secret-key-not-for-production-123456"


@pytest.fixture
def client(tmp_path: Path):
    database_path = tmp_path / "test.db"
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{database_path.as_posix()}",
        jwt_secret_key=TEST_JWT_SECRET,
    )
    application = create_app(settings)
    with TestClient(application) as test_client:
        yield test_client
    application.state.db_engine.dispose()
