from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_endpoint() -> None:
    application = create_app(
        Settings(_env_file=None, database_url="sqlite://")
    )

    with TestClient(application) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
