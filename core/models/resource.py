from dataclasses import dataclass


@dataclass
class Resource:
    id: str
    title: str
    type: str           # lesson | youtube_video | pdf | flashcard
    topic_id: str
    difficulty: str     # easy | medium | hard
    content: str = ""   # markdown for lessons
    url: str = ""       # for videos/links
    relevance_score: float = 0.0
    avg_rating: float = 0.0
    source: str = "manual"  # manual | ai_generated
