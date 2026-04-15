from fastapi import APIRouter, Request
from api.schemas.recommendation import RecommendRequest, RecommendResponse
from services.recommendation_service import RecommendationService
from infrastructure.repositories.resource_repo import ResourceRepository
from infrastructure.repositories.topic_repo import TopicRepository

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _svc(request: Request) -> RecommendationService:
    r = request.app.state.registry
    from config.settings import Settings
    return RecommendationService(
        recommender=r.recommender,
        generator=r.generator,
        resource_repo=ResourceRepository(),
        topic_repo=TopicRepository(),
        youtube_api_key=Settings().YOUTUBE_API_KEY,
    )


@router.post("", response_model=RecommendResponse)
async def recommend_resources(body: RecommendRequest, request: Request):
    resources = await _svc(request).recommend(
        body.student_id, body.weak_topic_ids, body.difficulty, body.limit
    )
    return RecommendResponse(student_id=body.student_id, resources=resources)
