import json
from infrastructure.db.postgres import connection


class QuestionRepository:

    def save_batch(self, topic_id: str, questions: list[dict]) -> list[str]:
        """Persist AI-generated questions. Returns list of new question_ids."""
        ids = []
        with connection() as conn:
            with conn.cursor() as cur:
                for q in questions:
                    cur.execute(
                        """
                        INSERT INTO question_bank
                            (topic_id, question_text, options, correct_answer,
                             explanation, difficulty, source, needs_review)
                        VALUES (%s, %s, %s::jsonb, %s, %s, %s, 'ai_generated', TRUE)
                        RETURNING question_id
                        """,
                        (
                            topic_id,
                            q.get("question", ""),
                            json.dumps(q.get("options", [])),
                            q.get("answer", "A"),
                            q.get("explanation", ""),
                            q.get("difficulty", "medium"),
                        ),
                    )
                    ids.append(str(cur.fetchone()[0]))
        return ids

    def get_by_topic(
        self, topic_id: str, difficulty: str | None = None, limit: int = 10
    ) -> list[dict]:
        with connection() as conn:
            with conn.cursor() as cur:
                if difficulty:
                    cur.execute(
                        """
                        SELECT question_id, question_text, options, correct_answer,
                               explanation, difficulty, needs_review
                        FROM question_bank
                        WHERE topic_id = %s AND difficulty = %s
                        ORDER BY created_at DESC LIMIT %s
                        """,
                        (topic_id, difficulty, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT question_id, question_text, options, correct_answer,
                               explanation, difficulty, needs_review
                        FROM question_bank
                        WHERE topic_id = %s
                        ORDER BY created_at DESC LIMIT %s
                        """,
                        (topic_id, limit),
                    )
                return [self._row_to_dict(r) for r in cur.fetchall()]

    def count_by_topic(self, topic_id: str) -> int:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM question_bank WHERE topic_id = %s",
                    (topic_id,),
                )
                return cur.fetchone()[0]

    @staticmethod
    def _row_to_dict(row) -> dict:
        return {
            "question_id": str(row[0]),
            "question": row[1],
            "options": row[2],
            "answer": row[3],
            "explanation": row[4],
            "difficulty": row[5],
            "needs_review": row[6],
        }
