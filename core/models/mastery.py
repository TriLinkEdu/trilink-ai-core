from dataclasses import dataclass


@dataclass
class MasteryUpdate:
    old: float
    new: float


@dataclass
class TopicMastery:
    student_id: str
    topic_id: str
    mastery_level: float  # 0.0 – 1.0
    assessment_count: int = 0
