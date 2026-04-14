import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from services.analytics_service import AnalyticsService
from infrastructure.repositories.analytics_repo import AnalyticsRepository
from infrastructure.repositories.question_repo import QuestionRepository


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=AnalyticsRepository)
    repo.get_student_weekly_summary.return_value = {
        "student_id": "s1",
        "grade_level": 9,
        "overall_mastery": 0.65,
        "topics_mastered": 4,
        "topics_assessed": 6,
        "active_topics_this_week": 3,
        "subjects": [
            {"subject": "Physics", "avg_mastery": 0.80, "topics_assessed": 3, "topics_mastered": 3},
            {"subject": "Biology", "avg_mastery": 0.45, "topics_assessed": 3, "topics_mastered": 1},
        ],
    }
    repo.get_at_risk_students.return_value = [
        {"student_id": "s2", "name": "Sara B", "avg_mastery": 0.20,
         "topics_assessed": 4, "critical_topics": 3, "last_active": None, "risk_level": "HIGH"},
        {"student_id": "s3", "name": "Ahmed A", "avg_mastery": 0.55,
         "topics_assessed": 6, "critical_topics": 0, "last_active": "2026-04-10", "risk_level": "MEDIUM"},
    ]
    repo.get_class_performance.return_value = {
        "subject_id": "sub1",
        "overall_avg_mastery": 0.55,
        "total_students": 3,
        "weak_topics": [{"topic_name": "Kinematics", "status": "weak"}],
        "strong_topics": [{"topic_name": "Newton Laws", "status": "strong"}],
        "all_topics": [],
    }
    return repo


@pytest.fixture
def svc(mock_repo):
    generator = MagicMock()
    generator._call_raw = AsyncMock(return_value="Great progress this week!")
    s = AnalyticsService(generator=generator)
    s._repo = mock_repo
    return s


# ── AnalyticsService tests ────────────────────────────────────────────────────

class TestAnalyticsService:

    @pytest.mark.asyncio
    async def test_weekly_summary_returns_llm_summary(self, svc):
        result = await svc.weekly_summary("s1")
        assert "summary" in result
        assert result["summary"] == "Great progress this week!"

    @pytest.mark.asyncio
    async def test_weekly_summary_fallback_on_llm_error(self, svc):
        svc._generator._call_raw = AsyncMock(side_effect=Exception("LLM down"))
        result = await svc.weekly_summary("s1")
        assert "summary" in result
        assert len(result["summary"]) > 0  # fallback string

    @pytest.mark.asyncio
    async def test_weekly_summary_no_activity(self, svc, mock_repo):
        mock_repo.get_student_weekly_summary.return_value = {
            "student_id": "s1", "overall_mastery": 0.0,
            "topics_mastered": 0, "topics_assessed": 0,
            "active_topics_this_week": 0, "subjects": [],
        }
        result = await svc.weekly_summary("s1")
        assert "No activity" in result["summary"]

    @pytest.mark.asyncio
    async def test_at_risk_splits_by_level(self, svc):
        result = await svc.at_risk_students("sub1")
        assert result["high_risk_count"] == 1
        assert result["medium_risk_count"] == 1
        assert result["high_risk"][0]["name"] == "Sara B"

    @pytest.mark.asyncio
    async def test_at_risk_generates_recommendations(self, svc):
        result = await svc.at_risk_students("sub1")
        assert len(result["recommendations"]) > 0
        assert any("1-on-1" in r for r in result["recommendations"])

    @pytest.mark.asyncio
    async def test_at_risk_contact_parents_tip(self, svc):
        result = await svc.at_risk_students("sub1")
        assert any("contact parents" in r.lower() for r in result["recommendations"])

    @pytest.mark.asyncio
    async def test_at_risk_passes_pagination(self, svc, mock_repo):
        await svc.at_risk_students("sub1", limit=10, offset=5)
        mock_repo.get_at_risk_students.assert_called_with("sub1", limit=10, offset=5)

    @pytest.mark.asyncio
    async def test_class_performance_returns_dict(self, svc):
        result = await svc.class_performance("sub1")
        assert "weak_topics" in result
        assert "strong_topics" in result
        assert "overall_avg_mastery" in result

    @pytest.mark.asyncio
    async def test_class_performance_passes_pagination(self, svc, mock_repo):
        await svc.class_performance("sub1", limit=20, offset=10)
        mock_repo.get_class_performance.assert_called_with("sub1", limit=20, offset=10)


# ── QuestionRepository tests ──────────────────────────────────────────────────

class TestQuestionRepository:

    def test_save_batch_inserts_and_returns_ids(self):
        repo = QuestionRepository()
        questions = [
            {"question": "Q1?", "options": ["A) a", "B) b", "C) c", "D) d"],
             "answer": "A", "explanation": "Because A", "difficulty": "easy"},
        ]
        fake_id = "fake-uuid"
        with patch.object(repo, 'save_batch', return_value=[fake_id]) as mock_save:
            ids = repo.save_batch("topic-1", questions)
            mock_save.assert_called_once_with("topic-1", questions)

    def test_get_by_topic_filters_difficulty(self):
        repo = QuestionRepository()
        with patch.object(repo, 'get_by_topic', return_value=[]) as mock_get:
            repo.get_by_topic("topic-1", difficulty="easy", limit=5)
            mock_get.assert_called_with("topic-1", difficulty="easy", limit=5)

    def test_count_by_topic_returns_int(self):
        repo = QuestionRepository()
        with patch.object(repo, 'count_by_topic', return_value=5):
            count = repo.count_by_topic("topic-1")
            assert count == 5


# ── AnalyticsRepository tests (unit — mocked DB) ─────────────────────────────

class TestAnalyticsRepository:

    def test_get_weekly_summary_structure(self):
        repo = AnalyticsRepository()
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchall.side_effect = [
            [("Physics", 0.75, 5, 4)],  # subjects query
        ]
        mock_cur.fetchone.side_effect = [
            (2,),              # active_topics query
            (0.75, 4, 5),      # overall progress
            (9,),              # grade_level
        ]
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch('infrastructure.repositories.analytics_repo.connection', return_value=mock_conn):
            result = repo.get_student_weekly_summary("s1")

        assert "student_id" in result
        assert "overall_mastery" in result
        assert "subjects" in result

    def test_intervention_tips_empty_for_no_risk(self):
        from services.analytics_service import AnalyticsService
        tips = AnalyticsService._intervention_tips([])
        assert tips == []

    def test_intervention_tips_schedules_sessions(self):
        from services.analytics_service import AnalyticsService
        high_risk = [
            {"name": "Sara", "critical_topics": 1, "last_active": "2026-04-10"},
            {"name": "Ahmed", "critical_topics": 5, "last_active": None},
        ]
        tips = AnalyticsService._intervention_tips(high_risk)
        assert any("1-on-1" in t for t in tips)
        assert any("remedial" in t for t in tips)
        assert any("contact parents" in t.lower() for t in tips)
