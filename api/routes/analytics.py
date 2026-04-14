from fastapi import APIRouter, Request, Query
from services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _svc(request: Request) -> AnalyticsService:
    return AnalyticsService(generator=request.app.state.registry.generator)


# ── Parent endpoints ──────────────────────────────────────────────────────────

@router.get("/student/{student_id}/weekly-summary")
async def weekly_summary(student_id: str, request: Request):
    """Parent: weekly progress summary with AI-generated plain-language report."""
    return await _svc(request).weekly_summary(student_id)


# ── Teacher endpoints ─────────────────────────────────────────────────────────

@router.get("/subject/{subject_id}/at-risk")
async def at_risk_students(
    subject_id: str,
    request: Request,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Teacher: students at risk of falling behind in a subject."""
    return await _svc(request).at_risk_students(subject_id, limit=limit, offset=offset)


@router.get("/subject/{subject_id}/class-performance")
async def class_performance(
    subject_id: str,
    request: Request,
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Teacher: per-topic class performance — which topics need re-teaching."""
    return _svc(request).class_performance(subject_id, limit=limit, offset=offset)