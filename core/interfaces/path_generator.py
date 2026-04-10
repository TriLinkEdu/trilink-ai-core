from abc import ABC, abstractmethod
from core.models.learning_path import LearningPath


class PathGenerator(ABC):
    """Contract for learning path generation strategies."""

    @abstractmethod
    async def generate(self, student_id: str, subject_id: str) -> LearningPath:
        """
        Generate an ordered learning path for a student in a subject.

        Args:
            student_id: The student's UUID
            subject_id: The subject UUID

        Returns:
            LearningPath with topics ordered by prerequisites and priority
        """
        ...
