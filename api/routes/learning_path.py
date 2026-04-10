from fastapi import APIRouter, Request
from api.schemas.learning_path import LearningPathRequest, LearningPathResponse
from services.learning_path_service import LearningPathService
from infrastructure.repositories.student_repo import StudentRepository
from infrastructure.repositories.topic_repo import TopicRepository

router = APIRouter(prefix="/learning-path", tags=["learning-path"])


def _svc(request: Request) -> LearningPathService:
    return LearningPathService(
        student_repo=StudentRepository(),
        topic_repo=TopicRepository(),
    )


@router.post("", response_model=LearningPathResponse)
async def generate_learning_path(body: LearningPathRequest, request: Request):
    path = await _svc(request).generate(body.student_id, body.subject_id)
    return LearningPathResponse(
        student_id      =path.student_id,
        subject_id      =path.subject_id,
        overall_progress=path.overall_progress,
        topics=[
            {
                "topic_id"       : t.topic_id,
                "topic_name"     : t.topic_name,
                "current_mastery": t.current_mastery,
                "target_mastery" : t.target_mastery,
                "sequence_order" : t.sequence_order,
                "is_completed"   : t.is_completed,
                "explanation"    : t.explanation,
            }
            for t in path.topics
        ],
    )
