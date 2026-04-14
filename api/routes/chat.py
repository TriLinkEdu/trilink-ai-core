from fastapi import APIRouter, Request, Query, HTTPException
from api.schemas.chat import ChatRequest, ChatResponse
from services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


def _svc(request: Request) -> ChatService:
    r = request.app.state.registry
    return ChatService(generator=r.generator, embedder=r.embedder)


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request):
    try:
        return await _svc(request).chat(body.student_id, body.message, body.grade_level)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/history/{student_id}")
async def chat_history(student_id: str, limit: int = Query(default=20, le=50)):
    from infrastructure.repositories.mongo_repos import ChatLogRepository
    return {
        "student_id": student_id,
        "history": ChatLogRepository().get_history(student_id, limit=limit),
    }
