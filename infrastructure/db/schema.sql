-- TriLink AI Engine — PostgreSQL Schema
-- Run once against a fresh database.
-- Requires: pgvector extension

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";     -- pgvector

-- -----------------------------------------------------------------------
-- Subjects
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subject (
    subject_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_name    VARCHAR(60)  NOT NULL,
    subject_code    VARCHAR(10)  NOT NULL UNIQUE,
    grade_level     SMALLINT     NOT NULL DEFAULT 9 CHECK (grade_level BETWEEN 1 AND 12),
    UNIQUE (subject_name, grade_level)
);

-- -----------------------------------------------------------------------
-- Topics  (self-referential hierarchy: chapter → topic → subtopic)
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS topic (
    topic_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id        UUID NOT NULL REFERENCES subject(subject_id) ON DELETE CASCADE,
    parent_topic_id   UUID REFERENCES topic(topic_id) ON DELETE SET NULL,
    topic_name        VARCHAR(100) NOT NULL,
    topic_code        VARCHAR(20)  NOT NULL UNIQUE,
    difficulty_tier   VARCHAR(10)  NOT NULL CHECK (difficulty_tier IN ('easy','medium','hard')),
    objectives        TEXT[]       NOT NULL DEFAULT '{}',
    keywords          TEXT[]       NOT NULL DEFAULT '{}',
    embedding         vector(384),                          -- all-MiniLM-L6-v2
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_topic_subject   ON topic(subject_id);
CREATE INDEX IF NOT EXISTS idx_topic_parent    ON topic(parent_topic_id);
CREATE INDEX IF NOT EXISTS idx_topic_embedding ON topic USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 20);

-- -----------------------------------------------------------------------
-- Topic prerequisites  (many-to-many)
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS topic_prerequisite (
    topic_id      UUID NOT NULL REFERENCES topic(topic_id) ON DELETE CASCADE,
    prereq_id     UUID NOT NULL REFERENCES topic(topic_id) ON DELETE CASCADE,
    PRIMARY KEY (topic_id, prereq_id)
);

-- -----------------------------------------------------------------------
-- Users  (base table — profiles live in separate tables)
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "user" (
    user_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(254) NOT NULL UNIQUE,
    password_hash CHAR(60)     NOT NULL,
    role          VARCHAR(10)  NOT NULL CHECK (role IN ('student','teacher','parent','admin')),
    first_name    VARCHAR(60)  NOT NULL,
    last_name     VARCHAR(60)  NOT NULL,
    status        VARCHAR(10)  NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------
-- Student profile
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_profile (
    student_id            UUID PRIMARY KEY REFERENCES "user"(user_id) ON DELETE CASCADE,
    grade_level           SMALLINT NOT NULL CHECK (grade_level BETWEEN 1 AND 12),
    section               VARCHAR(10) NOT NULL,
    offline_cache_enabled BOOLEAN NOT NULL DEFAULT FALSE
);

-- -----------------------------------------------------------------------
-- Student topic mastery  (BKT output — one row per student × topic)
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS student_topic_mastery (
    student_id        UUID NOT NULL REFERENCES student_profile(student_id) ON DELETE CASCADE,
    topic_id          UUID NOT NULL REFERENCES topic(topic_id) ON DELETE CASCADE,
    mastery_level     DECIMAL(6,5) NOT NULL DEFAULT 0.1 CHECK (mastery_level BETWEEN 0 AND 1),
    assessment_count  INTEGER      NOT NULL DEFAULT 0,
    last_assessed     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (student_id, topic_id)
);

CREATE INDEX IF NOT EXISTS idx_mastery_student ON student_topic_mastery(student_id);

-- -----------------------------------------------------------------------
-- AI learning path  (one per student — replaced on each generation)
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ai_learning_path (
    path_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id       UUID NOT NULL UNIQUE REFERENCES student_profile(student_id) ON DELETE CASCADE,
    subject_id       UUID NOT NULL REFERENCES subject(subject_id),
    overall_progress DECIMAL(6,5) NOT NULL DEFAULT 0 CHECK (overall_progress BETWEEN 0 AND 1),
    last_updated     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS learning_path_topic (
    path_id        UUID NOT NULL REFERENCES ai_learning_path(path_id) ON DELETE CASCADE,
    topic_id       UUID NOT NULL REFERENCES topic(topic_id) ON DELETE CASCADE,
    sequence_order INTEGER      NOT NULL,
    target_mastery DECIMAL(6,5) NOT NULL DEFAULT 0.8,
    is_completed   BOOLEAN      NOT NULL DEFAULT FALSE,
    PRIMARY KEY (path_id, topic_id)
);

-- -----------------------------------------------------------------------
-- Question Bank
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS question_bank (
    question_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id        UUID NOT NULL REFERENCES topic(topic_id) ON DELETE CASCADE,
    question_text   TEXT         NOT NULL,
    options         JSONB        NOT NULL,          -- ["A) ...", "B) ...", ...]
    correct_answer  VARCHAR(1)   NOT NULL,          -- "A" | "B" | "C" | "D"
    explanation     TEXT         NOT NULL DEFAULT '',
    difficulty      VARCHAR(10)  NOT NULL CHECK (difficulty IN ('easy','medium','hard')),
    source          VARCHAR(20)  NOT NULL DEFAULT 'ai_generated',
    needs_review    BOOLEAN      NOT NULL DEFAULT TRUE,
    embedding       vector(384),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_question_topic ON question_bank(topic_id);
CREATE INDEX IF NOT EXISTS idx_question_difficulty ON question_bank(topic_id, difficulty);

-- -----------------------------------------------------------------------
-- Resources
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS resource (
    resource_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id     UUID NOT NULL REFERENCES topic(topic_id) ON DELETE CASCADE,
    title        VARCHAR(200) NOT NULL,
    type         VARCHAR(20)  NOT NULL CHECK (type IN ('lesson','youtube_video','pdf','flashcard')),
    content      TEXT         NOT NULL DEFAULT '',   -- markdown for lessons
    url          TEXT         NOT NULL DEFAULT '',   -- for videos/links
    difficulty   VARCHAR(10)  NOT NULL CHECK (difficulty IN ('easy','medium','hard')),
    source       VARCHAR(20)  NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','ai_generated')),
    needs_review BOOLEAN      NOT NULL DEFAULT FALSE,
    avg_rating   DECIMAL(3,2) NOT NULL DEFAULT 0,
    embedding    vector(384),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resource_topic     ON resource(topic_id);
CREATE INDEX IF NOT EXISTS idx_resource_embedding ON resource USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 20);
