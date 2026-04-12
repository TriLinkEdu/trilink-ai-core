from pydantic import BaseModel


class ChatRequest(BaseModel):
    student_id: str
    message: str


class ChatResponse(BaseModel):
    student_id: str
    message: str
    answer: str
    sources: list[dict]
