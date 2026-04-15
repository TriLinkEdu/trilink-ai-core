# TriLink AI Engine — Integration Guide

> For the NestJS backend team. Everything you need to integrate the AI engine into the TriLink platform.

---

## Overview

The AI engine is a standalone Python/FastAPI service that runs alongside the NestJS backend. NestJS is the only consumer — Flutter never calls the AI engine directly.

```
Flutter App
    ↕
NestJS Backend (:4000)   ← you are here
    ↕
AI Engine (:8000)        ← this document
    ↕
PostgreSQL (Neon) + MongoDB Atlas
```

---

## Quick Start

### 1. Environment

```bash
cd ai-engine
cp .env.example .env
# Fill in the required values (see Environment Variables below)
pip install -r requirements.txt
```

### 2. Run

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Verify

```bash
curl http://localhost:8000/health
# → {"status": "ok"}
```

### 4. Swagger UI

```
http://localhost:8000/docs
```

All endpoints are interactive and testable from the browser.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `POSTGRES_URL` | ✅ | Neon PostgreSQL connection string |
| `MONGO_URL` | ✅ | MongoDB Atlas connection string |
| `INTERNAL_API_KEY` | ✅ | Shared secret — NestJS sends this in every request |
| `GENERATOR_PLUGIN` | ✅ | `gemini` (current) or `groq`, `openai`, `claude` |
| `GEMINI_API_KEY` | ✅ | Gemini API key (used for content generation + chat) |
| `YOUTUBE_API_KEY` | ✅ | YouTube Data API v3 key (for live video recommendations) |
| `GROQ_API_KEY` | optional | Fallback generator |
| `OPENAI_API_KEY` | optional | Fallback generator |
| `CLAUDE_API_KEY` | optional | Fallback generator |

---

## Authentication

Every request (except `/health`) must include:

```
X-API-Key: <INTERNAL_API_KEY>
```

Set the same value in both NestJS and AI engine `.env` files.

```typescript
// NestJS axios config
const AI_ENGINE = axios.create({
  baseURL: process.env.AI_ENGINE_URL, // http://localhost:8000
  headers: { 'X-API-Key': process.env.INTERNAL_API_KEY },
});
```

---

## Full API Reference

### Health

```
GET /health
```
No auth. Returns `{"status": "ok"}`. Use for Docker health checks.

---

### Mastery

#### Update mastery after a quiz answer
```
POST /api/ai/mastery/update
```
Call this after **every single answer** a student submits. BKT updates the mastery score in real time.

```json
// Request
{
  "student_id": "uuid",
  "topic_id": "uuid",
  "is_correct": true
}

// Response
{
  "topic_id": "uuid",
  "old_mastery": 0.45,
  "new_mastery": 0.61,
  "assessment_count": 6,
  "mastered": false
}
```

`mastered: true` when mastery ≥ 0.70. Use this to trigger XP awards and move to the next topic.

---

#### Get topic mastery
```
GET /api/ai/mastery/{student_id}/{topic_id}
```
```json
{
  "topic_id": "uuid",
  "mastery_level": 0.61,
  "assessment_count": 6,
  "mastered": false
}
```

---

#### Get weak topics for a subject
```
GET /api/ai/mastery/{student_id}/weak/{subject_id}
```
Returns all topics below 70% mastery, sorted lowest first. Use to build the learning path and recommendations.

```json
{
  "student_id": "uuid",
  "subject_id": "uuid",
  "weak_topics": [
    { "topic_id": "uuid", "mastery_level": 0.2, "assessment_count": 3 },
    { "topic_id": "uuid", "mastery_level": 0.45, "assessment_count": 6 }
  ]
}
```

---

### Adaptive Quiz

#### Get next question (adaptive difficulty)
```
GET /api/ai/content/next-question/{student_id}/{topic_id}
```
Returns one question at the right difficulty based on the student's current mastery.

```
mastery < 0.4  → easy question
mastery 0.4–0.7 → medium question
mastery > 0.7  → hard question
```

```json
{
  "topic_id": "uuid",
  "current_mastery": 0.35,
  "selected_difficulty": "easy",
  "question": {
    "question_id": "uuid",
    "question": "What does Newton's 2nd Law state?",
    "options": ["A) F=ma", "B) F=mv", "C) F=m/a", "D) F=m+a"],
    "answer": "A",
    "explanation": "Force equals mass times acceleration.",
    "difficulty": "easy"
  }
}
```

#### Get questions for a topic (bulk)
```
GET /api/ai/content/questions/{topic_id}?difficulty=medium&limit=10
```
Use this to build a fixed quiz (non-adaptive). Returns up to `limit` questions.

