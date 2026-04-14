import json
import re
from openai import AsyncOpenAI
from core.interfaces.content_generator import ContentGenerator
from core.models.topic import Topic
from core.exceptions import ContentGenerationError


class OpenAIGenerator(ContentGenerator):

    MODEL = "gpt-4o-mini"

    def __init__(self, api_key: str):
        self._client = AsyncOpenAI(api_key=api_key)

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
        prompt = (
            f"Generate {count} MCQ questions for Grade {topic.grade_level} {topic.subject}: {topic.name}.\n"
            "Return JSON array only:\n"
            '[{"question":"...","options":["A)...","B)...","C)...","D)..."],'
            '"answer":"A","explanation":"...","difficulty":"easy|medium|hard"}]'
        )
        raw = await self._call_raw(prompt)
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            raise ContentGenerationError(topic.id, "no JSON array in response")
        try:
            return json.loads(match.group())
        except json.JSONDecodeError as e:
            raise ContentGenerationError(topic.id, f"invalid JSON: {e}") from e

    async def _call_raw(self, prompt: str) -> str:
        try:
            resp = await self._client.chat.completions.create(
                model=self.MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2000,
            )
            return resp.choices[0].message.content
        except Exception as e:
            raise ContentGenerationError("chat", str(e)) from e
