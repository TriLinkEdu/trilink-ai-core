from core.models.mastery import TopicMastery
from core.exceptions import MasteryNotFoundError
from infrastructure.db.postgres import connection


class StudentRepository:

    def get_mastery(self, student_id: str, topic_id: str) -> TopicMastery:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT mastery_level, assessment_count
                    FROM student_topic_mastery
                    WHERE student_id = %s AND topic_id = %s
                    """,
                    (student_id, topic_id),
                )
                row = cur.fetchone()

        if row is None:
            # Cold start — return prior, don't raise
            return TopicMastery(
                student_id=student_id,
                topic_id=topic_id,
                mastery_level=0.1,
                assessment_count=0,
            )
        return TopicMastery(
            student_id=student_id,
            topic_id=topic_id,
            mastery_level=float(row[0]),
            assessment_count=row[1],
        )

    def save_mastery(self, student_id: str, topic_id: str, mastery: float) -> None:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO student_topic_mastery
                        (student_id, topic_id, mastery_level, assessment_count, last_assessed)
                    VALUES (%s, %s, %s, 1, NOW())
                    ON CONFLICT (student_id, topic_id) DO UPDATE SET
                        mastery_level    = EXCLUDED.mastery_level,
                        assessment_count = student_topic_mastery.assessment_count + 1,
                        last_assessed    = NOW()
                    """,
                    (student_id, topic_id, mastery),
                )

    def get_all_masteries(self, student_id: str, subject_id: str) -> list[TopicMastery]:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT stm.topic_id, stm.mastery_level, stm.assessment_count
                    FROM student_topic_mastery stm
                    JOIN topic t ON t.topic_id = stm.topic_id
                    WHERE stm.student_id = %s AND t.subject_id = %s
                    """,
                    (student_id, subject_id),
                )
                rows = cur.fetchall()

        return [
            TopicMastery(
                student_id=student_id,
                topic_id=str(r[0]),
                mastery_level=float(r[1]),
                assessment_count=r[2],
            )
            for r in rows
        ]

    def save_response(self, student_id: str, topic_id: str, is_correct: bool) -> None:
        """
        Persist a single question response to the response log.
        This log is the source of truth for BKT EM parameter fitting.

        The table is created on first write (self-bootstrapping) to avoid
        requiring a separate migration for this new feature.
        """
        with connection() as conn:
            with conn.cursor() as cur:
                # Create table if it doesn't exist yet (idempotent)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS student_response_log (
                        id           BIGSERIAL PRIMARY KEY,
                        student_id   UUID        NOT NULL,
                        topic_id     UUID        NOT NULL,
                        is_correct   BOOLEAN     NOT NULL,
                        answered_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS idx_srl_topic_id
                        ON student_response_log (topic_id, answered_at);
                """)
                cur.execute(
                    """
                    INSERT INTO student_response_log (student_id, topic_id, is_correct)
                    VALUES (%s, %s, %s)
                    """,
                    (student_id, topic_id, is_correct),
                )

    def get_response_sequences(self, topic_id: str) -> list[list[bool]]:
        """
        Return per-student ordered response sequences for BKT EM fitting.

        Returns a list of sequences, one per student, each an ordered list of
        True (correct) / False (incorrect) answers, oldest to newest.
        """
        with connection() as conn:
            with conn.cursor() as cur:
                # Graceful fallback: return empty list if table doesn't exist yet
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'student_response_log'
                    )
                """)
                if not cur.fetchone()[0]:
                    return []

                cur.execute(
                    """
                    SELECT student_id, is_correct
                    FROM   student_response_log
                    WHERE  topic_id = %s
                    ORDER  BY student_id, answered_at ASC
                    """,
                    (topic_id,),
                )
                rows = cur.fetchall()

        # Group rows into per-student sequences
        sequences: dict[str, list[bool]] = {}
        for student_id, is_correct in rows:
            sequences.setdefault(str(student_id), []).append(bool(is_correct))

        return list(sequences.values())
