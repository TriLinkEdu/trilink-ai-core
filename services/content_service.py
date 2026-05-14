from core.interfaces.content_generator import ContentGenerator
from core.models.resource import Resource
from infrastructure.repositories.resource_repo import ResourceRepository
from infrastructure.repositories.topic_repo import TopicRepository
from infrastructure.repositories.question_repo import QuestionRepository
from infrastructure.repositories.mongo_repos import AuditRepository


class ContentService:

    def __init__(
        self,
        generator: ContentGenerator,
        resource_repo: ResourceRepository,
        topic_repo: TopicRepository,
        question_repo: QuestionRepository | None = None,
    ):
        self._generator = generator
        self._resources = resource_repo
        self._topics    = topic_repo
        self._questions = question_repo or QuestionRepository()
        self._audit     = AuditRepository()

    async def generate_lesson(self, topic_id: str) -> dict:
        topic   = self._topics.get_by_id(topic_id)
        content = await self._generator.generate_lesson(topic)

        resource = Resource(
            id="", title=f"Lesson: {topic.name}",
            type="lesson", topic_id=topic_id,
            difficulty=topic.difficulty_tier,
            content=content, source="ai_generated",
        )
        new_id = self._resources.save(resource)
        self._audit.log("system", "lesson_generated", "resource", new_id,
                        {"topic_id": topic_id, "topic_name": topic.name})

        return {
            "resource_id" : new_id,
            "title"       : resource.title,
            "topic_id"    : topic_id,
            "content"     : content,
            "needs_review": True,
            "source"      : "ai_generated",
        }

    async def generate_questions(self, topic_id: str, count: int = 5) -> dict:
        topic     = self._topics.get_by_id(topic_id)
        questions = await self._generator.generate_questions(topic, count)

        # Persist to question bank so NestJS can pull them into quizzes
        saved_ids = self._questions.save_batch(topic_id, questions)
        for q, qid in zip(questions, saved_ids):
            q["question_id"] = qid
        self._audit.log("system", "questions_generated", "question_bank", topic_id,
                        {"count": len(saved_ids), "topic_name": topic.name})

        return {
            "topic_id"  : topic_id,
            "topic_name": topic.name,
            "questions" : questions,
            "saved"     : len(saved_ids),
        }

    async def generate_quiz(
        self,
        subject: str,
        grade_level: int,
        topics: list[str],
        count: int = 5,
        difficulty: str = "medium",
    ) -> dict:
        """
        Real-time, ephemeral quiz generation for the gamification hub.

        Builds a temporary Topic from curriculum context (no DB lookup required),
        generates fresh MCQ questions via the LLM, normalises them defensively,
        and returns immediately.  Nothing is persisted — the answer key lives only
        in the NestJS response that re-wraps these questions for the mobile client.
        """
        import hashlib, time

        # Construct a rich topic description from the provided curriculum context
        if topics:
            # Use all topic names to build context, focus prompt on the first few
            focus_topics  = topics[:3]
            topic_context = ", ".join(focus_topics)
            topic_name    = f"{', '.join(focus_topics[:2])} and related concepts"
        else:
            topic_context = subject
            topic_name    = subject

        # Build a synthetic Topic dataclass so all generators work unchanged
        from core.models.topic import Topic
        synthetic_topic = Topic(
            id              = f"quiz-live-{subject.lower().replace(' ', '-')}-g{grade_level}",
            name            = topic_name,
            subject         = subject,
            subject_id      = "",
            difficulty_tier = difficulty,
            objectives      = [f"Test understanding of {t}" for t in (topics[:3] if topics else [subject])],
            keywords        = topics[:5] if topics else [],
            grade_level     = grade_level,
        )

        # Generate via LLM — let exceptions propagate so NestJS can fall back
        raw_questions = await self._generator.generate_questions(synthetic_topic, count)

        # ── Defensive normalisation ───────────────────────────────────────────
        # The LLM may return "A", "A)", "Option A", or an integer for the answer.
        # We normalise all of them into a zero-based correctIndex integer.
        normalised: list[dict] = []
        for idx, q in enumerate(raw_questions):
            question_text = str(q.get("question") or q.get("stem") or q.get("text") or "").strip()
            if not question_text:
                continue

            options_raw: list = q.get("options") or []
            options: list[str] = []
            for opt in options_raw:
                if isinstance(opt, str):
                    # Strip leading "A) ", "A. ", "a) " labels if present
                    cleaned = opt.strip()
                    if len(cleaned) >= 3 and cleaned[1] in ")." and cleaned[0].isalpha():
                        cleaned = cleaned[2:].strip()
                    options.append(cleaned)
                else:
                    options.append(str(opt).strip())

            if len(options) < 2:
                continue

            # Resolve correct answer to a zero-based index
            answer_raw = q.get("answer") or q.get("answer_key") or q.get("correctIndex") or 0
            correct_index = 0
            if isinstance(answer_raw, int):
                correct_index = answer_raw
            elif isinstance(answer_raw, str):
                a = answer_raw.strip()
                # Handle "A", "A)", "Option A"
                if a and a[0].upper() in "ABCDE" and (len(a) == 1 or a[1] in ") ."):
                    correct_index = ord(a[0].upper()) - ord("A")
                else:
                    # Try matching exact text
                    try:
                        correct_index = int(a)
                    except ValueError:
                        match = next(
                            (i for i, o in enumerate(options) if o.strip().lower() == a.lower()),
                            0,
                        )
                        correct_index = match

            if correct_index < 0 or correct_index >= len(options):
                correct_index = 0

            # Deterministic stable ID: hash of (subject + grade + question text)
            stable_id = "qz-" + hashlib.md5(
                f"{subject}:{grade_level}:{question_text}".encode()
            ).hexdigest()[:12]

            normalised.append({
                "id"           : stable_id,
                "text"         : question_text,
                "options"      : options,
                "correctIndex" : correct_index,
                "explanation"  : str(q.get("explanation") or "").strip(),
                "difficulty"   : str(q.get("difficulty") or difficulty),
                "type"         : "multipleChoice",
                "pointValue"   : 1,
                "topicHint"    : topic_context,
            })

        return {
            "subject"     : subject,
            "grade_level" : grade_level,
            "topics_used" : topics[:3] if topics else [],
            "questions"   : normalised,
            "generated"   : len(normalised),
        }
