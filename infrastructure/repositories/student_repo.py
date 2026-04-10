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
