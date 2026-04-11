import json
import re
import google.generativeai as genai
from core.interfaces.content_generator import ContentGenerator
from core.models.topic import Topic
from core.exceptions import ContentGenerationError


class GeminiGenerator(ContentGenerator):

    MODEL = "gemini-1.5-flash"  # free tier

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(self.MODEL)

    async def generate_lesson(self, topic: Topic) -> str:
        prompt = (
            f"You are an expert Ethiopian Grade {topic.grade_level} {topic.subject} teacher.\n\n"
            f"Write a comprehensive lesson for: **{topic.name}**\n"
            f"Learning objectives: {', '.join(topic.objectives)}\n\n"
            "Structure: Introduction, Key Concepts, Worked Examples, "
            f"Practice Problems, Summary. Use language suitable for Grade {topic.grade_level}. Output markdown."
        )
        try:
            resp = self._model.generate_content(prompt)
            return resp.text
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
            resp = self._model.generate_content(prompt)
            match = re.search(r"\[.*\]", resp.text, re.DOTALL)
            if not match:
                raise ContentGenerationError(topic.id, "no JSON array in response")
            return json.loads(match.group())
        except ContentGenerationError:
            raise
        except Exception as e:
            raise ContentGenerationError(topic.id, str(e)) from e
