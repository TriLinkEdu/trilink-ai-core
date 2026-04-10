"""
Bulk lesson + question generation for all 359 curriculum topics.

Usage:
    python3 scripts/generate_content.py

Reads topics from DB, generates lessons + 5 questions each via Groq,
stores everything with needs_review=TRUE.

Rate limit: Groq free tier = 30 req/min → 2s delay between calls.
Estimated runtime: ~12 minutes for 359 topics.
"""
import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.settings import Settings
from infrastructure.db.postgres import init_pool
from infrastructure.repositories.topic_repo import TopicRepository
from infrastructure.repositories.resource_repo import ResourceRepository
from plugins.generators.groq_generator import GroqGenerator
from services.content_service import ContentService


DELAY_BETWEEN_TOPICS = 2.0   # seconds — stay under 30 req/min
SUBJECTS = ["math", "physics", "chemistry", "biology", "english"]


async def run():
    settings = Settings()
    init_pool(settings.POSTGRES_URL)

    generator = GroqGenerator(api_key=settings.GROQ_API_KEY)
    svc = ContentService(
        generator    =generator,
        resource_repo=ResourceRepository(),
        topic_repo   =TopicRepository(),
    )

    topic_repo = TopicRepository()
    topics = []
    for subject_id in _get_subject_ids():
        topics.extend(topic_repo.get_by_subject(subject_id))

    total   = len(topics)
    success = 0
    failed  = []

    print(f"Generating content for {total} topics...\n")

    for i, topic in enumerate(topics, 1):
        try:
            lesson = await svc.generate_lesson(topic.id)
            print(f"[{i}/{total}] ✓ Lesson: {topic.name}")

            await asyncio.sleep(DELAY_BETWEEN_TOPICS)

            questions = await svc.generate_questions(topic.id, count=5)
            print(f"[{i}/{total}] ✓ Questions: {len(questions['questions'])} generated")

            success += 1
        except Exception as e:
            print(f"[{i}/{total}] ✗ FAILED {topic.name}: {e}")
            failed.append({"topic_id": topic.id, "name": topic.name, "error": str(e)})

        await asyncio.sleep(DELAY_BETWEEN_TOPICS)

    print(f"\n{'='*50}")
    print(f"Done. {success}/{total} succeeded.")
    if failed:
        print(f"\nFailed ({len(failed)}):")
        for f in failed:
            print(f"  - {f['name']}: {f['error']}")


def _get_subject_ids() -> list[str]:
    """Fetch subject UUIDs from DB."""
    from infrastructure.db.postgres import connection
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT subject_id FROM subject ORDER BY subject_name")
            return [str(r[0]) for r in cur.fetchall()]


if __name__ == "__main__":
    asyncio.run(run())
