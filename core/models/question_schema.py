"""
Canonical Pydantic schemas for LLM-generated quiz questions.

These schemas are passed directly to LLM APIs as response_schema / tool definitions
to guarantee Structured Output. No regex parsing required anywhere in the codebase.
"""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class MCQOption(BaseModel):
    """A single answer option. Label must be A, B, C, or D."""
    label: Literal["A", "B", "C", "D"]
    text: str = Field(min_length=1)


class MCQQuestion(BaseModel):
    """A single multiple-choice quiz question with a validated answer key."""
    question: str = Field(min_length=10, description="The question text")
    options: list[MCQOption] = Field(min_length=4, max_length=4)
    answer: Literal["A", "B", "C", "D"] = Field(
        description="The label of the correct answer option"
    )
    explanation: str = Field(
        min_length=5,
        description="A clear explanation of why this answer is correct"
    )
    difficulty: Literal["easy", "medium", "hard"]

    def to_dict(self) -> dict:
        """Serialise to the legacy dict format expected by the rest of the system."""
        return {
            "question"    : self.question,
            "options"     : [f"{o.label}) {o.text}" for o in self.options],
            "answer"      : self.answer,
            "explanation" : self.explanation,
            "difficulty"  : self.difficulty,
        }


class MCQQuestionList(BaseModel):
    """Container returned by all Structured Output API calls."""
    questions: list[MCQQuestion]
