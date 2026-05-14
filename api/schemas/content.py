from pydantic import BaseModel, Field


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
    saved: int


# ── Real-time gamification quiz generation ────────────────────────────────────

class GenerateQuizRequest(BaseModel):
    """
    Sent by NestJS when a student taps a quiz card.
    No database IDs required — uses curriculum context directly.
    """
    subject: str = Field(..., description="Subject name, e.g. 'Mathematics'")
    grade_level: int = Field(9, ge=1, le=12, description="Student's grade (1-12)")
    topics: list[str] = Field(
        default_factory=list,
        description="Topic names from the student's current curriculum (ordered by syllabus position)",
    )
    count: int = Field(5, ge=3, le=10, description="Number of MCQ questions to generate")
    difficulty: str = Field("medium", description="easy | medium | hard")


class GenerateQuizResponse(BaseModel):
    """
    Returned immediately to NestJS — questions are ephemeral, not persisted.
    NestJS re-sends the questions to the mobile client without storing them;
    the answer key is held server-side for scoring.
    """
    subject: str
    grade_level: int
    topics_used: list[str]
    questions: list[dict]
    generated: int
