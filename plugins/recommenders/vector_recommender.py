import numpy as np
from core.interfaces.recommender import Recommender
from core.interfaces.embedder import Embedder
from core.models.resource import Resource
from infrastructure.repositories.resource_repo import ResourceRepository
from infrastructure.repositories.topic_repo import TopicRepository


class VectorRecommender(Recommender):
    """
    Semantic search: compute centroid of weak-topic embeddings,
    then find resources closest to that centroid via pgvector.
    """

    def __init__(self, embedder: Embedder, db_url: str):
        self._embedder = embedder
        self._resources = ResourceRepository()
        self._topics = TopicRepository()

    async def recommend(
        self,
        weak_topic_ids: list[str],
        difficulty: str,
        limit: int = 5,
    ) -> list[Resource]:
        centroid = self._centroid(weak_topic_ids)
        return self._resources.find_similar(centroid, difficulty, limit=limit * 2)[
            :limit
        ]

    def _centroid(self, topic_ids: list[str]) -> list[float]:
        """Average the embeddings of all weak topics into one query vector."""
        topics = self._topics.get_with_prerequisites(topic_ids)

        # Use topic names to generate embeddings (topics may not have stored embeddings yet)
        texts = [f"{t.subject} {t.name} {' '.join(t.keywords)}" for t in topics]
        if not texts:
            # Fallback: zero vector — will return lowest-distance resources
            return [0.0] * self._embedder.dimensions

        vectors = np.array(self._embedder.embed_batch(texts))
        centroid = vectors.mean(axis=0)
        # Re-normalise after averaging
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm
        return centroid.tolist()
