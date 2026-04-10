# TriLink AI Engine

Python/FastAPI AI microservice for the TriLink educational platform.

## Architecture

```
core/interfaces/     ← Immutable contracts (never change these)
core/models/         ← Pure domain models
plugins/             ← Swappable implementations
services/            ← Orchestration (depends on interfaces only)
infrastructure/      ← DB, repositories
api/                 ← FastAPI routes (thin layer)
config/              ← Settings + plugin registry (wiring)
scripts/             ← One-shot data generation scripts
tests/               ← unit / integration / contract
```

**To swap any AI model:** set one env var, zero code changes.

```
GENERATOR_PLUGIN=openai   # was groq
TRACER_PLUGIN=irt         # was bkt
EMBEDDER_PLUGIN=openai    # was minilm
```

---

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Fill in POSTGRES_URL, MONGO_URL, GROQ_API_KEY

# 2. Start infrastructure
docker-compose up postgres mongo -d

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the server
uvicorn main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### Or run everything with Docker

```bash
docker-compose up --build
```

---

## First-Time Data Setup

Run these once after the DB is up and curriculum topics are seeded:

```bash
# Generate AI lessons + questions for all 359 topics (~12 min, free)
python3 scripts/generate_content.py

# Generate and store vector embeddings for topics + resources (~5 min)
python3 scripts/generate_embeddings.py
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/ai/mastery/update` | Update topic mastery after an answer (BKT) |
| `GET`  | `/api/ai/mastery/{student_id}/{topic_id}` | Get current mastery for one topic |
| `GET`  | `/api/ai/mastery/{student_id}/weak/{subject_id}` | Get all weak topics, sorted |
| `POST` | `/api/ai/learning-path` | Generate personalized learning path |
| `POST` | `/api/ai/recommendations` | Recommend resources for weak topics |
| `POST` | `/api/ai/content/generate-lesson` | Generate AI lesson for a topic |
| `POST` | `/api/ai/content/generate-questions` | Generate MCQ questions for a topic |
| `GET`  | `/health` | Health check |

### Example: Update Mastery

```bash
curl -X POST http://localhost:8000/api/ai/mastery/update \
  -H "Content-Type: application/json" \
  -d '{"student_id":"uuid","topic_id":"uuid","is_correct":true}'
```

```json
{
  "topic_id": "uuid",
  "old_mastery": 0.45,
  "new_mastery": 0.61,
  "assessment_count": 6,
  "mastered": false
}
```

### Example: Generate Learning Path

```bash
curl -X POST http://localhost:8000/api/ai/learning-path \
  -H "Content-Type: application/json" \
  -d '{"student_id":"uuid","subject_id":"uuid"}'
```

```json
{
  "student_id": "uuid",
  "subject_id": "uuid",
  "overall_progress": 0.42,
  "topics": [
    {
      "topic_id": "uuid",
      "topic_name": "Uniform Motion",
      "current_mastery": 0.3,
      "target_mastery": 0.8,
      "sequence_order": 1,
      "is_completed": false,
      "explanation": "You scored 30% on Uniform Motion. Mastering this unlocks 2 dependent topic(s)."
    }
  ]
}
```

---

## Running Tests

```bash
# Unit tests only (no DB required)
python3 -m pytest tests/unit/ -v

# All tests (set TEST_POSTGRES_URL for integration tests)
TEST_POSTGRES_URL=postgresql://trilink:trilink@localhost:5432/trilink \
  python3 -m pytest -v
```

---

## Adding a New AI Plugin

1. Implement the interface:
```python
# plugins/generators/openai_generator.py
from core.interfaces.content_generator import ContentGenerator

class OpenAIGenerator(ContentGenerator):
    async def generate_lesson(self, topic): ...
    async def generate_questions(self, topic, count): ...
```

2. Add one `case` in `config/plugin_registry.py`:
```python
case "openai":
    from plugins.generators.openai_generator import OpenAIGenerator
    return OpenAIGenerator(api_key=settings.OPENAI_API_KEY)
```

3. Set env var:
```
GENERATOR_PLUGIN=openai
```

That's it. No other files change.

---

## BKT Parameters

Tunable via `.env`:

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `BKT_P_INIT` | `0.1` | Prior knowledge (10%) |
| `BKT_P_LEARN` | `0.3` | Learning rate per attempt |
| `BKT_P_SLIP` | `0.1` | Correct answer despite not knowing |
| `BKT_P_GUESS` | `0.25` | Wrong answer despite knowing |
| `MASTERY_THRESHOLD` | `0.70` | Topic considered mastered at 70% |

---

## Team

- **Sadam Husen** — Mobile & AI/ML
- **Nebiyu Musbah** — Backend & AI
- **Yohannes Gizachew** — Backend & AI
- **Abdulaziz Isa** — Mobile & Frontend
- **Abdallah Abdurazak** — UI/UX & Frontend

**Advisor:** Mr. Anteneh Tilaye — Adama Science and Technology University
