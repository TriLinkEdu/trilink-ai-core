from pydantic import BaseModel


class LearningPathRequest(BaseModel):
    student_id: str
    subject_id: str


class LearningPathTopicOut(BaseModel):
    topic_id: str
    topic_name: str
    current_mastery: float
    target_mastery: float
    sequence_order: int
    is_completed: bool
    explanation: str


class LearningPathResponse(BaseModel):
    student_id: str
    subject_id: str
    overall_progress: float
    topics: list[LearningPathTopicOut]
