import pytest
from unittest.mock import MagicMock
from services.learning_path_service import LearningPathService
from core.models.topic import Topic
from core.models.mastery import TopicMastery

STUDENT = "s1"
SUBJECT = "subj-physics"


def _topic(tid, name, prereqs=None):
    return Topic(
        id=tid, name=name, subject="Physics", subject_id=SUBJECT,
        difficulty_tier="medium", prerequisites=prereqs or [],
    )


def _mastery(tid, level):
    return TopicMastery(student_id=STUDENT, topic_id=tid,
                        mastery_level=level, assessment_count=3)


@pytest.fixture
def repos():
    student_repo = MagicMock()
    topic_repo   = MagicMock()
    return student_repo, topic_repo


@pytest.fixture
def svc(repos):
    return LearningPathService(student_repo=repos[0], topic_repo=repos[1])


class TestTopologicalSort:
    """Pure algorithm tests — no mocks needed."""

    def _svc(self):
        return LearningPathService(MagicMock(), MagicMock())

    def test_linear_chain_ordered(self):
        # A → B → C  (A is prereq of B, B is prereq of C)
        a = _topic("A", "Algebra",    prereqs=[])
        b = _topic("B", "Linear Eq",  prereqs=["A"])
        c = _topic("C", "Quadratic",  prereqs=["B"])
        result = self._svc()._topological_sort([c, b, a])  # intentionally shuffled
        ids = [t.id for t in result]
        assert ids.index("A") < ids.index("B") < ids.index("C")

    def test_diamond_dependency(self):
        # A → B, A → C, B → D, C → D
        a = _topic("A", "Base",  prereqs=[])
        b = _topic("B", "Left",  prereqs=["A"])
        c = _topic("C", "Right", prereqs=["A"])
        d = _topic("D", "Top",   prereqs=["B", "C"])
        result = self._svc()._topological_sort([d, c, b, a])
        ids = [t.id for t in result]
        assert ids.index("A") < ids.index("B")
        assert ids.index("A") < ids.index("C")
        assert ids.index("B") < ids.index("D")
        assert ids.index("C") < ids.index("D")

    def test_no_prerequisites_any_order(self):
        topics = [_topic(str(i), f"Topic {i}") for i in range(5)]
        result = self._svc()._topological_sort(topics)
        assert len(result) == 5

    def test_cycle_guard_returns_all_topics(self):
        # Cycle: A → B → A (shouldn't crash, should return all)
        a = _topic("A", "A", prereqs=["B"])
        b = _topic("B", "B", prereqs=["A"])
        result = self._svc()._topological_sort([a, b])
        assert len(result) == 2


class TestLearningPathService:

    @pytest.mark.asyncio
    async def test_all_mastered_returns_empty_path(self, svc, repos):
        student_repo, topic_repo = repos
        student_repo.get_all_masteries.return_value = [
            _mastery("t1", 0.9), _mastery("t2", 0.85)
        ]
        topic_repo.get_by_subject.return_value = [
            _topic("t1", "Kinematics"), _topic("t2", "Dynamics")
        ]
        path = await svc.generate(STUDENT, SUBJECT)
        assert path.topics == []
        assert path.overall_progress == 1.0

    @pytest.mark.asyncio
    async def test_weak_topics_included_in_path(self, svc, repos):
        student_repo, topic_repo = repos
        student_repo.get_all_masteries.return_value = [
            _mastery("t1", 0.4),   # weak
            _mastery("t2", 0.85),  # strong
        ]
        topic_repo.get_by_subject.return_value = [
            _topic("t1", "Kinematics"), _topic("t2", "Dynamics")
        ]
        path = await svc.generate(STUDENT, SUBJECT)
        ids = [t.topic_id for t in path.topics]
        assert "t1" in ids
        assert "t2" not in ids

    @pytest.mark.asyncio
    async def test_prerequisites_respected_in_ordering(self, svc, repos):
        student_repo, topic_repo = repos
        student_repo.get_all_masteries.return_value = [
            _mastery("t1", 0.3),
            _mastery("t2", 0.2),
        ]
        topic_repo.get_by_subject.return_value = [
            _topic("t1", "Uniform Motion", prereqs=[]),
            _topic("t2", "Projectile",     prereqs=["t1"]),
        ]
        path = await svc.generate(STUDENT, SUBJECT)
        ids = [t.topic_id for t in path.topics]
        assert ids.index("t1") < ids.index("t2")

    @pytest.mark.asyncio
    async def test_sequence_order_starts_at_one(self, svc, repos):
        student_repo, topic_repo = repos
        student_repo.get_all_masteries.return_value = [_mastery("t1", 0.3)]
        topic_repo.get_by_subject.return_value = [_topic("t1", "Kinematics")]
        path = await svc.generate(STUDENT, SUBJECT)
        assert path.topics[0].sequence_order == 1

    @pytest.mark.asyncio
    async def test_cold_start_student_gets_full_path(self, svc, repos):
        student_repo, topic_repo = repos
        student_repo.get_all_masteries.return_value = []  # no history
        topic_repo.get_by_subject.return_value = [
            _topic("t1", "Topic A"), _topic("t2", "Topic B")
        ]
        path = await svc.generate(STUDENT, SUBJECT)
        assert len(path.topics) == 2

    @pytest.mark.asyncio
    async def test_explanation_contains_topic_name(self, svc, repos):
        student_repo, topic_repo = repos
        student_repo.get_all_masteries.return_value = [_mastery("t1", 0.4)]
        topic_repo.get_by_subject.return_value = [_topic("t1", "Kinematics")]
        path = await svc.generate(STUDENT, SUBJECT)
        assert "Kinematics" in path.topics[0].explanation

    @pytest.mark.asyncio
    async def test_overall_progress_calculated(self, svc, repos):
        student_repo, topic_repo = repos
        student_repo.get_all_masteries.return_value = [
            _mastery("t1", 0.9),  # mastered
            _mastery("t2", 0.3),  # weak
        ]
        topic_repo.get_by_subject.return_value = [
            _topic("t1", "A"), _topic("t2", "B")
        ]
        path = await svc.generate(STUDENT, SUBJECT)
        assert path.overall_progress == pytest.approx(0.5)
