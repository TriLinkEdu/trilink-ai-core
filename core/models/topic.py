from dataclasses import dataclass, field


@dataclass
class Topic:
    id: str
    name: str
    subject: str
    subject_id: str
    difficulty_tier: str  # easy | medium | hard
    objectives: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    parent_topic_id: str | None = None
    grade_level: int = 9          # default 9 for pilot; scales to any grade
