"""
Textbook ingestion pipeline.

Usage:
    python3 scripts/ingest_textbook.py --pdf data/textbooks/math_grade9.pdf --subject "Mathematics" --grade 9
    python3 scripts/ingest_textbook.py --pdf data/textbooks/physics_grade9.pdf --subject "Physics" --grade 9

What it does:
    1. Extracts text from PDF using pdfplumber
    2. Detects chapters and topics from the table of contents
    3. Seeds subject + topics into PostgreSQL
    4. Stores raw textbook content per topic
    5. Generates embeddings for all topics
    6. Generates AI lessons + questions grounded in textbook content

Place your PDF files in: data/textbooks/
"""
import sys
import os
import re
import uuid
import asyncio
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pdfplumber
import psycopg2
from config.settings import Settings
from infrastructure.db.postgres import init_pool, connection
from plugins.embedders.minilm_embedder import MiniLMEmbedder
from plugins.generators.groq_generator import GroqGenerator


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def extract_text_by_page(pdf_path: str) -> list[dict]:
    """Extract text from each page with page numbers."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append({"page": i, "text": text.strip()})
    return pages


def detect_toc(pages: list[dict]) -> list[dict]:
    """
    Detect table of contents entries.
    Looks for patterns like:
      'Chapter 1: Number Systems .... 1'
      '1.1 Natural Numbers ............. 5'
    Returns list of {title, page_hint, level}
    """
    toc_entries = []
    # Search first 20 pages for TOC
    toc_text = " ".join(p["text"] for p in pages[:20])

    # Chapter pattern
    chapter_pattern = re.compile(
        r'(?:Chapter|CHAPTER|Unit|UNIT)\s+(\d+)[:\s]+([A-Za-z][^\n\.]{3,60})',
        re.MULTILINE
    )
    for m in chapter_pattern.finditer(toc_text):
        toc_entries.append({
            "level": 1,
            "number": m.group(1),
            "title": m.group(2).strip(),
        })

    # Section pattern (1.1, 2.3, etc.)
    section_pattern = re.compile(
        r'(\d+\.\d+)\s+([A-Za-z][^\n\.]{3,60})',
        re.MULTILINE
    )
    for m in section_pattern.finditer(toc_text):
        toc_entries.append({
            "level": 2,
            "number": m.group(1),
            "title": m.group(2).strip(),
        })

    return toc_entries


def chunk_by_topic(pages: list[dict], toc_entries: list[dict]) -> list[dict]:
    """
    Split full text into chunks per topic.
    Each chunk = {title, number, level, content, page_start}
    """
    full_text = "\n".join(p["text"] for p in pages)
    chunks = []

    for i, entry in enumerate(toc_entries):
        title = entry["title"]
        # Find where this topic starts in the full text
        start = full_text.find(title)
        if start == -1:
            continue

        # Find where next topic starts
        if i + 1 < len(toc_entries):
            next_title = toc_entries[i + 1]["title"]
            end = full_text.find(next_title, start + len(title))
            content = full_text[start:end] if end != -1 else full_text[start:start + 3000]
        else:
            content = full_text[start:start + 3000]

        chunks.append({
            "title": title,
            "number": entry["number"],
            "level": entry["level"],
            "content": content[:3000].strip(),  # cap at 3000 chars
        })

    return chunks


# ---------------------------------------------------------------------------
# Database seeding
# ---------------------------------------------------------------------------

def seed_subject(subject_name: str, grade: int, subject_code: str) -> str:
    """Insert subject, return subject_id."""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO subject(subject_id, subject_name, subject_code, grade_level)
                VALUES(%s, %s, %s, %s)
                ON CONFLICT (subject_name, grade_level) DO UPDATE SET subject_code = EXCLUDED.subject_code
                RETURNING subject_id
                """,
                (str(uuid.uuid4()), subject_name, subject_code, grade),
            )
            return str(cur.fetchone()[0])


def seed_topics(subject_id: str, chunks: list[dict], subject_code: str) -> list[dict]:
    """Insert topics, return list of {topic_id, title, content}."""
    seeded = []
    chapter_ids = {}  # number → topic_id for parent linking

    with connection() as conn:
        with conn.cursor() as cur:
            for chunk in chunks:
                topic_id = str(uuid.uuid4())
                topic_code = f"{subject_code}.{chunk['number']}"
                parent_id = None

                # Link subtopics to their chapter
                if chunk["level"] == 2:
                    chapter_num = chunk["number"].split(".")[0]
                    parent_id = chapter_ids.get(chapter_num)

                cur.execute(
                    """
                    INSERT INTO topic(
                        topic_id, subject_id, parent_topic_id, topic_name,
                        topic_code, difficulty_tier, objectives, keywords
                    )
                    VALUES(%s, %s, %s, %s, %s, 'medium', ARRAY[]::text[], ARRAY[]::text[])
                    ON CONFLICT (topic_code) DO UPDATE SET topic_name = EXCLUDED.topic_name
                    RETURNING topic_id
                    """,
                    (topic_id, subject_id, parent_id, chunk["title"], topic_code),
                )
                actual_id = str(cur.fetchone()[0])

                if chunk["level"] == 1:
                    chapter_ids[chunk["number"]] = actual_id

                seeded.append({
                    "topic_id": actual_id,
                    "title": chunk["title"],
                    "content": chunk["content"],
                    "topic_code": topic_code,
                })

    return seeded


