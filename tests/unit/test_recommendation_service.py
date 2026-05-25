import pytest
from unittest.mock import AsyncMock, MagicMock
from services.recommendation_service import RecommendationService
from core.models.resource import Resource
from core.models.topic import Topic

STUDENT  = "student-1"
TOPIC_ID = "topic-1"


def _resource(rid: str, score: float = 0.9) -> Resource:
    return Resource(
        id=rid, title=f"Resource {rid}", type="lesson",
        topic_id=TOPIC_ID, difficulty="medium",
        relevance_score=score, source="manual",
    )


@pytest.fixture
def recommender():
    mock = MagicMock()
    mock.recommend = AsyncMock(return_value=[_resource("r1"), _resource("r2"), _resource("r3")])
    return mock


@pytest.fixture
def generator():
    mock = MagicMock()
    mock.generate_lesson = AsyncMock(return_value="# Lesson content")
    return mock


@pytest.fixture
def resource_repo():
    mock = MagicMock()
    mock.save.return_value = "new-resource-id"
    return mock


@pytest.fixture
def topic_repo():
    mock = MagicMock()
    mock.get_by_id.return_value = Topic(
        id=TOPIC_ID, name="Kinematics", subject="Physics",
        subject_id="subj-1", difficulty_tier="medium",
    )
    return mock


@pytest.fixture
def svc(recommender, generator, resource_repo, topic_repo):
    return RecommendationService(recommender, generator, resource_repo, topic_repo)


class TestRecommendationService:

    @pytest.mark.asyncio
    async def test_returns_resources_as_dicts(self, svc):
        result = await svc.recommend(STUDENT, [TOPIC_ID])
        assert isinstance(result, list)
        assert all(isinstance(r, dict) for r in result)

    @pytest.mark.asyncio
    async def test_resource_dict_has_required_keys(self, svc):
        result = await svc.recommend(STUDENT, [TOPIC_ID])
        required = {"resource_id", "title", "type", "relevance_score", "source"}
        assert required.issubset(result[0].keys())

    @pytest.mark.asyncio
    async def test_no_generation_when_enough_resources(self, svc, generator):
        await svc.recommend(STUDENT, [TOPIC_ID])
        generator.generate_lesson.assert_not_called()

    @pytest.mark.asyncio
    async def test_generates_lesson_when_too_few_resources(
        self, recommender, generator, resource_repo, topic_repo
    ):
        recommender.recommend = AsyncMock(return_value=[_resource("r1")])
        svc = RecommendationService(recommender, generator, resource_repo, topic_repo)
        result = await svc.recommend(STUDENT, [TOPIC_ID])
        generator.generate_lesson.assert_called_once()
        assert any(r["source"] == "ai_generated" for r in result)

    @pytest.mark.asyncio
    async def test_generation_failure_is_non_fatal(
        self, recommender, generator, resource_repo, topic_repo
    ):
        recommender.recommend = AsyncMock(return_value=[])
        generator.generate_lesson = AsyncMock(side_effect=Exception("API down"))
        svc = RecommendationService(recommender, generator, resource_repo, topic_repo)
        result = await svc.recommend(STUDENT, [TOPIC_ID])
        assert isinstance(result, list)  # no crash

    @pytest.mark.asyncio
    async def test_empty_topic_ids_returns_intro_lesson(self, svc, generator):
        """Zero-interaction student: must always get a generated lesson, never empty."""
        result = await svc.recommend(STUDENT, [], subject_name="Physics", grade_level=9)
        generator.generate_lesson.assert_called_once()
        assert len(result) == 1
        assert result[0]["source"] == "ai_generated"
        assert result[0]["type"] == "lesson"

    @pytest.mark.asyncio
    async def test_empty_topic_ids_groq_failure_still_non_fatal(self, recommender, resource_repo, topic_repo):
        """If Groq is down, fallback returns [] gracefully instead of crashing."""
        bad_generator = MagicMock()
        bad_generator.generate_lesson = AsyncMock(side_effect=Exception("Groq down"))
        svc = RecommendationService(recommender, bad_generator, resource_repo, topic_repo)
        result = await svc.recommend(STUDENT, [], subject_name="Physics", grade_level=9)
        assert isinstance(result, list)  # no crash

    @pytest.mark.asyncio
    async def test_empty_topic_ids_uses_subject_name_in_title(self, svc):
        """Returned lesson title should mention the subject name."""
        result = await svc.recommend(STUDENT, [], subject_name="Mathematics", grade_level=10)
        assert "Mathematics" in result[0]["title"]
