from abc import ABC, abstractmethod
from core.models.mastery import MasteryUpdate


class KnowledgeTracer(ABC):
    """Contract for any knowledge tracing algorithm (BKT, IRT, etc.)."""

    @abstractmethod
    def update(self, current_mastery: float, is_correct: bool) -> MasteryUpdate:
        """
        Update mastery given a single answer. Pure function — no side effects.

        Args:
            current_mastery: Current mastery level (0.0 – 1.0)
            is_correct: Whether the student answered correctly

        Returns:
            MasteryUpdate with old and new mastery values
        """
        ...

    @abstractmethod
    def predict_mastery(self, history: list[bool]) -> float:
        """
        Predict mastery from a full answer history.

        Args:
            history: Ordered list of correct/incorrect answers

        Returns:
            Predicted mastery level (0.0 – 1.0)
        """
        ...
