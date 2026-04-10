from abc import ABC, abstractmethod
from core.models.resource import Resource


class Recommender(ABC):
    """Contract for any resource recommendation strategy."""

    @abstractmethod
    async def recommend(
        self,
        weak_topic_ids: list[str],
        difficulty: str,
        limit: int = 5,
    ) -> list[Resource]:
        """
        Return ranked resources for a student's weak topics.

        Args:
            weak_topic_ids: Topics where mastery < threshold
            difficulty: Target difficulty level (easy | medium | hard)
            limit: Max number of resources to return

        Returns:
            Resources sorted by relevance_score descending
        """
        ...
