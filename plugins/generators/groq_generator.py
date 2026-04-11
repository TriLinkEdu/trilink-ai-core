import asyncio
import json
import re
from groq import AsyncGroq, RateLimitError
from core.interfaces.content_generator import ContentGenerator
from core.models.topic import Topic
from core.exceptions import ContentGenerationError


class GroqGenerator(ContentGenerator):

    MODEL      = "llama-3.3-70b-versatile"
    MAX_RETRY  = 3
    BACKOFF    = 2  # seconds, doubles each retry

    def __init__(self, api_key: str):
        self._client = AsyncGroq(api_key=api_key)

    async def generate_lesson(self, topic: Topic) -> str:
        prompt = (
            f"You are an expert Ethiopian Grade {topic.grade_level} {topic.subject} teacher.\n\n"
            f"Write a comprehensive lesson for: **{topic.name}**\n"
            f"Learning objectives: {', '.join(topic.objectives)}\n\n"
            "Structure:\n"
            "1. Introduction (why this matters, Ethiopian context)\n"
            "2. Key Concepts (3-5 main ideas with clear definitions)\n"
            "3. Worked Examples (2-3 solved problems)\n"
            "4. Practice Problems (5 questions with answers)\n"
            "5. Summary\n\n"
            f"Use simple language suitable for Grade {topic.grade_level} students. Output markdown."
        )
        return await self._call(prompt, max_tokens=2500)

    async def generate_questions(self, topic: Topic, count: int) -> list[dict]:
        prompt = (
            f"Generate {count} multiple-choice questions for Grade {topic.grade_level} "
            f"{topic.subject}: {topic.name}.\n\n"
            "Return a JSON array only, no extra text:\n"
            '[{"question":"...","options":["A)...","B)...","C)...","D)..."],'
            '"answer":"A","explanation":"...","difficulty":"easy|medium|hard"}]'
        )
        raw = await self._call(prompt, max_tokens=2000, temperature=0.5)
        return self._parse_json(raw, topic.id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _call(
        self, prompt: str, max_tokens: int, temperature: float = 0.7
    ) -> str:
        for attempt in range(self.MAX_RETRY):
            try:
                resp = await self._client.chat.completions.create(
                    model=self.MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content
            except RateLimitError:
                if attempt == self.MAX_RETRY - 1:
                    raise ContentGenerationError("groq", "rate limit exceeded")
                await asyncio.sleep(self.BACKOFF ** attempt)
            except Exception as e:
                raise ContentGenerationError("groq", str(e)) from e

        raise ContentGenerationError("groq", "max retries exceeded")

    @staticmethod
    def _parse_json(raw: str, topic_id: str) -> list[dict]:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            raise ContentGenerationError(topic_id, "no JSON array in response")
        try:
            return json.loads(match.group())
        except json.JSONDecodeError as e:
            raise ContentGenerationError(topic_id, f"invalid JSON: {e}") from e
