import asyncio
import json
import os
import re
from google import genai
from google.oauth2 import service_account
from core.interfaces.content_generator import ContentGenerator
from core.models.topic import Topic
from core.exceptions import ContentGenerationError


class GeminiGenerator(ContentGenerator):

    MODEL = "gemini-2.5-flash"

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
            resp = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._client.models.generate_content(
                    model=self.MODEL, contents=prompt
                ),
            )
            return resp.text
        except Exception as e:
            raise ContentGenerationError("chat", str(e)) from e
