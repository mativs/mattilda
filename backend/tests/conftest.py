import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from app.application.services.security_service import hash_password
from app.domain.roles import UserRole
from app.infrastructure.db.models import DummyRecord, School, User, UserProfile, UserSchoolRole
from app.infrastructure.db.session import get_db
from app.main import app


class FakeRedisClient:
    def ping(self) -> bool:
        return True


@pytest.fixture
def postgres_url():
    with PostgresContainer("postgres:16-alpine") as postgres:
        url = postgres.get_connection_url().replace("postgresql://", "postgresql+psycopg2://", 1)
        yield url


def run_migrations(database_url: str) -> None:
    from app.config import settings

    os.environ["DATABASE_URL"] = database_url
    settings.database_url = database_url
    alembic_config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    command.upgrade(alembic_config, "head")


@pytest.fixture
def db_session(monkeypatch, postgres_url):
    engine = create_engine(postgres_url, future=True)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    run_migrations(database_url=postgres_url)

    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()
    monkeypatch.setattr("app.interfaces.api.v1.routes.ping.get_redis_client", lambda: FakeRedisClient())
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


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
        is_active=True,
    )
    admin.profile = UserProfile(first_name="Admin", last_name="One", phone="111", address="Admin Street")

    student = User(
        email="student@example.com",
        hashed_password=hash_password("student123"),
        is_active=True,
    )
    student.profile = UserProfile(first_name="Student", last_name="One", phone="222", address="Student Street")

    teacher = User(
        email="teacher@example.com",
        hashed_password=hash_password("teacher123"),
        is_active=True,
    )
    teacher.profile = UserProfile(first_name="Teacher", last_name="One", phone="333", address="Teacher Street")

    north_school = School(name="North High", slug="north-high")
    south_school = School(name="South High", slug="south-high")

    db_session.add_all([admin, student, teacher, north_school, south_school])
    db_session.commit()
    db_session.refresh(admin)
    db_session.refresh(student)
    db_session.refresh(teacher)
    db_session.refresh(north_school)
    db_session.refresh(south_school)

    db_session.add_all(
        [
            UserSchoolRole(user_id=admin.id, school_id=north_school.id, role=UserRole.director.value),
            UserSchoolRole(user_id=admin.id, school_id=south_school.id, role=UserRole.director.value),
            UserSchoolRole(user_id=teacher.id, school_id=north_school.id, role=UserRole.teacher.value),
            UserSchoolRole(user_id=student.id, school_id=north_school.id, role=UserRole.student.value),
        ]
    )
    db_session.add_all(
        [
            DummyRecord(name="north-record", school_id=north_school.id),
            DummyRecord(name="south-record", school_id=south_school.id),
        ]
    )
    db_session.commit()

    return {
        "admin": admin,
        "student": student,
        "teacher": teacher,
        "north_school": north_school,
        "south_school": south_school,
    }
