from pydantic import BaseModel


class ChatRequest(BaseModel):
    student_id: str
    message: str
    grade_level: int = 9


class ChatResponse(BaseModel):
    student_id: str
    message: str
    answer: str
    sources: list[dict]
