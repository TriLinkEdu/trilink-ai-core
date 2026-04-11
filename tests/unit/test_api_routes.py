import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch


def _make_app(registry_overrides: dict):
    """Build a test app with mocked registry."""
    from fastapi import FastAPI
    from api.routes import mastery, recommendations, learning_path, content

    app = FastAPI()
    app.include_router(mastery.router,         prefix="/api/ai")
    app.include_router(recommendations.router, prefix="/api/ai")
    app.include_router(learning_path.router,   prefix="/api/ai")
    app.include_router(content.router,         prefix="/api/ai")

    registry = MagicMock()
    for k, v in registry_overrides.items():
        setattr(registry, k, v)
    app.state.registry = registry
    return app


# ---------------------------------------------------------------------------
# Mastery routes
# ---------------------------------------------------------------------------

class TestMasteryRoutes:

    @pytest.fixture
    def client(self):
        tracer = MagicMock()
        tracer.update.return_value = MagicMock(old=0.5, new=0.65)

        repo_mock = MagicMock()
        repo_mock.get_mastery.return_value = MagicMock(
            mastery_level=0.5, assessment_count=3
        )
        repo_mock.save_mastery.return_value = None

        with patch(
            "api.routes.mastery.StudentRepository", return_value=repo_mock
        ):
            app = _make_app({"tracer": tracer})
            yield TestClient(app)

    def test_update_mastery_200(self, client):
        resp = client.post("/api/ai/mastery/update", json={
            "student_id": "s1", "topic_id": "t1", "is_correct": True
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "new_mastery" in data
        assert "mastered" in data

    def test_update_mastery_missing_field_422(self, client):
        resp = client.post("/api/ai/mastery/update", json={
            "student_id": "s1", "topic_id": "t1"
            # missing is_correct
        })
        assert resp.status_code == 422

    def test_get_mastery_200(self, client):
        resp = client.get("/api/ai/mastery/s1/t1")
        assert resp.status_code == 200
        assert "mastery_level" in resp.json()


# ---------------------------------------------------------------------------
# Learning path routes
# ---------------------------------------------------------------------------

class TestLearningPathRoutes:

    @pytest.fixture
    def client(self):
        from core.models.learning_path import LearningPath

        student_repo = MagicMock()
        student_repo.get_all_masteries.return_value = []
        topic_repo = MagicMock()
        topic_repo.get_by_subject.return_value = []

        with patch("api.routes.learning_path.StudentRepository",
                   return_value=student_repo), \
             patch("api.routes.learning_path.TopicRepository",
                   return_value=topic_repo):
            app = _make_app({})
            yield TestClient(app)

    def test_generate_path_200(self, client):
        resp = client.post("/api/ai/learning-path", json={
            "student_id": "s1", "subject_id": "subj1"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "topics" in data
        assert "overall_progress" in data

    def test_generate_path_missing_field_422(self, client):
        resp = client.post("/api/ai/learning-path", json={"student_id": "s1"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Recommendation routes
# ---------------------------------------------------------------------------

class TestRecommendationRoutes:

    @pytest.fixture
    def client(self):
        recommender = MagicMock()
        recommender.recommend = AsyncMock(return_value=[])
        generator = MagicMock()
        generator.generate_lesson = AsyncMock(return_value="# Lesson")

        resource_repo = MagicMock()
        resource_repo.save.return_value = "new-id"
        topic_repo = MagicMock()

        with patch("api.routes.recommendations.ResourceRepository",
                   return_value=resource_repo), \
             patch("api.routes.recommendations.TopicRepository",
                   return_value=topic_repo):
            app = _make_app({"recommender": recommender, "generator": generator})
            yield TestClient(app)

    def test_recommend_200(self, client):
        resp = client.post("/api/ai/recommendations", json={
            "student_id": "s1",
            "weak_topic_ids": ["t1"],
            "difficulty": "medium",
            "limit": 5,
        })
        assert resp.status_code == 200
        assert "resources" in resp.json()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_health():
    from main import create_app
    with patch("main.init_pool"), patch("main.get_registry"):
        app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    # Just verify the route exists and returns 200 without DB
    resp = client.get("/health")
    assert resp.status_code == 200
