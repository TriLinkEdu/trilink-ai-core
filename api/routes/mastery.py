from fastapi import APIRouter, Request
from api.schemas.mastery import (
    MasteryUpdateRequest,
    MasteryUpdateResponse,
    MasteryGetResponse,
    WeakTopicsResponse,
)
from services.mastery_service import MasteryService
from infrastructure.repositories.student_repo import StudentRepository

router = APIRouter(prefix="/mastery", tags=["mastery"])


def _svc(request: Request) -> MasteryService:
    registry = request.app.state.registry
    return MasteryService(
        tracer=registry.tracer,
        repo=StudentRepository(),
    )


@router.post("/update", response_model=MasteryUpdateResponse)
async def update_mastery(body: MasteryUpdateRequest, request: Request):
    return await _svc(request).process_answer(
        body.student_id, body.topic_id, body.is_correct
    )


@router.get("/{student_id}/{topic_id}", response_model=MasteryGetResponse)
async def get_mastery(student_id: str, topic_id: str, request: Request):
    return await _svc(request).get_mastery(student_id, topic_id)


@router.get("/{student_id}/weak/{subject_id}", response_model=WeakTopicsResponse)
async def get_weak_topics(student_id: str, subject_id: str, request: Request):
    weak = await _svc(request).get_weak_topics(student_id, subject_id)
    return WeakTopicsResponse(
        student_id=student_id,
        subject_id=subject_id,
        weak_topics=weak,
    )
