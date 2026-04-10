from collections import deque
from core.models.topic import Topic
from core.models.learning_path import LearningPath, LearningPathTopic
from core.interfaces.path_generator import PathGenerator
from infrastructure.repositories.student_repo import StudentRepository
from infrastructure.repositories.topic_repo import TopicRepository


class LearningPathService(PathGenerator):

    MASTERY_THRESHOLD = 0.70
    TARGET_MASTERY    = 0.80

    def __init__(self, student_repo: StudentRepository, topic_repo: TopicRepository):
        self._students = student_repo
        self._topics   = topic_repo

    async def generate(self, student_id: str, subject_id: str) -> LearningPath:
        # 1. Get all mastery records for this student × subject
        masteries = self._students.get_all_masteries(student_id, subject_id)
        mastery_map = {m.topic_id: m.mastery_level for m in masteries}

        # 2. All topics in subject — we need the full graph for prerequisite resolution
        all_topics = self._topics.get_by_subject(subject_id)

        # 3. Identify weak topics (below threshold)
        weak_ids = {
            t.id for t in all_topics
            if mastery_map.get(t.id, 0.0) < self.MASTERY_THRESHOLD
        }

        if not weak_ids:
            return LearningPath(student_id=student_id, subject_id=subject_id,
                                overall_progress=1.0)

        # 4. Expand: include any prerequisite that is also weak
        weak_ids = self._expand_prerequisites(weak_ids, all_topics)

        # 5. Topological sort over the weak subgraph
        weak_topics = [t for t in all_topics if t.id in weak_ids]
        ordered     = self._topological_sort(weak_topics)

        # 6. Build path topics with explanations
        path_topics = [
            LearningPathTopic(
                topic_id       = t.id,
                topic_name     = t.name,
                current_mastery= mastery_map.get(t.id, 0.0),
                target_mastery = self.TARGET_MASTERY,
                sequence_order = i + 1,
                explanation    = self._explain(t, mastery_map.get(t.id, 0.0)),
            )
            for i, t in enumerate(ordered)
        ]

        completed = sum(1 for m in masteries if m.mastery_level >= self.MASTERY_THRESHOLD)
        progress  = completed / len(all_topics) if all_topics else 0.0

        return LearningPath(
            student_id      = student_id,
            subject_id      = subject_id,
            topics          = path_topics,
            overall_progress= round(progress, 4),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _expand_prerequisites(self, weak_ids: set[str], all_topics: list[Topic]) -> set[str]:
        """Pull in any prerequisite of a weak topic that is itself weak."""
        topic_map = {t.id: t for t in all_topics}
        expanded  = set(weak_ids)
        queue     = deque(weak_ids)
        while queue:
            tid = queue.popleft()
            for prereq_id in topic_map.get(tid, Topic("","","","","",[])).prerequisites:
                if prereq_id not in expanded and prereq_id in topic_map:
                    expanded.add(prereq_id)
                    queue.append(prereq_id)
        return expanded

    def _topological_sort(self, topics: list[Topic]) -> list[Topic]:
        """Kahn's algorithm — prerequisites come before dependents."""
        ids       = {t.id for t in topics}
        topic_map = {t.id: t for t in topics}
        graph     = {t.id: [] for t in topics}   # prereq → dependents
        in_degree = {t.id: 0  for t in topics}

        for t in topics:
            for prereq in t.prerequisites:
                if prereq in ids:
                    graph[prereq].append(t.id)
                    in_degree[t.id] += 1

        queue  = deque(tid for tid, deg in in_degree.items() if deg == 0)
        result = []
        while queue:
            tid = queue.popleft()
            result.append(topic_map[tid])
            for dependent in graph[tid]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Append any remaining (cycle guard)
        seen = {t.id for t in result}
        result += [t for t in topics if t.id not in seen]
        return result

    @staticmethod
    def _explain(topic: Topic, mastery: float) -> str:
        pct = round(mastery * 100)
        if mastery == 0.0:
            return f"You haven't studied {topic.name} yet. Start here."
        if topic.prerequisites:
            return (
                f"You scored {pct}% on {topic.name}. "
                f"Mastering this unlocks {len(topic.prerequisites)} dependent topic(s)."
            )
        return f"You scored {pct}% on {topic.name}. Bring this above 80% to move forward."
