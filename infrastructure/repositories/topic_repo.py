from core.models.topic import Topic
from core.exceptions import TopicNotFoundError
from infrastructure.db.postgres import connection


class TopicRepository:

    def get_by_id(self, topic_id: str) -> Topic:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT t.topic_id, t.topic_name, s.subject_name, t.subject_id,
                           t.difficulty_tier, t.objectives, t.keywords, t.parent_topic_id,
                           s.grade_level
                    FROM topic t
                    JOIN subject s ON s.subject_id = t.subject_id
                    WHERE t.topic_id = %s
                    """,
                    (topic_id,),
                )
                row = cur.fetchone()

        if row is None:
            raise TopicNotFoundError(topic_id)
        return self._row_to_topic(row)

    def get_with_prerequisites(self, topic_ids: list[str]) -> list[Topic]:
        if not topic_ids:
            return []
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT t.topic_id, t.topic_name, s.subject_name, t.subject_id,
                           t.difficulty_tier, t.objectives, t.keywords, t.parent_topic_id,
                           s.grade_level,
                           ARRAY_AGG(tp.prereq_id) FILTER (WHERE tp.prereq_id IS NOT NULL)
                    FROM topic t
                    JOIN subject s ON s.subject_id = t.subject_id
                    LEFT JOIN topic_prerequisite tp ON tp.topic_id = t.topic_id
                    WHERE t.topic_id = ANY(%s)
                    GROUP BY t.topic_id, s.subject_name, s.grade_level
                    """,
                    (topic_ids,),
                )
                rows = cur.fetchall()

        return [self._row_to_topic(r, prereqs=r[9]) for r in rows]

    def get_by_subject(self, subject_id: str) -> list[Topic]:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT t.topic_id, t.topic_name, s.subject_name, t.subject_id,
                           t.difficulty_tier, t.objectives, t.keywords, t.parent_topic_id,
                           s.grade_level
                    FROM topic t
                    JOIN subject s ON s.subject_id = t.subject_id
                    WHERE t.subject_id = %s
                    ORDER BY t.topic_name
                    """,
                    (subject_id,),
                )
                rows = cur.fetchall()

        return [self._row_to_topic(r) for r in rows]

    def save_embedding(self, topic_id: str, embedding: list[float]) -> None:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE topic SET embedding = %s WHERE topic_id = %s",
                    (embedding, topic_id),
                )

    @staticmethod
    def _row_to_topic(row, prereqs: list | None = None) -> Topic:
        return Topic(
            id=str(row[0]),
            name=row[1],
            subject=row[2],
            subject_id=str(row[3]),
            difficulty_tier=row[4],
            objectives=list(row[5] or []),
            keywords=list(row[6] or []),
            parent_topic_id=str(row[7]) if row[7] else None,
            grade_level=int(row[8]) if row[8] else 9,
            prerequisites=[str(p) for p in (prereqs or [])],
        )
