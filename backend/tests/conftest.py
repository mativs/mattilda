import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.application.services.security_service import hash_password
from app.domain.roles import UserRole
from app.infrastructure.db.models import Base, User, UserProfile
from app.infrastructure.db.session import get_db
from app.main import app


class FakeRedisClient:
    def ping(self) -> bool:
        return True


@pytest.fixture
def db_session(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    monkeypatch.setattr("app.interfaces.api.v1.routes.ping.get_redis_client", lambda: FakeRedisClient())
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def seeded_users(db_session):
    admin = User(
        email="admin@example.com",
        hashed_password=hash_password("admin123"),
        roles=[UserRole.admin.value],
        is_active=True,
    )
    admin.profile = UserProfile(first_name="Admin", last_name="One", phone="111", address="Admin Street")

    student = User(
        email="student@example.com",
        hashed_password=hash_password("student123"),
        roles=[UserRole.student.value],
        is_active=True,
    )
    student.profile = UserProfile(first_name="Student", last_name="One", phone="222", address="Student Street")

    db_session.add_all([admin, student])
    db_session.commit()
    db_session.refresh(admin)
    db_session.refresh(student)

    return {"admin": admin, "student": student}
