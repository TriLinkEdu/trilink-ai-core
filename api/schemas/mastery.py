from pydantic import BaseModel, Field


class MasteryUpdateRequest(BaseModel):
    student_id: str
    topic_id: str
    is_correct: bool


class MasteryUpdateResponse(BaseModel):
    topic_id: str
    old_mastery: float
    new_mastery: float
    assessment_count: int
    mastered: bool


class MasteryGetResponse(BaseModel):
    topic_id: str
    mastery_level: float
    assessment_count: int
    mastered: bool


class WeakTopicsResponse(BaseModel):
    student_id: str
    subject_id: str
    weak_topics: list[dict]
