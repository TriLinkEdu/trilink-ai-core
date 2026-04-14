from infrastructure.db.postgres import connection


class AnalyticsRepository:

    def get_student_weekly_summary(self, student_id: str) -> dict:
        with connection() as conn:
            with conn.cursor() as cur:
                # Mastery per subject this week vs last week
                cur.execute("""
                    SELECT s.subject_name,
                           AVG(stm.mastery_level) as current_avg,
                           COUNT(stm.topic_id) as topics_assessed,
                           SUM(CASE WHEN stm.mastery_level >= 0.7 THEN 1 ELSE 0 END) as mastered
                    FROM student_topic_mastery stm
                    JOIN topic t ON t.topic_id = stm.topic_id
                    JOIN subject s ON s.subject_id = t.subject_id
                    WHERE stm.student_id = %s
                    GROUP BY s.subject_name
                    ORDER BY current_avg DESC
                """, (student_id,))
                subjects = [
                    {
                        "subject": r[0],
                        "avg_mastery": round(float(r[1]), 3),
                        "topics_assessed": r[2],
                        "topics_mastered": r[3],
                    }
                    for r in cur.fetchall()
                ]

                # Recent activity count (last 7 days)
                cur.execute("""
                    SELECT COUNT(*) FROM student_topic_mastery
                    WHERE student_id = %s
                    AND last_assessed >= NOW() - INTERVAL '7 days'
                """, (student_id,))
                active_topics = cur.fetchone()[0]

                # Overall progress
                cur.execute("""
                    SELECT AVG(mastery_level),
                           SUM(CASE WHEN mastery_level >= 0.7 THEN 1 ELSE 0 END),
                           COUNT(*)
                    FROM student_topic_mastery WHERE student_id = %s
                """, (student_id,))
                row = cur.fetchone()
                overall = float(row[0]) if row[0] else 0.0
                mastered_total = row[1] or 0
                assessed_total = row[2] or 0

        return {
            "student_id": student_id,
            "overall_mastery": round(overall, 3),
            "topics_mastered": mastered_total,
            "topics_assessed": assessed_total,
            "active_topics_this_week": active_topics,
            "subjects": subjects,
        }

    def get_at_risk_students(self, subject_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        sp.student_id,
                        u.first_name || ' ' || u.last_name as name,
                        AVG(stm.mastery_level) as avg_mastery,
                        COUNT(stm.topic_id) as topics_assessed,
                        SUM(CASE WHEN stm.mastery_level < 0.4 THEN 1 ELSE 0 END) as critical_topics,
                        MAX(stm.last_assessed) as last_active
                    FROM student_profile sp
                    JOIN "user" u ON u.user_id = sp.student_id
                    LEFT JOIN (
                        SELECT stm.*
                        FROM student_topic_mastery stm
                        JOIN topic t ON t.topic_id = stm.topic_id
                        WHERE t.subject_id = %s
                    ) stm ON stm.student_id = sp.student_id
                    GROUP BY sp.student_id, u.first_name, u.last_name
                    HAVING AVG(stm.mastery_level) < 0.6 OR AVG(stm.mastery_level) IS NULL
                    ORDER BY avg_mastery ASC NULLS FIRST
                    LIMIT %s OFFSET %s
                """, (subject_id, limit, offset))

                students = []
                for r in cur.fetchall():
                    avg = float(r[2]) if r[2] else 0.0
                    risk = "HIGH" if avg < 0.4 else "MEDIUM"
                    students.append({
                        "student_id": str(r[0]),
                        "name": r[1],
                        "avg_mastery": round(avg, 3),
                        "topics_assessed": r[3] or 0,
                        "critical_topics": r[4] or 0,
                        "last_active": r[5].isoformat() if r[5] else None,
                        "risk_level": risk,
                    })
                return students

    def get_class_performance(self, subject_id: str, limit: int = 50, offset: int = 0) -> dict:
        with connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT t.topic_name, t.topic_code,
                           AVG(stm.mastery_level) as avg_mastery,
                           COUNT(stm.student_id) as students_assessed
                    FROM topic t
                    LEFT JOIN student_topic_mastery stm ON stm.topic_id = t.topic_id
                    WHERE t.subject_id = %s
                    GROUP BY t.topic_id, t.topic_name, t.topic_code
                    ORDER BY avg_mastery ASC NULLS FIRST
                    LIMIT %s OFFSET %s
                """, (subject_id, limit, offset))

                topics = []
                for r in cur.fetchall():
                    avg = float(r[2]) if r[2] else None
                    topics.append({
                        "topic_name": r[0],
                        "topic_code": r[1],
                        "avg_mastery": round(avg, 3) if avg else None,
                        "students_assessed": r[3],
                        "status": (
                            "strong" if avg and avg >= 0.7 else
                            "weak" if avg and avg < 0.5 else
                            "progressing" if avg else "not_started"
                        ),
                    })

                # Overall subject stats
                cur.execute("""
                    SELECT AVG(stm.mastery_level), COUNT(DISTINCT stm.student_id)
                    FROM student_topic_mastery stm
                    JOIN topic t ON t.topic_id = stm.topic_id
                    WHERE t.subject_id = %s
                """, (subject_id,))
                row = cur.fetchone()
                overall = float(row[0]) if row[0] else 0.0

                weak   = [t for t in topics if t["status"] == "weak"]
                strong = [t for t in topics if t["status"] == "strong"]

        return {
            "subject_id": subject_id,
            "overall_avg_mastery": round(overall, 3),
            "total_students": row[1] or 0,
            "weak_topics": weak[:5],    # top 5 weakest
            "strong_topics": strong[:5],
            "all_topics": topics,
        }
