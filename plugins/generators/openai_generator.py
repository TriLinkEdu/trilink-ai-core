"""
OpenAIGenerator — uses OpenAI's native JSON mode + response_format to guarantee
structured, schema-validated question output. No regex. No fallback hacks.
"""

from openai import AsyncOpenAI
from core.interfaces.content_generator import ContentGenerator
from core.models.question_schema import MCQQuestionList
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
        """
        Generate MCQ questions using OpenAI's Structured Outputs (parse method).

        openai>=1.40 supports response_format with Pydantic models directly,
        guaranteeing schema-validated JSON at the API boundary.
        """
        try:
            resp = await self._client.beta.chat.completions.parse(
                model=self.MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            f"You are an expert Ethiopian Grade {topic.grade_level} "
                            f"{topic.subject} question writer. "
                            "Generate questions strictly aligned with the Ethiopian national curriculum."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Generate exactly {count} multiple-choice questions for: {topic.name}.\n"
                            "Each question must have exactly 4 options labelled A, B, C, D.\n"
                            "Vary difficulty across easy, medium, and hard.\n"
                            "Include a clear explanation for the correct answer."
                        ),
                    },
                ],
                response_format=MCQQuestionList,
                max_tokens=2500,
                temperature=0.7,
            )
            question_list: MCQQuestionList = resp.choices[0].message.parsed
            return [q.to_dict() for q in question_list.questions]

        except Exception as e:
            raise ContentGenerationError(topic.id, f"Structured Output failed: {e}") from e

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
