from core.interfaces.recommender import Recommender
from core.interfaces.content_generator import ContentGenerator
from core.models.resource import Resource
from infrastructure.repositories.resource_repo import ResourceRepository
from infrastructure.repositories.topic_repo import TopicRepository


class RecommendationService:

    MIN_RESOURCES = 3  # generate AI lesson if fewer found

    def __init__(
        self,
        recommender: Recommender,
        generator: ContentGenerator,
        resource_repo: ResourceRepository,
        topic_repo: TopicRepository,
    ):
        self._recommender = recommender
        self._generator = generator
        self._resources = resource_repo
        self._topics = topic_repo

    async def recommend(
        self,
        student_id: str,
        weak_topic_ids: list[str],
        difficulty: str = "medium",
        limit: int = 5,
    ) -> list[dict]:
        resources = await self._recommender.recommend(weak_topic_ids, difficulty, limit)

        # Gap-fill: if too few resources, generate an AI lesson for the weakest topic
        if len(resources) < self.MIN_RESOURCES and weak_topic_ids:
            lesson = await self._generate_and_save(weak_topic_ids[0], difficulty)
            if lesson:
                resources.append(lesson)

        return [self._to_dict(r) for r in resources]

    async def _generate_and_save(self, topic_id: str, difficulty: str) -> Resource | None:
        try:
            topic = self._topics.get_by_id(topic_id)
            content = await self._generator.generate_lesson(topic)
            resource = Resource(
                id="",
                title=f"Lesson: {topic.name}",
                type="lesson",
                topic_id=topic_id,
                difficulty=difficulty,
                content=content,
                source="ai_generated",
            )
            new_id = self._resources.save(resource)
            resource.id = new_id
            return resource
        except Exception:
            return None  # generation failure is non-fatal

    @staticmethod
    def _to_dict(r: Resource) -> dict:
        return {
            "resource_id": r.id,
            "title": r.title,
            "type": r.type,
            "topic_id": r.topic_id,
            "difficulty": r.difficulty,
            "content": r.content if r.type == "lesson" else "",
            "url": r.url,
            "relevance_score": round(r.relevance_score, 4),
            "avg_rating": r.avg_rating,
            "source": r.source,
        }
