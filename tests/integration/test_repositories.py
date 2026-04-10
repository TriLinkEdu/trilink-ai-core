"""
Integration tests for repositories.
Requires a running PostgreSQL with the schema applied.
Set TEST_POSTGRES_URL env var or these tests are skipped.
"""
import os
import uuid
import pytest
from infrastructure.db.postgres import init_pool
from infrastructure.repositories.student_repo import StudentRepository
from infrastructure.repositories.topic_repo import TopicRepository

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL", "")


@pytest.fixture(scope="module", autouse=True)
def db():
    if not POSTGRES_URL:
        pytest.skip("TEST_POSTGRES_URL not set — skipping DB integration tests")
    init_pool(POSTGRES_URL)


@pytest.fixture
def student_repo():
    return StudentRepository()


@pytest.fixture
def topic_repo():
    return TopicRepository()


class TestStudentRepository:

    def test_cold_start_returns_prior(self, student_repo):
        mastery = student_repo.get_mastery(str(uuid.uuid4()), str(uuid.uuid4()))
        assert mastery.mastery_level == pytest.approx(0.1)
        assert mastery.assessment_count == 0

    def test_save_and_retrieve_mastery(self, student_repo, topic_repo):
        # Requires seeded student + topic in DB — skip if not available
        pytest.skip("Requires seeded data — run after seed script")
