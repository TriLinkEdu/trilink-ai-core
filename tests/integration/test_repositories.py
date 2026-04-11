"""
Integration tests — require live PostgreSQL.
Set TEST_POSTGRES_URL env var to run, otherwise skipped.
"""
import os
import uuid
import pytest
import psycopg2
from infrastructure.db.postgres import init_pool
from infrastructure.repositories.student_repo import StudentRepository
from infrastructure.repositories.topic_repo import TopicRepository
from infrastructure.repositories.resource_repo import ResourceRepository
from core.models.resource import Resource

POSTGRES_URL = os.getenv("TEST_POSTGRES_URL", "")


@pytest.fixture(scope="module")
def db():
    if not POSTGRES_URL:
        pytest.skip("TEST_POSTGRES_URL not set")
    init_pool(POSTGRES_URL)


@pytest.fixture(scope="module")
def seeded_ids(db):
    """Insert minimal test data, return ids, clean up after module."""
    conn = psycopg2.connect(POSTGRES_URL)
    conn.autocommit = True
    cur = conn.cursor()

    subj_id = str(uuid.uuid4())
    topic_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    cur.execute(
        "INSERT INTO subject(subject_id,subject_name,subject_code,grade_level) VALUES(%s,'TestSubject','TST9',9)",
        (subj_id,),
    )
    cur.execute(
        """INSERT INTO topic(topic_id,subject_id,topic_name,topic_code,difficulty_tier,objectives,keywords)
           VALUES(%s,%s,'TestTopic','TST9.1.1','easy',ARRAY['obj1'],ARRAY['kw1'])""",
        (topic_id, subj_id),
    )
    cur.execute(
        """INSERT INTO "user"(user_id,email,password_hash,role,first_name,last_name)
           VALUES(%s,'integration@test.com','hash','student','Test','User')""",
        (user_id,),
    )
    cur.execute(
        "INSERT INTO student_profile(student_id,grade_level,section) VALUES(%s,9,'A')",
        (user_id,),
    )
    conn.close()

    yield {"subject_id": subj_id, "topic_id": topic_id, "student_id": user_id}

    # Cleanup
    conn = psycopg2.connect(POSTGRES_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute('DELETE FROM "user" WHERE user_id=%s', (user_id,))
    cur.execute("DELETE FROM subject WHERE subject_id=%s", (subj_id,))
    conn.close()


class TestStudentRepository:

    def test_cold_start_returns_prior(self, db):
        repo = StudentRepository()
        m = repo.get_mastery(str(uuid.uuid4()), str(uuid.uuid4()))
        assert m.mastery_level == pytest.approx(0.1)
        assert m.assessment_count == 0

    def test_save_and_retrieve_mastery(self, seeded_ids):
        repo = StudentRepository()
        sid, tid = seeded_ids["student_id"], seeded_ids["topic_id"]

        repo.save_mastery(sid, tid, 0.72)
        m = repo.get_mastery(sid, tid)
        assert m.mastery_level == pytest.approx(0.72, abs=1e-4)
        assert m.assessment_count == 1

    def test_upsert_increments_count(self, seeded_ids):
        repo = StudentRepository()
        sid, tid = seeded_ids["student_id"], seeded_ids["topic_id"]

        repo.save_mastery(sid, tid, 0.80)
        m = repo.get_mastery(sid, tid)
        assert m.assessment_count == 2

    def test_get_all_masteries(self, seeded_ids):
        repo = StudentRepository()
        masteries = repo.get_all_masteries(
            seeded_ids["student_id"], seeded_ids["subject_id"]
        )
        assert len(masteries) >= 1
        assert any(m.topic_id == seeded_ids["topic_id"] for m in masteries)


class TestTopicRepository:

    def test_get_by_id(self, seeded_ids):
        repo = TopicRepository()
        t = repo.get_by_id(seeded_ids["topic_id"])
        assert t.name == "TestTopic"
        assert t.grade_level == 9

    def test_get_by_subject(self, seeded_ids):
        repo = TopicRepository()
        topics = repo.get_by_subject(seeded_ids["subject_id"])
        assert any(t.id == seeded_ids["topic_id"] for t in topics)


class TestResourceRepository:

    def test_save_and_embed(self, seeded_ids):
        repo = ResourceRepository()
        res = Resource(
            id="", title="Test Lesson", type="lesson",
            topic_id=seeded_ids["topic_id"], difficulty="easy",
            content="# Test", source="manual",
        )
        new_id = repo.save(res)
        assert new_id

        # Save embedding
        vector = [0.1] * 384
        repo.save_embedding(new_id, vector)  # should not raise
