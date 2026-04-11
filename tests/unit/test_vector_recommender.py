import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from plugins.recommenders.vector_recommender import VectorRecommender
from core.models.topic import Topic
from core.models.resource import Resource

SUBJECT = "subj-1"


def _topic(tid, name, keywords=None):
    return Topic(
        id=tid, name=name, subject="Physics", subject_id=SUBJECT,
        difficulty_tier="medium", keywords=keywords or [],
    )


def _embedder(dims=384):
    mock = MagicMock()
    mock.dimensions = dims
    mock.embed_batch.side_effect = lambda texts: [
        np.random.rand(dims).tolist() for _ in texts
    ]
    return mock


@pytest.fixture
def recommender():
    embedder = _embedder()
    rec = VectorRecommender(embedder=embedder, db_url="postgresql://fake")
    rec._resources = MagicMock()
    rec._topics = MagicMock()
    return rec


class TestVectorRecommenderCentroid:

    def test_centroid_correct_dimensions(self):
        embedder = _embedder(384)
        rec = VectorRecommender(embedder=embedder, db_url="fake")
        rec._topics = MagicMock()
        rec._topics.get_with_prerequisites.return_value = [
            _topic("t1", "Kinematics"), _topic("t2", "Dynamics")
        ]
        centroid = rec._centroid(["t1", "t2"])
        assert len(centroid) == 384

    def test_centroid_is_normalised(self):
        embedder = _embedder(384)
        rec = VectorRecommender(embedder=embedder, db_url="fake")
        rec._topics = MagicMock()
        rec._topics.get_with_prerequisites.return_value = [
            _topic("t1", "Kinematics")
        ]
        centroid = rec._centroid(["t1"])
        norm = float(np.linalg.norm(centroid))
        assert norm == pytest.approx(1.0, abs=1e-5)

    def test_empty_topics_returns_zero_vector(self):
        embedder = _embedder(384)
        rec = VectorRecommender(embedder=embedder, db_url="fake")
        rec._topics = MagicMock()
        rec._topics.get_with_prerequisites.return_value = []
        centroid = rec._centroid([])
        assert len(centroid) == 384
        assert all(v == 0.0 for v in centroid)

    @pytest.mark.asyncio
    async def test_recommend_calls_find_similar(self, recommender):
        recommender._topics.get_with_prerequisites.return_value = [
            _topic("t1", "Kinematics")
        ]
        recommender._resources.find_similar.return_value = [
            Resource(id="r1", title="T", type="lesson",
                     topic_id="t1", difficulty="medium")
        ]
        result = await recommender.recommend(["t1"], "medium", limit=5)
        recommender._resources.find_similar.assert_called_once()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_recommend_respects_limit(self, recommender):
        recommender._topics.get_with_prerequisites.return_value = [
            _topic("t1", "Kinematics")
        ]
        recommender._resources.find_similar.return_value = [
            Resource(id=f"r{i}", title=f"R{i}", type="lesson",
                     topic_id="t1", difficulty="medium")
            for i in range(10)
        ]
        result = await recommender.recommend(["t1"], "medium", limit=3)
        assert len(result) <= 3
