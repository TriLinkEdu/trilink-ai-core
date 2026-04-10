from dataclasses import dataclass, field


@dataclass
class LearningPathTopic:
    topic_id: str
    topic_name: str
    current_mastery: float
    target_mastery: float
    sequence_order: int
    is_completed: bool = False
    explanation: str = ""


@dataclass
class LearningPath:
    student_id: str
    subject_id: str
    topics: list[LearningPathTopic] = field(default_factory=list)
    overall_progress: float = 0.0
