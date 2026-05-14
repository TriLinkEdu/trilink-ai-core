"""
GroqGenerator — uses Groq's JSON mode + Pydantic validation for structured outputs.

Groq does not yet have a first-class `response_schema` API (as of 2025-05), but
supports `response_format={"type": "json_object"}` which constrains the model to
return only valid JSON. We then parse + validate the result with Pydantic, giving
us the same guarantees as native Structured Outputs without regex.
"""

import asyncio
import json
from groq import AsyncGroq, RateLimitError
from pydantic import ValidationError

from core.interfaces.content_generator import ContentGenerator
from core.models.question_schema import MCQQuestionList
from core.models.topic import Topic
from core.exceptions import ContentGenerationError


class GroqGenerator(ContentGenerator):

    MODEL     = "llama-3.3-70b-versatile"
    MAX_RETRY = 3
    BACKOFF   = 2  # seconds, doubles each retry

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
        """
        Generate MCQ questions using Groq JSON mode + Pydantic validation.

        response_format={"type": "json_object"} forces the LLM to return only
        valid JSON. We then validate against MCQQuestionList for schema correctness.
        """
        system_prompt = (
            f"You are an expert Ethiopian Grade {topic.grade_level} {topic.subject} question writer. "
            "Respond ONLY with a valid JSON object matching this exact schema:\n"
            '{"questions": [{"question": "...", "options": [{"label": "A", "text": "..."}, '
            '{"label": "B", "text": "..."}, {"label": "C", "text": "..."}, {"label": "D", "text": "..."}], '
            '"answer": "A", "explanation": "...", "difficulty": "easy|medium|hard"}]}'
        )
        user_prompt = (
            f"Generate exactly {count} multiple-choice questions for: {topic.name}.\n"
            "Vary difficulty across easy, medium, and hard.\n"
            "Include a clear explanation for the correct answer.\n"
            "Ensure questions are appropriate for the Ethiopian national curriculum."
        )

        try:
            raw_json = await self._call_json_mode(system_prompt, user_prompt, max_tokens=2500)
            data = json.loads(raw_json)
            question_list = MCQQuestionList.model_validate(data)
            return [q.to_dict() for q in question_list.questions]
        except ValidationError as e:
            raise ContentGenerationError(topic.id, f"Schema validation failed: {e}") from e
        except json.JSONDecodeError as e:
            raise ContentGenerationError(topic.id, f"JSON mode returned invalid JSON: {e}") from e

    async def _call_json_mode(
        self, system_prompt: str, user_prompt: str, max_tokens: int, temperature: float = 0.7
    ) -> str:
        """Call Groq with response_format=json_object enforced."""
        for attempt in range(self.MAX_RETRY):
            try:
                resp = await self._client.chat.completions.create(
                    model=self.MODEL,
                    messages=[
                        {"role": "system",  "content": system_prompt},
                        {"role": "user",    "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
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

    async def _call(self, prompt: str, max_tokens: int, temperature: float = 0.7) -> str:
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

    async def _call_raw(self, prompt: str) -> str:
        return await self._call(prompt, max_tokens=1000, temperature=0.7)
