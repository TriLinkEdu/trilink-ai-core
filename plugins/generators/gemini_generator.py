"""
GeminiGenerator — uses native Structured Outputs (response_schema) to guarantee
that generate_questions() always returns perfectly valid, schema-enforced JSON.
No regex parsing. No fallback hacks.
"""

import asyncio
import os

import google.generativeai as genai
from google.oauth2 import service_account

from core.exceptions import ContentGenerationError
from core.interfaces.content_generator import ContentGenerator
from core.models.question_schema import MCQQuestion, MCQQuestionList
from core.models.topic import Topic


class GeminiGenerator(ContentGenerator):

    MODEL = "gemini-2.0-flash"

    def __init__(self, api_key: str):
        gcp_key = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "gcp-key.json"
        )
        if os.path.exists(gcp_key):
            creds = service_account.Credentials.from_service_account_file(
                gcp_key, scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            self._client = genai.Client(
                vertexai=True,
                project="gen-lang-client-0611252551",
                location="us-central1",
                credentials=creds,
            )
        else:
            self._client = genai.Client(api_key=api_key)

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
        Generate MCQ questions using Gemini's native Structured Output.

        response_schema enforces the exact Pydantic shape at the API level —
        the model CANNOT return malformed JSON.
        """
        prompt = (
            f"Generate exactly {count} high-quality multiple-choice questions "
            f"for Grade {topic.grade_level} {topic.subject}: {topic.name}.\n"
            "Each question must have exactly 4 options labelled A, B, C, D.\n"
            "Vary difficulty across easy, medium, and hard.\n"
            "Include a clear explanation for the correct answer.\n"
            "Ensure questions are appropriate for the Ethiopian national curriculum."
        )

        try:
            resp = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._client.models.generate_content(
                    model=self.MODEL,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=MCQQuestionList,
                        temperature=0.7,
                    ),
                ),
            )
            # Gemini returns a fully validated Pydantic object when response_schema is set
            question_list: MCQQuestionList = resp.parsed
            return [q.to_dict() for q in question_list.questions]

        except Exception as e:
            raise ContentGenerationError(topic.id, f"Structured Output failed: {e}") from e

    async def _call_raw(self, prompt: str) -> str:
        try:
            resp = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._client.models.generate_content(
                    model=self.MODEL, contents=prompt
                ),
            )
            return resp.text
        except Exception as e:
            raise ContentGenerationError("chat", str(e)) from e
