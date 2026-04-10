from fastapi import APIRouter, Request
from api.schemas.content import (
    GenerateLessonRequest, GenerateLessonResponse,
    GenerateQuestionsRequest, GenerateQuestionsResponse,
)
from services.content_service import ContentService
from infrastructure.repositories.resource_repo import ResourceRepository
from infrastructure.repositories.topic_repo import TopicRepository

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
