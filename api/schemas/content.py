from pydantic import BaseModel


class GenerateLessonRequest(BaseModel):
    topic_id: str


class GenerateLessonResponse(BaseModel):
    resource_id: str
    title: str
    topic_id: str
    content: str
    needs_review: bool
    source: str


class GenerateQuestionsRequest(BaseModel):
    topic_id: str
    count: int = 5


class GenerateQuestionsResponse(BaseModel):
    topic_id: str
    topic_name: str
    questions: list[dict]
