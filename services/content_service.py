from core.interfaces.content_generator import ContentGenerator
from core.models.resource import Resource
from infrastructure.repositories.resource_repo import ResourceRepository
from infrastructure.repositories.topic_repo import TopicRepository
from infrastructure.repositories.student_repo import StudentRepository


class ContentService:

    def __init__(
        self,
        generator: ContentGenerator,
        resource_repo: ResourceRepository,
        topic_repo: TopicRepository,
    ):
        self._generator = generator
        self._resources = resource_repo
        self._topics    = topic_repo

    async def generate_lesson(self, topic_id: str) -> dict:
        topic   = self._topics.get_by_id(topic_id)
        content = await self._generator.generate_lesson(topic)

        resource = Resource(
            id="", title=f"Lesson: {topic.name}",
            type="lesson", topic_id=topic_id,
            difficulty=topic.difficulty_tier,
            content=content, source="ai_generated",
        )
        new_id = self._resources.save(resource)

        return {
            "resource_id" : new_id,
            "title"       : resource.title,
            "topic_id"    : topic_id,
            "content"     : content,
            "needs_review": True,
            "source"      : "ai_generated",
        }

    async def generate_questions(self, topic_id: str, count: int = 5) -> dict:
        topic     = self._topics.get_by_id(topic_id)
        questions = await self._generator.generate_questions(topic, count)
        return {
            "topic_id" : topic_id,
            "topic_name": topic.name,
            "questions" : questions,
        }
