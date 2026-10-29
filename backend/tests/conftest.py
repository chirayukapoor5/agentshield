from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.db.session import Base, get_db
from app.main import app
from app.models.models import Organization, User


@pytest.fixture
def test_session_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'agentshield-test.db'}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.fixture
def client(test_session_factory) -> Iterator[TestClient]:
    db = test_session_factory()
    organization = Organization(name="Test Org", slug="test-org")
    db.add(organization)
    db.flush()
    db.add(User(
        organization_id=organization.id,
        email="demo@agentshield.local",
        full_name="Demo Admin",
        password_hash=hash_password("password123"),
        is_active=True,
    ))
    db.commit()
    db.close()

    def override_get_db():
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def demo_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "demo@agentshield.local", "password": "password123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