# ---------------------------------------------------------------------------
# Embeddings + content generation
# ---------------------------------------------------------------------------

def generate_embeddings(seeded_topics: list[dict]) -> None:
    embedder = MiniLMEmbedder()
    texts = [f"{t['title']} {t['content'][:500]}" for t in seeded_topics]
    vectors = embedder.embed_batch(texts)

    with connection() as conn:
        with conn.cursor() as cur:
            for topic, vector in zip(seeded_topics, vectors):
                cur.execute(
                    "UPDATE topic SET embedding = %s WHERE topic_id = %s",
                    (vector, topic["topic_id"]),
                )
    print(f"  Embeddings: {len(seeded_topics)} topics embedded")


async def generate_content(seeded_topics: list[dict], settings: Settings) -> None:
    from core.models.topic import Topic
    from services.content_service import ContentService
    from infrastructure.repositories.resource_repo import ResourceRepository
    from infrastructure.repositories.topic_repo import TopicRepository
    from infrastructure.repositories.question_repo import QuestionRepository

    generator = GroqGenerator(api_key=settings.GROQ_API_KEY)
    svc = ContentService(
        generator=generator,
        resource_repo=ResourceRepository(),
        topic_repo=TopicRepository(),
        question_repo=QuestionRepository(),
    )

    success, failed = 0, 0
    for i, t in enumerate(seeded_topics, 1):
        try:
            await svc.generate_lesson(t["topic_id"])
            await asyncio.sleep(2)  # Groq rate limit
            await svc.generate_questions(t["topic_id"], count=5)
            await asyncio.sleep(2)
            success += 1
            print(f"  [{i}/{len(seeded_topics)}] ✓ {t['title']}")
        except Exception as e:
            failed += 1
            print(f"  [{i}/{len(seeded_topics)}] ✗ {t['title']}: {e}")

    print(f"  Content: {success} succeeded, {failed} failed")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(pdf_path: str, subject_name: str, grade: int):
    settings = Settings()
    init_pool(settings.POSTGRES_URL)

    subject_code = f"{subject_name[:4].upper()}{grade}"

    print(f"\n{'='*50}")
    print(f"Ingesting: {subject_name} Grade {grade}")
    print(f"PDF: {pdf_path}")
    print(f"{'='*50}\n")

    print("Step 1/4: Extracting text from PDF...")
    pages = extract_text_by_page(pdf_path)
    print(f"  Extracted {len(pages)} pages")

    print("Step 2/4: Detecting topics from table of contents...")
    toc = detect_toc(pages)
    chunks = chunk_by_topic(pages, toc)
    print(f"  Found {len(toc)} TOC entries → {len(chunks)} topic chunks")

    if not chunks:
        print("  WARNING: No topics detected. Check PDF format.")
        print("  Tip: Ensure the PDF has a Table of Contents with chapter/section headings.")
        return

    print("Step 3/4: Seeding database...")
    subject_id = seed_subject(subject_name, grade, subject_code)
    seeded = seed_topics(subject_id, chunks, subject_code)
    print(f"  Seeded {len(seeded)} topics for subject_id={subject_id}")

    print("Step 4/4: Generating embeddings...")
    generate_embeddings(seeded)

    print("Step 5/5: Generating AI lessons + questions (this takes a while)...")
    await generate_content(seeded, settings)

    print(f"\n✅ Done! {subject_name} Grade {grade} is ready.")
    print(f"   Topics: {len(seeded)}")
    print(f"   Run 'python3 scripts/ingest_textbook.py --help' for next subject.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a textbook PDF into TriLink")
    parser.add_argument("--pdf",     required=True, help="Path to PDF file")
    parser.add_argument("--subject", required=True, help="Subject name e.g. 'Mathematics'")
    parser.add_argument("--grade",   required=True, type=int, help="Grade level e.g. 9")
    args = parser.parse_args()

    if not os.path.exists(args.pdf):
        print(f"Error: PDF not found: {args.pdf}")
        sys.exit(1)

    asyncio.run(run(args.pdf, args.subject, args.grade))
