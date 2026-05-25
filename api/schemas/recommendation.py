from pydantic import BaseModel


class RecommendRequest(BaseModel):
    student_id: str
    weak_topic_ids: list[str]
    difficulty: str = "medium"
    limit: int = 5
    subject_name: str = ""
    grade_level: int = 9


class RecommendResponse(BaseModel):
    student_id: str
    resources: list[dict]
