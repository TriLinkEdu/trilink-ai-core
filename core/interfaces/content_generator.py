from abc import ABC, abstractmethod
from core.models.topic import Topic


class ContentGenerator(ABC):
    """Contract for any LLM-backed content generation (Groq, OpenAI, etc.)."""

    @abstractmethod
    async def generate_lesson(self, topic: Topic) -> str:
        """Generate a full markdown lesson for a topic."""
        ...

    @abstractmethod
    async def generate_questions(self, topic: Topic, count: int) -> list[dict]:
        """Generate MCQ questions. Returns list of dicts."""
        ...

    @abstractmethod
    async def _call_raw(self, prompt: str) -> str:
        """Send a raw prompt, return response text. Used by ChatService."""
        ...
