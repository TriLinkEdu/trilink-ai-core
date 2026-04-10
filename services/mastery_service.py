from core.interfaces.knowledge_tracer import KnowledgeTracer
from infrastructure.repositories.student_repo import StudentRepository


class MasteryService:

    MASTERY_THRESHOLD = 0.70

    def __init__(self, tracer: KnowledgeTracer, repo: StudentRepository):
        self._tracer = tracer
        self._repo = repo

    async def process_answer(
        self, student_id: str, topic_id: str, is_correct: bool
    ) -> dict:
        current = self._repo.get_mastery(student_id, topic_id)
        update = self._tracer.update(current.mastery_level, is_correct)
        self._repo.save_mastery(student_id, topic_id, update.new)

        return {
            "topic_id": topic_id,
            "old_mastery": update.old,
            "new_mastery": update.new,
            "assessment_count": current.assessment_count + 1,
            "mastered": update.new >= self.MASTERY_THRESHOLD,
        }

    async def get_mastery(self, student_id: str, topic_id: str) -> dict:
        m = self._repo.get_mastery(student_id, topic_id)
        return {
            "topic_id": topic_id,
            "mastery_level": m.mastery_level,
            "assessment_count": m.assessment_count,
            "mastered": m.mastery_level >= self.MASTERY_THRESHOLD,
        }

    async def get_weak_topics(self, student_id: str, subject_id: str) -> list[dict]:
        masteries = self._repo.get_all_masteries(student_id, subject_id)
        weak = [
            {
                "topic_id": m.topic_id,
                "mastery_level": m.mastery_level,
                "assessment_count": m.assessment_count,
            }
            for m in masteries
            if m.mastery_level < self.MASTERY_THRESHOLD
        ]
        return sorted(weak, key=lambda x: x["mastery_level"])
