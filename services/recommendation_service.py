import requests
from core.interfaces.recommender import Recommender
from core.interfaces.content_generator import ContentGenerator
from core.models.resource import Resource
from infrastructure.repositories.resource_repo import ResourceRepository
from infrastructure.repositories.topic_repo import TopicRepository

_YT_SEARCH = "https://www.googleapis.com/youtube/v3/search"
_YT_VIDEOS = 2  # videos to fetch per recommendation request


def _fetch_youtube(query: str, api_key: str) -> list[dict]:
    try:
        resp = requests.get(_YT_SEARCH, params={
            "part": "snippet", "q": query, "type": "video",
            "maxResults": _YT_VIDEOS, "safeSearch": "strict", "key": api_key,
        }, timeout=5)
        resp.raise_for_status()
        return [
            {
                "resource_id": f"yt-{item['id']['videoId']}",
                "title": item["snippet"]["title"],
                "type": "youtube_video",
                "topic_id": None,
                "difficulty": "medium",
                "content": "",
                "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                "relevance_score": 0.8,
                "avg_rating": 0.0,
                "source": "youtube",
            }
            for item in resp.json().get("items", [])
        ]
    except Exception:
        return []  # YouTube failure is non-fatal


class RecommendationService:

    MIN_RESOURCES = 3

    def __init__(
        self,
        recommender: Recommender,
        generator: ContentGenerator,
        resource_repo: ResourceRepository,
        topic_repo: TopicRepository,
        youtube_api_key: str = "",
    ):
        self._recommender    = recommender
        self._generator      = generator
        self._resources      = resource_repo
        self._topics         = topic_repo
        self._youtube_key    = youtube_api_key

    async def recommend(
        self,
        student_id: str,
        weak_topic_ids: list[str],
        difficulty: str = "medium",
        limit: int = 5,
    ) -> list[dict]:
        resources = await self._recommender.recommend(weak_topic_ids, difficulty, limit)

        # Gap-fill: generate AI lesson if too few DB resources
        if len(resources) < self.MIN_RESOURCES and weak_topic_ids:
            lesson = await self._generate_and_save(weak_topic_ids[0], difficulty)
            if lesson:
                resources.append(lesson)

        result = [self._to_dict(r) for r in resources]

        # Append live YouTube videos if API key configured
        if self._youtube_key and weak_topic_ids:
            topic = self._topics.get_by_id(weak_topic_ids[0])
            query = f"{topic.subject} {topic.name} lesson"
            result += _fetch_youtube(query, self._youtube_key)

        return result

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
