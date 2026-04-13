from fastapi import APIRouter, Request
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
async def at_risk_students(subject_id: str, request: Request):
    """Teacher: students at risk of falling behind in a subject."""
    return await _svc(request).at_risk_students(subject_id)


@router.get("/subject/{subject_id}/class-performance")
def class_performance(subject_id: str, request: Request):
    """Teacher: per-topic class performance — which topics need re-teaching."""
    return _svc(request).class_performance(subject_id)
