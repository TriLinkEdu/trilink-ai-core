"""
ClaudeGenerator — uses Anthropic's tool_use to force structured JSON output.

Claude does not have a native response_schema API, but tool_use with
a strict JSON schema is the recommended pattern for guaranteed structured output.
We define a single tool "submit_questions" and force the model to call it with
the validated question list.
"""

import asyncio
import json
import anthropic
from pydantic import ValidationError

from core.interfaces.content_generator import ContentGenerator
from core.models.question_schema import MCQQuestionList
from core.models.topic import Topic
from core.exceptions import ContentGenerationError


# Tool definition passed to the Claude API for structured question generation.
# Using Anthropic's JSON Schema format (same as OpenAPI spec subset).
_QUESTIONS_TOOL = {
    "name": "submit_questions",
    "description": "Submit a list of multiple-choice questions for the student's quiz.",
    "input_schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question":    {"type": "string"},
                        "options": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string", "enum": ["A", "B", "C", "D"]},
                                    "text":  {"type": "string"},
                                },
                                "required": ["label", "text"],
                            },
                            "minItems": 4, "maxItems": 4,
                        },
                        "answer":      {"type": "string", "enum": ["A", "B", "C", "D"]},
                        "explanation": {"type": "string"},
                        "difficulty":  {"type": "string", "enum": ["easy", "medium", "hard"]},
                    },
                    "required": ["question", "options", "answer", "explanation", "difficulty"],
                },
            }
        },
        "required": ["questions"],
    },
}


class ClaudeGenerator(ContentGenerator):

    MODEL = "claude-3-haiku-20240307"

    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

    async def generate_lesson(self, topic: Topic) -> str:
        prompt = (
            f"You are an expert Ethiopian Grade {topic.grade_level} {topic.subject} teacher.\n\n"
            f"Write a comprehensive lesson for: **{topic.name}**\n"
            f"Learning objectives: {', '.join(topic.objectives)}\n\n"
            "Structure: Introduction, Key Concepts, Worked Examples, "
            f"Practice Problems, Summary. Use language suitable for Grade {topic.grade_level}. Output markdown."
        )
        return await self._call_raw(prompt)

    async def generate_questions(self, topic: Topic, count: int) -> list[dict]:
        """
        Generate MCQ questions using Claude's tool_use for guaranteed structured output.

        tool_choice={"type": "tool", "name": "submit_questions"} forces the model
        to ALWAYS call the tool — it cannot return free-form text.
        """
        try:
            resp = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._client.messages.create(
                    model=self.MODEL,
                    max_tokens=3000,
                    tools=[_QUESTIONS_TOOL],
                    tool_choice={"type": "tool", "name": "submit_questions"},
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                f"Generate exactly {count} multiple-choice questions for "
                                f"Grade {topic.grade_level} {topic.subject}: {topic.name}.\n"
                                "Vary difficulty across easy, medium, and hard.\n"
                                "Include clear explanations. Align with Ethiopian national curriculum."
                            ),
                        }
                    ],
                ),
            )

            # Extract the tool call input block
            tool_block = next(
                (b for b in resp.content if b.type == "tool_use" and b.name == "submit_questions"),
                None,
            )
            if not tool_block:
                raise ContentGenerationError(topic.id, "Claude did not call submit_questions tool")

            question_list = MCQQuestionList.model_validate(tool_block.input)
            return [q.to_dict() for q in question_list.questions]

        except ValidationError as e:
            raise ContentGenerationError(topic.id, f"Schema validation failed: {e}") from e
        except ContentGenerationError:
            raise
        except Exception as e:
            raise ContentGenerationError(topic.id, str(e)) from e

    async def _call_raw(self, prompt: str) -> str:
        try:
            msg = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._client.messages.create(
                    model=self.MODEL, max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}],
                ),
            )
            return msg.content[0].text
        except Exception as e:
            raise ContentGenerationError("chat", str(e)) from e
