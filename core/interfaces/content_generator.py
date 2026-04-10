from abc import ABC, abstractmethod
from core.models.topic import Topic


class ContentGenerator(ABC):
    """Contract for any LLM-backed content generation (Groq, OpenAI, etc.)."""

    @abstractmethod
    async def generate_lesson(self, topic: Topic) -> str:
        """
        Generate a full markdown lesson for a topic.

        Args:
            topic: The curriculum topic to generate content for

        Returns:
            Markdown-formatted lesson string
        """
        ...

    @abstractmethod
    async def generate_questions(self, topic: Topic, count: int) -> list[dict]:
        """
        Generate MCQ questions for a topic.

        Args:
            topic: The curriculum topic
            count: Number of questions to generate

        Returns:
            List of dicts: {question, options, answer, explanation, difficulty}
        """
        ...
