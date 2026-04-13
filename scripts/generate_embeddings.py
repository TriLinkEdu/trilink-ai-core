"""
Generate and store embeddings for all topics and resources.

Usage:
    python3 scripts/generate_embeddings.py

Reads topics + resources from DB, embeds them with MiniLM,
stores back into the embedding column.

Runtime: ~5 minutes for 359 topics + 359 resources.
Storage: ~4.5 MB total.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.settings import Settings
from infrastructure.db.postgres import init_pool, connection
from infrastructure.repositories.topic_repo import TopicRepository
from infrastructure.repositories.resource_repo import ResourceRepository
from plugins.embedders.minilm_embedder import MiniLMEmbedder


def embed_topics(embedder: MiniLMEmbedder, topic_repo: TopicRepository):
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT topic_id, topic_name, subject_id, keywords FROM topic WHERE embedding IS NULL"
            )
            rows = cur.fetchall()

    if not rows:
        print("Topics: all embeddings already generated.")
        return

    print(f"Embedding {len(rows)} topics...")
    ids   = [str(r[0]) for r in rows]
    texts = [
        f"{r[1]} {' '.join(r[3] or [])}"
        for r in rows
    ]

    vectors = embedder.embed_batch(texts)
    for topic_id, vector in zip(ids, vectors):
        topic_repo.save_embedding(topic_id, vector)

    print(f"Topics: {len(ids)} embeddings stored.")


def embed_resources(embedder: MiniLMEmbedder, resource_repo: ResourceRepository):
    with connection() as conn:
        with conn.cursor() as cur:
            # Re-embed ALL resources (not just NULL) to fix quality issues
            cur.execute(
                "SELECT resource_id, title, content FROM resource"
            )
            rows = cur.fetchall()

    if not rows:
        print("Resources: none found.")
        return

    print(f"Embedding {len(rows)} resources...")
    ids   = [str(r[0]) for r in rows]

    # Skip template boilerplate — use title + first 500 chars of actual content
    # Strip markdown headers and template lines
    def extract_body(title: str, content: str) -> str:
        lines = content.splitlines()
        body_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip template placeholders and empty lines at start
            if not stripped:
                continue
            if any(p in stripped for p in ["[Your Name", "[Current Date", "**Teacher:**", "**Date:**", "**Subject:**"]):
                continue
            body_lines.append(stripped)
            if len(" ".join(body_lines)) > 500:
                break
        body = " ".join(body_lines)[:500]
        return f"{title} {body}" if body else title

    texts = [extract_body(r[1], r[2] or "") for r in rows]

    vectors = embedder.embed_batch(texts)
    for resource_id, vector in zip(ids, vectors):
        resource_repo.save_embedding(resource_id, vector)

    print(f"Resources: {len(ids)} embeddings stored.")


def run():
    settings = Settings()
    init_pool(settings.POSTGRES_URL)

    embedder      = MiniLMEmbedder()
    topic_repo    = TopicRepository()
    resource_repo = ResourceRepository()

    embed_topics(embedder, topic_repo)
    embed_resources(embedder, resource_repo)

    print("\nDone. Run this script again after adding new topics or resources.")


if __name__ == "__main__":
    run()