---

### Learning Path

```
POST /api/ai/learning-path
```
Generates a personalized, prerequisite-ordered study plan. Call after quiz submission or on dashboard load.

```json
// Request
{ "student_id": "uuid", "subject_id": "uuid" }

// Response
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
      "explanation": "You scored 30% on Uniform Motion. Mastering this unlocks 2 dependent topics."
    }
  ]
}
```

---

### Recommendations

```
POST /api/ai/recommendations
```
Returns a mix of AI lessons, open books (OpenStax, CK-12, Khan Academy), and live YouTube videos matched to the student's weak topics.

```json
// Request
{
  "student_id": "uuid",
  "weak_topic_ids": ["uuid1", "uuid2"],
  "difficulty": "medium",
  "limit": 5
}

// Response
{
  "student_id": "uuid",
  "resources": [
    {
      "resource_id": "uuid",
      "title": "Lesson: Newton's Laws",
      "type": "lesson",
      "topic_id": "uuid",
      "difficulty": "medium",
      "content": "# Newton's Laws\n\n...",
      "url": "",
      "relevance_score": 0.92,
      "source": "ai_generated"
    },
    {
      "resource_id": "uuid",
      "title": "OpenStax College Physics",
      "type": "book",
      "topic_id": "uuid",
      "difficulty": "medium",
      "content": "",
      "url": "https://openstax.org/books/college-physics-2e/...",
      "relevance_score": 0.85,
      "source": "open_library"
    },
    {
      "resource_id": "yt-hLExLsKKZDI",
      "title": "Grade 9 Physics: Newton's Laws of Motion",
      "type": "youtube_video",
      "topic_id": null,
      "difficulty": "medium",
      "content": "",
      "url": "https://www.youtube.com/watch?v=hLExLsKKZDI",
      "relevance_score": 0.8,
      "source": "youtube"
    }
  ]
}
```

**Resource types:** `lesson` | `book` | `youtube_video`

---

### AI Chat (RAG Tutor)

```
POST /api/ai/chat
```
Student asks a question. The AI answers grounded in the actual Ethiopian Grade 9 textbook content.

```json
// Request
{
  "student_id": "uuid",
  "message": "trigonometry is giving me a headache",
  "grade_level": 9
}

// Response
{
  "student_id": "uuid",
  "message": "trigonometry is giving me a headache",
  "answer": "Selam! Trigonometry can feel tricky at first...",
  "sources": [
    { "title": "Lesson: Introduction to Trigonometry", "topic_id": "uuid" },
    { "title": "Lesson: Trigonometric Ratios", "topic_id": "uuid" }
  ]
}
```

`grade_level` defaults to `9`. Pass the student's actual grade when available.

#### Get chat history
```
GET /api/ai/chat/history/{student_id}?limit=20
```

---

### Analytics

#### Parent: weekly progress summary
```
GET /api/ai/analytics/student/{student_id}/weekly-summary
```
```json
{
  "student_id": "uuid",
  "overall_mastery": 0.64,
  "topics_mastered": 4,
  "topics_assessed": 6,
  "active_topics_this_week": 3,
  "subjects": [
    { "subject": "Physics", "avg_mastery": 0.80, "topics_assessed": 3, "topics_mastered": 3 },
    { "subject": "Biology", "avg_mastery": 0.45, "topics_assessed": 3, "topics_mastered": 1 }
  ],
  "summary": "Great progress this week! Ahmed has mastered 4 out of 6 topics..."
}
```

#### Teacher: at-risk students
```
GET /api/ai/analytics/subject/{subject_id}/at-risk?limit=50&offset=0
```
```json
{
  "subject_id": "uuid",
  "high_risk_count": 2,
  "medium_risk_count": 5,
  "high_risk": [
    {
      "student_id": "uuid",
      "name": "Sara Bekele",
      "avg_mastery": 0.18,
      "topics_assessed": 4,
      "critical_topics": 3,
      "last_active": "2026-04-10T00:00:00",
      "risk_level": "HIGH"
    }
  ],
  "medium_risk": [...],
  "recommendations": [
    "Schedule 1-on-1 sessions for 2 high-risk student(s).",
    "1 student(s) have never attempted a quiz — contact parents."
  ]
}
```

Risk levels: `HIGH` = avg mastery < 40%, `MEDIUM` = avg mastery < 60%.

