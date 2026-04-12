"""
Textbook ingestion pipeline — handles large PDFs (300+ pages, 10MB+).

Scans the ENTIRE document for unit/chapter/section headings, not just TOC pages.
This catches all topics even when TOC formatting is non-standard.

Usage:
    # Preview detected topics (dry run)
    python3 scripts/ingest_textbook.py --pdf data/textbooks/math.pdf --subject Mathematics --grade 9 --dry-run

    # Full ingest (topics + embeddings, skip AI content generation)
    python3 scripts/ingest_textbook.py --pdf data/textbooks/math.pdf --subject Mathematics --grade 9 --no-content

    # Full ingest including AI content generation
    python3 scripts/ingest_textbook.py --pdf data/textbooks/math.pdf --subject Mathematics --grade 9
"""
import sys
import os
import re
import uuid
import asyncio
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pdfplumber
from config.settings import Settings
from infrastructure.db.postgres import init_pool, connection


CHUNK_WORDS    = 400
TOC_PAGES      = 25   # pages to scan for TOC
FULL_SCAN      = True  # also scan full doc for headings missed in TOC


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def extract_pages(pdf_path: str) -> list[dict]:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        print(f"  PDF has {total} pages")
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if text.strip():
                pages.append({"page": i, "text": text.strip()})
    return pages


# ---------------------------------------------------------------------------
# Topic detection — scans full document
# ---------------------------------------------------------------------------

def detect_topics(pages: list[dict]) -> list[dict]:
    """
    Scan the entire document for unit/chapter/section headings.
    Returns deduplicated, sorted list of topics.
    """
    entries = []
    seen_keys = set()

    full_text = "\n".join(p["text"] for p in pages)

    # Unit / Chapter level
    for m in re.finditer(
        r'(?:Unit|Chapter|UNIT|CHAPTER)\s+(\d+)[:\s]+([A-Za-z][^\n]{3,70})',
        full_text, re.IGNORECASE
    ):
        num   = m.group(1).strip()
        title = _clean(m.group(2))
        key   = (num, title[:15])
        if key not in seen_keys and len(title) > 3:
            seen_keys.add(key)
            entries.append({"level": 1, "number": num, "title": title})

    # Section level (1.1, 2.3, 9.4 etc.)
    for m in re.finditer(
        r'(?m)^(\d+\.\d+)\s+([A-Z][^\n]{4,70})$',
        full_text
    ):
        num   = m.group(1).strip()
        title = _clean(m.group(2))
        key   = (num, title[:15])
        if key not in seen_keys and len(title) > 4:
            seen_keys.add(key)
            entries.append({"level": 2, "number": num, "title": title})

    return sorted(entries, key=lambda x: _sort_key(x["number"]))


def _clean(text: str) -> str:
    text = re.sub(r'[_\.\s]+\d*\s*$', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)  # fix CamelCase
    return text.strip()


def _sort_key(number: str) -> tuple:
    parts = number.replace(".", " ").split()
    return tuple(int(p) for p in parts if p.isdigit())


# ---------------------------------------------------------------------------
# Content chunking
# ---------------------------------------------------------------------------

def assign_content(pages: list[dict], topics: list[dict]) -> list[dict]:
    full_text = "\n".join(p["text"] for p in pages)
    words     = full_text.split()
    total     = len(words)

    enriched = []
    for i, t in enumerate(topics):
        pos = full_text.lower().find(t["title"].lower())
        if pos == -1:
            partial = " ".join(t["title"].split()[:3]).lower()
            pos = full_text.lower().find(partial)

        if pos != -1:
            word_start = len(full_text[:pos].split())
        else:
            word_start = int((i / max(len(topics), 1)) * total)

        chunk = " ".join(words[word_start: word_start + CHUNK_WORDS])
        enriched.append({**t, "content": chunk})

    return enriched


# ---------------------------------------------------------------------------
# Database seeding
# ---------------------------------------------------------------------------

def clear_subject_topics(subject_id: str) -> None:
    """Remove existing topics for this subject before re-ingesting."""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM topic WHERE subject_id = %s", (subject_id,))


