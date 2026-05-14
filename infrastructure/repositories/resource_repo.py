from core.models.resource import Resource
from infrastructure.db.postgres import connection


class ResourceRepository:

    def find_similar(
        self,
        embedding: list[float],
        difficulty: str,
        limit: int = 10,
    ) -> list[Resource]:
        """Vector similarity search — returns resources ordered by cosine distance."""
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT resource_id, title, type, topic_id, difficulty,
                           content, url, avg_rating, source,
                           1 - (embedding <=> %s::vector) AS score
                    FROM resource
                    WHERE difficulty = %s
                      AND embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (embedding, difficulty, embedding, limit),
                )
                rows = cur.fetchall()

        return [self._row_to_resource(r) for r in rows]

    def save(self, resource: Resource) -> str:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO resource
                        (topic_id, title, type, content, url, difficulty,
                         source, needs_review, avg_rating)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE, 0)
                    RETURNING resource_id
                    """,
                    (
                        resource.topic_id, resource.title, resource.type,
                        resource.content, resource.url, resource.difficulty,
                        resource.source,
                    ),
                )
                return str(cur.fetchone()[0])

    def save_embedding(self, resource_id: str, embedding: list[float]) -> None:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE resource SET embedding = %s WHERE resource_id = %s",
                    (embedding, resource_id),
                )

    def find_all_with_content(self, limit: int = 5000) -> list[Resource]:
        """
        Fetch all resources that have textual content for BM25 index building.

        The BM25 index is built in-memory per request. The 5000-resource cap
        prevents memory issues; in practice most corpora are much smaller.
        For large corpora, consider pre-building and caching the BM25 index.
        """
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT resource_id, title, type, topic_id, difficulty,
                           content, url, avg_rating, source, 0.0 AS score
                    FROM resource
                    WHERE content IS NOT NULL AND content != ''
                    ORDER BY resource_id
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = cur.fetchall()

        return [self._row_to_resource(r) for r in rows]

    @staticmethod
    def _row_to_resource(row) -> Resource:
        return Resource(
            id=str(row[0]),
            title=row[1],
            type=row[2],
            topic_id=str(row[3]),
            difficulty=row[4],
            content=row[5] or "",
            url=row[6] or "",
            avg_rating=float(row[7]),
            source=row[8],
            relevance_score=float(row[9]),
        )