#### Teacher: class performance
```
GET /api/ai/analytics/subject/{subject_id}/class-performance?limit=50&offset=0
```
```json
{
  "subject_id": "uuid",
  "overall_avg_mastery": 0.55,
  "total_students": 32,
  "weak_topics": [
    { "topic_name": "Kinematics", "avg_mastery": 0.28, "students_assessed": 30, "status": "weak" }
  ],
  "strong_topics": [
    { "topic_name": "Newton's Laws", "avg_mastery": 0.82, "students_assessed": 30, "status": "strong" }
  ],
  "all_topics": [...]
}
```

---

## Recommended NestJS Integration Flow

### Student takes an adaptive quiz

```typescript
// 1. Get next question
const { question, selected_difficulty } = await aiEngine.get(
  `/api/ai/content/next-question/${studentId}/${topicId}`
);

// 2. Student answers — update mastery
const { new_mastery, mastered } = await aiEngine.post('/api/ai/mastery/update', {
  student_id: studentId,
  topic_id: topicId,
  is_correct: studentAnswer === question.answer,
});

// 3. Award XP in NestJS based on mastery delta
// 4. If mastered → move to next topic in learning path
// 5. Repeat from step 1
```

### Student opens AI assistant

```typescript
// Learning path
const path = await aiEngine.post('/api/ai/learning-path', {
  student_id: studentId,
  subject_id: subjectId,
});

// Recommendations (pass weak topic IDs from path)
const weakIds = path.topics.filter(t => !t.is_completed).map(t => t.topic_id);
const resources = await aiEngine.post('/api/ai/recommendations', {
  student_id: studentId,
  weak_topic_ids: weakIds.slice(0, 3),
  difficulty: 'medium',
  limit: 5,
});

// Chat
const reply = await aiEngine.post('/api/ai/chat', {
  student_id: studentId,
  message: userMessage,
  grade_level: student.gradeLevel,
});
```

### Parent views weekly report

```typescript
const report = await aiEngine.get(
  `/api/ai/analytics/student/${studentId}/weekly-summary`
);
// report.summary is a ready-to-display AI-generated sentence
```

### Teacher views at-risk students

```typescript
const atRisk = await aiEngine.get(
  `/api/ai/analytics/subject/${subjectId}/at-risk?limit=50`
);
// atRisk.high_risk → show alert banner
// atRisk.recommendations → show action items
```

---

## Data You Need to Pass

The AI engine uses UUIDs from the shared PostgreSQL database. NestJS must pass:

| Field | Where to get it |
|---|---|
| `student_id` | `user.user_id` from auth token |
| `topic_id` | `topic.topic_id` from curriculum tables |
| `subject_id` | `subject.subject_id` from curriculum tables |
| `grade_level` | `student_profile.grade_level` |

The curriculum tables (`subject`, `topic`, `question_bank`) are in the same Neon PostgreSQL database that NestJS uses. No duplication needed.

---

## Error Handling

All errors follow standard HTTP codes:

| Code | Meaning |
|---|---|
| `400` | Invalid input (e.g. injection attempt in chat message) |
| `401` | Missing or wrong `X-API-Key` |
| `404` | Topic/student not found |
| `422` | Missing required field |
| `500` | Internal error (LLM failure, DB issue) |

```typescript
try {
  const result = await aiEngine.post('/api/ai/mastery/update', body);
} catch (err) {
  if (err.response?.status === 404) {
    // Topic not found — check topic_id
  }
  // Log and continue — AI failures should never block the student
}
```

**Important:** AI engine failures should be non-blocking. If the AI engine is down, students should still be able to use the core app (exams, attendance, etc.).

---

## Database — Shared Tables

These tables are in the shared Neon PostgreSQL. Both NestJS and the AI engine read/write them:

| Table | Owner | NestJS reads |
|---|---|---|
| `subject` | AI engine seeds | subject_id, subject_name |
| `topic` | AI engine seeds | topic_id, topic_name, subject_id |
| `question_bank` | AI engine seeds | Pull questions for quizzes |
| `student_topic_mastery` | AI engine writes | Read for dashboards |
| `resource` | AI engine seeds | Show lessons/books to students |
| `ai_learning_path` | AI engine writes | Show path to students |

MongoDB (`trilink` database) is used exclusively by the AI engine for chat logs and audit trail. NestJS does not need to touch it.

---

## Current Data

| | Count |
|---|---|
| Subjects | 5 (Biology, Chemistry, History, Mathematics, Physics) |
| Topics | 212 |
| AI lessons | 218 |
| Open books | 636 (OpenStax, CK-12, Khan Academy) |
| MCQ questions | 1,060 |
| Embeddings | 854 resources + 212 topics |

All Grade 9 Ethiopian curriculum. Content is in English.
