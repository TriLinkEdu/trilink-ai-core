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
    question_repo = MagicMock()
    question_repo.save_batch.return_value = ["q-id-1"]
    return ContentService(generator, resource_repo, topic_repo, question_repo)


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
        assert "saved" in result

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


class TestStructuredOutputParsing:
    """
    Test the Pydantic-based question validation that replaced regex parsing.

    All generators now use MCQQuestionList.model_validate() for guaranteed
    schema enforcement. These tests verify that schema is correctly applied.
    """

    def test_valid_question_list_parses(self):
        from core.models.question_schema import MCQQuestionList
        data = {
            "questions": [
                {
                    "question": "What is velocity?",
                    "options": [
                        {"label": "A", "text": "speed"},
                        {"label": "B", "text": "displacement/time"},
                        {"label": "C", "text": "force"},
                        {"label": "D", "text": "mass"},
                    ],
                    "answer": "B",
                    "explanation": "Velocity = displacement / time",
                    "difficulty": "easy",
                }
            ]
        }
        result = MCQQuestionList.model_validate(data)
        assert len(result.questions) == 1
        assert result.questions[0].answer == "B"

    def test_to_dict_produces_legacy_format(self):
        from core.models.question_schema import MCQQuestionList
        data = {
            "questions": [
                {
                    "question": "What is osmosis?",
                    "options": [
                        {"label": "A", "text": "movement of water"},
                        {"label": "B", "text": "movement of ions"},
                        {"label": "C", "text": "cell division"},
                        {"label": "D", "text": "photosynthesis"},
                    ],
                    "answer": "A",
                    "explanation": "Osmosis is the diffusion of water.",
                    "difficulty": "medium",
                }
            ]
        }
        q = MCQQuestionList.model_validate(data).questions[0]
        d = q.to_dict()
        assert d["answer"] == "A"
        assert len(d["options"]) == 4
        assert d["options"][0].startswith("A)")

    def test_invalid_answer_label_raises(self):
        from core.models.question_schema import MCQQuestionList
        from pydantic import ValidationError
        data = {
            "questions": [
                {
                    "question": "Q?",
                    "options": [
                        {"label": "A", "text": "o1"},
                        {"label": "B", "text": "o2"},
                        {"label": "C", "text": "o3"},
                        {"label": "D", "text": "o4"},
                    ],
                    "answer": "E",
                    "explanation": "exp",
                    "difficulty": "easy",
                }
            ]
        }
        with pytest.raises(ValidationError):
            MCQQuestionList.model_validate(data)

    def test_invalid_difficulty_raises(self):
        from core.models.question_schema import MCQQuestionList
        from pydantic import ValidationError
        data = {
            "questions": [
                {
                    "question": "Q?",
                    "options": [
                        {"label": "A", "text": "o1"},
                        {"label": "B", "text": "o2"},
                        {"label": "C", "text": "o3"},
                        {"label": "D", "text": "o4"},
                    ],
                    "answer": "A",
                    "explanation": "exp",
                    "difficulty": "very_hard",
                }
            ]
        }
        with pytest.raises(ValidationError):
            MCQQuestionList.model_validate(data)
