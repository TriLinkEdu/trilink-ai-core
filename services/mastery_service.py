"""
MasteryService — wired to BKTService for per-topic fitted BKT parameters.

Previously: used hardcoded global BKT parameters for every topic.
Now: retrieves per-topic EM-fitted parameters from BKTService, which gives
each topic its own calibrated slip/guess/learn rates based on actual student data.

Also now persists individual responses to student_response_log so that the EM
fitting improves over time as more students answer questions.
"""

from core.interfaces.knowledge_tracer import KnowledgeTracer
from infrastructure.repositories.student_repo import StudentRepository
from infrastructure.repositories.mongo_repos import AuditRepository
from plugins.tracers.bkt_tracer import BKTTracer
from services.bkt_service import BKTService


class MasteryService:

    MASTERY_THRESHOLD = 0.70

    def __init__(
        self,
        tracer    : KnowledgeTracer,
        repo      : StudentRepository,
        bkt_svc   : BKTService | None = None,
    ):
        self._tracer  = tracer
        self._repo    = repo
        self._bkt_svc = bkt_svc
        self._audit   = AuditRepository()

    async def process_answer(
        self, student_id: str, topic_id: str, is_correct: bool
    ) -> dict:
        # 1. Get current mastery from DB
        current = self._repo.get_mastery(student_id, topic_id)

        # 2. Select the best tracer for this topic:
        #    - If BKTService is available, use its per-topic fitted parameters.
        #    - Otherwise fall back to the injected global tracer.
        tracer = self._resolve_tracer(topic_id)
        update = tracer.update(current.mastery_level, is_correct)

        # 3. Persist updated mastery
        self._repo.save_mastery(student_id, topic_id, update.new)

        # 4. Persist the raw response so BKT EM fitting improves over time
        self._repo.save_response(student_id, topic_id, is_correct)

        # 5. Audit log
        self._audit.log(
            actor_id   = student_id,
            action     = "mastery_updated",
            entity     = "student_topic_mastery",
            entity_id  = f"{student_id}:{topic_id}",
            metadata   = {
                "old"        : update.old,
                "new"        : update.new,
                "is_correct" : is_correct,
                "bkt_fitted" : self._bkt_svc is not None,
            },
        )

        return {
            "topic_id"         : topic_id,
            "old_mastery"      : update.old,
            "new_mastery"      : update.new,
            "assessment_count" : current.assessment_count + 1,
            "mastered"         : update.new >= self.MASTERY_THRESHOLD,
        }

    async def get_mastery(self, student_id: str, topic_id: str) -> dict:
        m = self._repo.get_mastery(student_id, topic_id)
        return {
            "topic_id"         : topic_id,
            "mastery_level"    : m.mastery_level,
            "assessment_count" : m.assessment_count,
            "mastered"         : m.mastery_level >= self.MASTERY_THRESHOLD,
        }

    async def get_weak_topics(self, student_id: str, subject_id: str) -> list[dict]:
        masteries = self._repo.get_all_masteries(student_id, subject_id)
        weak = [
            {
                "topic_id"         : m.topic_id,
                "mastery_level"    : m.mastery_level,
                "assessment_count" : m.assessment_count,
            }
            for m in masteries
            if m.mastery_level < self.MASTERY_THRESHOLD
        ]
        return sorted(weak, key=lambda x: x["mastery_level"])

    # ── Private ───────────────────────────────────────────────────────────────

    def _resolve_tracer(self, topic_id: str) -> KnowledgeTracer:
        """
        Return a BKTTracer configured with per-topic EM-fitted parameters,
        falling back to the injected global tracer if BKTService is unavailable.
        """
        if self._bkt_svc is None:
            return self._tracer

        params = self._bkt_svc.get_params_for_topic(topic_id)
        return BKTTracer(params.to_dict())
