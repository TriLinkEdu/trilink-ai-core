import pytest
from unittest.mock import MagicMock
from services.mastery_service import MasteryService
from plugins.tracers.bkt_tracer import BKTTracer
from core.models.mastery import TopicMastery

PARAMS = {"p_init": 0.1, "p_learn": 0.3, "p_slip": 0.1, "p_guess": 0.25}
STUDENT = "student-uuid-1"
TOPIC   = "topic-uuid-1"
SUBJECT = "subject-uuid-1"


@pytest.fixture
def tracer():
    return BKTTracer(PARAMS)


@pytest.fixture
def repo():
    mock = MagicMock()
    mock.get_mastery.return_value = TopicMastery(
        student_id=STUDENT, topic_id=TOPIC,
        mastery_level=0.5, assessment_count=5
    )
    return mock


@pytest.fixture
def svc(tracer, repo):
    return MasteryService(tracer=tracer, repo=repo)


class TestMasteryService:

    @pytest.mark.asyncio
    async def test_correct_answer_increases_mastery(self, svc, repo):
        result = await svc.process_answer(STUDENT, TOPIC, is_correct=True)
        assert result["new_mastery"] > result["old_mastery"]
        assert result["old_mastery"] == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_incorrect_answer_decreases_mastery(self, svc, repo):
        result = await svc.process_answer(STUDENT, TOPIC, is_correct=False)
        assert result["new_mastery"] < result["old_mastery"]

    @pytest.mark.asyncio
    async def test_mastered_flag_set_when_above_threshold(self, svc, repo):
        # Force mastery above threshold
        repo.get_mastery.return_value = TopicMastery(
            student_id=STUDENT, topic_id=TOPIC,
            mastery_level=0.85, assessment_count=10
        )
        result = await svc.process_answer(STUDENT, TOPIC, is_correct=True)
        assert result["mastered"] is True

    @pytest.mark.asyncio
    async def test_mastered_flag_false_when_below_threshold(self, svc, repo):
        repo.get_mastery.return_value = TopicMastery(
            student_id=STUDENT, topic_id=TOPIC,
            mastery_level=0.3, assessment_count=2
        )
        result = await svc.process_answer(STUDENT, TOPIC, is_correct=False)
        assert result["mastered"] is False

    @pytest.mark.asyncio
    async def test_save_mastery_called_with_new_value(self, svc, repo):
        result = await svc.process_answer(STUDENT, TOPIC, is_correct=True)
        repo.save_mastery.assert_called_once_with(STUDENT, TOPIC, result["new_mastery"])

    @pytest.mark.asyncio
    async def test_assessment_count_incremented(self, svc, repo):
        result = await svc.process_answer(STUDENT, TOPIC, is_correct=True)
        assert result["assessment_count"] == 6  # was 5

    @pytest.mark.asyncio
    async def test_get_weak_topics_filters_below_threshold(self, svc, repo):
        repo.get_all_masteries.return_value = [
            TopicMastery(STUDENT, "t1", 0.4, 3),
            TopicMastery(STUDENT, "t2", 0.8, 5),  # above threshold
            TopicMastery(STUDENT, "t3", 0.2, 1),
        ]
        result = await svc.get_weak_topics(STUDENT, SUBJECT)
        ids = [t["topic_id"] for t in result]
        assert "t1" in ids
        assert "t3" in ids
        assert "t2" not in ids

    @pytest.mark.asyncio
    async def test_get_weak_topics_sorted_by_mastery(self, svc, repo):
        repo.get_all_masteries.return_value = [
            TopicMastery(STUDENT, "t1", 0.5, 3),
            TopicMastery(STUDENT, "t2", 0.2, 1),
            TopicMastery(STUDENT, "t3", 0.4, 2),
        ]
        result = await svc.get_weak_topics(STUDENT, SUBJECT)
        levels = [t["mastery_level"] for t in result]
        assert levels == sorted(levels)  # lowest mastery first