def seed_subject(subject_name: str, grade: int, subject_code: str) -> str:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO subject(subject_id, subject_name, subject_code, grade_level)
                VALUES(%s, %s, %s, %s)
                ON CONFLICT (subject_name, grade_level)
                DO UPDATE SET subject_code = EXCLUDED.subject_code
                RETURNING subject_id
                """,
                (str(uuid.uuid4()), subject_name, subject_code, grade),
            )
            return str(cur.fetchone()[0])


def seed_topics(subject_id: str, topics: list[dict], subject_code: str) -> list[dict]:
    seeded = []
    chapter_ids = {}

    with connection() as conn:
        with conn.cursor() as cur:
            for t in topics:
                topic_id   = str(uuid.uuid4())
                topic_code = f"{subject_code}.{t['number']}"
                parent_id  = None

                if t["level"] == 2:
                    chapter_num = t["number"].split(".")[0]
                    parent_id   = chapter_ids.get(chapter_num)

                cur.execute(
                    """
                    INSERT INTO topic(
                        topic_id, subject_id, parent_topic_id,
                        topic_name, topic_code, difficulty_tier,
                        objectives, keywords
                    )
                    VALUES(%s, %s, %s, %s, %s, 'medium', ARRAY[]::text[], ARRAY[]::text[])
                    ON CONFLICT (topic_code) DO UPDATE
                        SET topic_name = EXCLUDED.topic_name
                    RETURNING topic_id
                    """,
                    (topic_id, subject_id, parent_id, t["title"], topic_code),
                )
                actual_id = str(cur.fetchone()[0])

                if t["level"] == 1:
                    chapter_ids[t["number"]] = actual_id

                seeded.append({
                    "topic_id"  : actual_id,
                    "title"     : t["title"],
                    "content"   : t["content"],
                    "topic_code": topic_code,
                })

    return seeded


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def generate_embeddings(seeded: list[dict]) -> None:
    from plugins.embedders.minilm_embedder import MiniLMEmbedder
    embedder   = MiniLMEmbedder()
    batch_size = 64

    for i in range(0, len(seeded), batch_size):
        batch   = seeded[i: i + batch_size]
        texts   = [f"{t['title']} {t['content']}" for t in batch]
        vectors = embedder.embed_batch(texts)

        with connection() as conn:
            with conn.cursor() as cur:
                for topic, vector in zip(batch, vectors):
                    cur.execute(
                        "UPDATE topic SET embedding = %s WHERE topic_id = %s",
                        (vector, topic["topic_id"]),
                    )
        print(f"  Embedded {min(i + batch_size, len(seeded))}/{len(seeded)}")


# ---------------------------------------------------------------------------
# Content generation
# ---------------------------------------------------------------------------

async def generate_content(seeded: list[dict], settings: Settings) -> None:
    from services.content_service import ContentService
    from infrastructure.repositories.resource_repo import ResourceRepository
    from infrastructure.repositories.topic_repo import TopicRepository
    from infrastructure.repositories.question_repo import QuestionRepository
    from config.plugin_registry import PluginRegistry

    registry = PluginRegistry(settings)
    svc = ContentService(
        generator    =registry.generator,
        resource_repo=ResourceRepository(),
        topic_repo   =TopicRepository(),
        question_repo=QuestionRepository(),
    )

    success, failed = 0, 0
    for i, t in enumerate(seeded, 1):
        try:
            await svc.generate_lesson(t["topic_id"])
            await asyncio.sleep(2)
            await svc.generate_questions(t["topic_id"], count=5)
            await asyncio.sleep(2)
            success += 1
            print(f"  [{i}/{len(seeded)}] ✓ {t['title']}")
        except Exception as e:
            failed += 1
            print(f"  [{i}/{len(seeded)}] ✗ {t['title']}: {e}")
            await asyncio.sleep(5)

    print(f"\n  Content: {success}/{len(seeded)} succeeded, {failed} failed")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(pdf_path: str, subject_name: str, grade: int,
              dry_run: bool = False, no_content: bool = False):

    settings = Settings()
    if not dry_run:
        init_pool(settings.POSTGRES_URL)

    subject_code = f"{subject_name[:4].upper()}{grade}"

    print(f"\n{'='*55}")
    print(f"  {subject_name} Grade {grade}  |  {os.path.basename(pdf_path)}")
    print(f"{'='*55}\n")

    print("Step 1: Extracting text from PDF...")
    pages = extract_pages(pdf_path)

    print("Step 2: Detecting topics (full document scan)...")
    topics = detect_topics(pages)
    print(f"  Detected {len(topics)} topics")

    if not topics:
        print("  ⚠️  No topics detected. Check PDF format.")
        return

    print("\n  Topics detected:")
    for t in topics[:30]:
        indent = "    " if t["level"] == 2 else "  "
        print(f"{indent}[{t['number']}] {t['title']}")
    if len(topics) > 30:
        print(f"  ... and {len(topics) - 30} more")

    if dry_run:
        print(f"\n  Dry run complete. {len(topics)} topics found.")
        return

    print("\nStep 3: Assigning textbook content to topics...")
    enriched = assign_content(pages, topics)

    print("Step 4: Seeding database (replacing existing topics)...")
    subject_id = seed_subject(subject_name, grade, subject_code)
    clear_subject_topics(subject_id)
    seeded = seed_topics(subject_id, enriched, subject_code)
    print(f"  Seeded {len(seeded)} topics")

    print("Step 5: Generating embeddings...")
    generate_embeddings(seeded)

    if no_content:
        print("\n  Skipping content generation (--no-content)")
    else:
        est = len(seeded) * 4 / 60
        print(f"Step 6: Generating AI content (~{est:.0f} min)...")
        await generate_content(seeded, settings)

    print(f"\n✅  {subject_name} Grade {grade} — {len(seeded)} topics ingested.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a Grade 9 textbook PDF into TriLink")
    parser.add_argument("--pdf",        required=True,  help="Path to PDF")
    parser.add_argument("--subject",    required=True,  help="Subject name e.g. Mathematics")
    parser.add_argument("--grade",      required=True,  type=int)
    parser.add_argument("--dry-run",    action="store_true", help="Preview without writing to DB")
    parser.add_argument("--no-content", action="store_true", help="Skip AI content generation")
    args = parser.parse_args()

    if not os.path.exists(args.pdf):
        print(f"Error: PDF not found: {args.pdf}")
        sys.exit(1)

    asyncio.run(run(args.pdf, args.subject, args.grade, args.dry_run, args.no_content))
