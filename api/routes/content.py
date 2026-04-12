from fastapi import APIRouter, Request, Query
from api.schemas.content import (
    GenerateLessonRequest, GenerateLessonResponse,
    GenerateQuestionsRequest, GenerateQuestionsResponse,
)
from services.content_service import ContentService
from infrastructure.repositories.resource_repo import ResourceRepository
from infrastructure.repositories.topic_repo import TopicRepository
from infrastructure.repositories.question_repo import QuestionRepository

router = APIRouter(prefix="/content", tags=["content"])


def _svc(request: Request) -> ContentService:
    r = request.app.state.registry
    return ContentService(
        generator    =r.generator,
        resource_repo=ResourceRepository(),
        topic_repo   =TopicRepository(),
    )


@router.post("/generate-lesson", response_model=GenerateLessonResponse)
async def generate_lesson(body: GenerateLessonRequest, request: Request):
    return await _svc(request).generate_lesson(body.topic_id)


@router.post("/generate-questions", response_model=GenerateQuestionsResponse)
async def generate_questions(body: GenerateQuestionsRequest, request: Request):
    return await _svc(request).generate_questions(body.topic_id, body.count)


@router.get("/questions/{topic_id}")
async def get_questions(
    topic_id: str,
    difficulty: str | None = Query(default=None),
    limit: int = Query(default=10, le=50),
):
    """Fetch persisted questions for a topic — used by NestJS to build quizzes."""
    repo = QuestionRepository()
    questions = repo.get_by_topic(topic_id, difficulty=difficulty, limit=limit)
    return {
        "topic_id": topic_id,
        "count": len(questions),
        "questions": questions,
    }


@router.get("/next-question/{student_id}/{topic_id}")
async def next_question(student_id: str, topic_id: str, request: Request):
    """
    Adaptive question selection using BKT mastery.
    Returns one question at the appropriate difficulty for this student.
    NestJS calls this during an adaptive quiz session.
    """
    from infrastructure.repositories.student_repo import StudentRepository
    import random

    student_repo = StudentRepository()
    mastery = student_repo.get_mastery(student_id, topic_id)

    # Map mastery to difficulty
    if mastery.mastery_level < 0.4:
        difficulty = "easy"
    elif mastery.mastery_level < 0.7:
        difficulty = "medium"
    else:
        difficulty = "hard"

    repo = QuestionRepository()
    questions = repo.get_by_topic(topic_id, difficulty=difficulty, limit=10)

    # Fallback to any difficulty if none found at target level
    if not questions:
        questions = repo.get_by_topic(topic_id, limit=10)

    if not questions:
        return {"topic_id": topic_id, "question": None, "difficulty": difficulty}

    question = random.choice(questions)
    return {
        "topic_id": topic_id,
        "current_mastery": mastery.mastery_level,
        "selected_difficulty": difficulty,
        "question": question,
    }
