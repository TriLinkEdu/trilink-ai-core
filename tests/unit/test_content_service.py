import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.content_service import ContentService
from core.models.topic import Topic
from core.exceptions import ContentGenerationError

TOPIC_ID = "topic-physics-1"

TOPIC = Topic(
    id=TOPIC_ID, name="Kinematics", subject="Physics",
    subject_id="subj-1", difficulty_tier="medium",
    objectives=["Define displacement", "Calculate velocity"],
)

SAMPLE_QUESTIONS = [
    {
        "question": "What is velocity?",
        "options": ["A) speed", "B) displacement/time", "C) force", "D) mass"],
        "answer": "B",
        "explanation": "Velocity = displacement / time",
        "difficulty": "easy",
    }
]


@pytest.fixture
def generator():
    mock = MagicMock()
    mock.generate_lesson     = AsyncMock(return_value="# Kinematics\n\nContent here.")
    mock.generate_questions  = AsyncMock(return_value=SAMPLE_QUESTIONS)
    return mock


@pytest.fixture
def resource_repo():
    mock = MagicMock()
    mock.save.return_value = "new-resource-uuid"
    return mock


@pytest.fixture
def topic_repo():
    mock = MagicMock()
    mock.get_by_id.return_value = TOPIC
    return mock


@pytest.fixture
def svc(generator, resource_repo, topic_repo):
    return ContentService(generator, resource_repo, topic_repo)


class TestContentService:

    @pytest.mark.asyncio
    async def test_generate_lesson_returns_dict(self, svc):
        result = await svc.generate_lesson(TOPIC_ID)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_generate_lesson_has_required_keys(self, svc):
        result = await svc.generate_lesson(TOPIC_ID)
        assert {"resource_id", "title", "content", "needs_review", "source"}.issubset(result)

    @pytest.mark.asyncio
    async def test_generate_lesson_always_needs_review(self, svc):
        result = await svc.generate_lesson(TOPIC_ID)
        assert result["needs_review"] is True

    @pytest.mark.asyncio
    async def test_generate_lesson_source_is_ai(self, svc):
        result = await svc.generate_lesson(TOPIC_ID)
        assert result["source"] == "ai_generated"

    @pytest.mark.asyncio
    async def test_generate_lesson_saves_to_repo(self, svc, resource_repo):
        await svc.generate_lesson(TOPIC_ID)
        resource_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_lesson_title_contains_topic_name(self, svc):
        result = await svc.generate_lesson(TOPIC_ID)
        assert "Kinematics" in result["title"]

    @pytest.mark.asyncio
    async def test_generate_questions_returns_list(self, svc):
        result = await svc.generate_questions(TOPIC_ID, count=1)
        assert isinstance(result["questions"], list)

    @pytest.mark.asyncio
    async def test_generate_questions_passes_count(self, svc, generator):
        await svc.generate_questions(TOPIC_ID, count=10)
        generator.generate_questions.assert_called_once_with(TOPIC, 10)

    @pytest.mark.asyncio
    async def test_content_generation_error_propagates(self, svc, generator):
        generator.generate_lesson = AsyncMock(
            side_effect=ContentGenerationError(TOPIC_ID, "API down")
        )
        with pytest.raises(ContentGenerationError):
            await svc.generate_lesson(TOPIC_ID)


class TestGroqGeneratorParsing:
    """Test JSON parsing logic without hitting the API."""

    def test_parse_valid_json(self):
        from plugins.generators.groq_generator import GroqGenerator
        raw = '[{"question":"Q?","options":["A","B"],"answer":"A","explanation":"E","difficulty":"easy"}]'
        result = GroqGenerator._parse_json(raw, "t1")
        assert len(result) == 1
        assert result[0]["answer"] == "A"

    def test_parse_json_embedded_in_text(self):
        from plugins.generators.groq_generator import GroqGenerator
        raw = 'Here are the questions:\n[{"question":"Q?","options":[],"answer":"A","explanation":"E","difficulty":"easy"}]\nDone.'
        result = GroqGenerator._parse_json(raw, "t1")
        assert len(result) == 1

    def test_parse_invalid_json_raises(self):
        from plugins.generators.groq_generator import GroqGenerator
        with pytest.raises(ContentGenerationError):
            GroqGenerator._parse_json("no json here", "t1")
