import asyncio
import json
import re
import anthropic
from core.interfaces.content_generator import ContentGenerator
from core.models.topic import Topic
from core.exceptions import ContentGenerationError


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
        try:
            msg = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.messages.create(
                    model=self.MODEL, max_tokens=2500,
                    messages=[{"role": "user", "content": prompt}],
                ),
            )
            return msg.content[0].text
        except Exception as e:
            raise ContentGenerationError(topic.id, str(e)) from e

    async def generate_questions(self, topic: Topic, count: int) -> list[dict]:
        prompt = (
            f"Generate {count} MCQ questions for Grade {topic.grade_level} {topic.subject}: {topic.name}.\n"
            "Return JSON array only:\n"
            '[{"question":"...","options":["A)...","B)...","C)...","D)..."],'
            '"answer":"A","explanation":"...","difficulty":"easy|medium|hard"}]'
        )
        try:
            msg = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._client.messages.create(
                    model=self.MODEL, max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}],
                ),
            )
            raw = msg.content[0].text
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if not match:
                raise ContentGenerationError(topic.id, "no JSON array in response")
            return json.loads(match.group())
        except ContentGenerationError:
            raise
        except Exception as e:
            raise ContentGenerationError(topic.id, str(e)) from e
