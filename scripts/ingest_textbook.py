"""
Textbook ingestion pipeline — handles large PDFs (300+ pages, 10MB+).

Strategy:
  - Extract text page by page
  - Use the actual Table of Contents page to build topic structure
  - Chunk content into ~500 word segments per topic
  - Embed chunks (not whole chapters) for better semantic search
  - Generate lessons/questions from chunked content, not raw pages

Usage:
    # Step 1: Extract TOC and preview detected structure (dry run)
    python3 scripts/ingest_textbook.py --pdf data/textbooks/math_grade9.pdf --subject "Mathematics" --grade 9 --dry-run

    # Step 2: Full ingest
    python3 scripts/ingest_textbook.py --pdf data/textbooks/math_grade9.pdf --subject "Mathematics" --grade 9

    # Step 3: Skip content generation (just seed topics + embeddings)
    python3 scripts/ingest_textbook.py --pdf data/textbooks/math_grade9.pdf --subject "Mathematics" --grade 9 --no-content
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


CHUNK_WORDS = 400       # words per content chunk stored per topic
TOC_SEARCH_PAGES = 15   # how many pages to scan for table of contents


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


def find_toc_page(pages: list[dict]) -> str:
    """Return the raw text of the TOC page(s)."""
    toc_text = ""
    for p in pages[:TOC_SEARCH_PAGES]:
        t = p["text"].lower()
        if "contents" in t or "table of" in t or "chapter" in t:
            toc_text += p["text"] + "\n"
    return toc_text


def parse_toc(toc_text: str) -> list[dict]:
    """
    Parse TOC into structured entries.
    Handles common patterns:
      'Chapter 1  Number Systems  1'
      '1.1  Natural Numbers  5'
      'Unit 1: Kinematics'
    """
    entries = []

    # Chapter / Unit level
    for m in re.finditer(
        r'(?:Chapter|Unit|CHAPTER|UNIT)\s*(\d+)[:\s.]+([A-Za-z][^\n\d]{4,60})',
        toc_text, re.IGNORECASE
    ):
        entries.append({
            "level": 1,
            "number": m.group(1).strip(),
            "title": _clean(m.group(2)),
        })

    # Section level (1.1, 2.3, etc.)
    for m in re.finditer(
        r'\b(\d+\.\d+)\s+([A-Z][^\n\d]{4,60})',
        toc_text
    ):
        entries.append({
            "level": 2,
            "number": m.group(1).strip(),
            "title": _clean(m.group(2)),
        })

    # Deduplicate and sort by number
    seen = set()
    unique = []
    for e in entries:
        key = e["number"]
        if key not in seen:
            seen.add(key)
            unique.append(e)

    return sorted(unique, key=lambda x: _sort_key(x["number"]))


def _clean(text: str) -> str:
    # Remove trailing dots, page numbers, extra spaces
    return re.sub(r'[\.\s]+\d*\s*$', '', text).strip()


def _sort_key(number: str) -> tuple:
    parts = number.replace(".", " ").split()
    return tuple(int(p) for p in parts if p.isdigit())


# ---------------------------------------------------------------------------
# Content chunking
# ---------------------------------------------------------------------------

def assign_content_to_topics(pages: list[dict], toc_entries: list[dict]) -> list[dict]:
    """
    For each topic, find its content in the full text and extract a chunk.
    Uses title matching to locate where each topic starts.
    """
    full_text = "\n".join(p["text"] for p in pages)
    words = full_text.split()
    total_words = len(words)

    print(f"  Total words in textbook: {total_words:,}")

    enriched = []
    for i, entry in enumerate(toc_entries):
        # Find topic title in full text
        title = entry["title"]
        pos = full_text.lower().find(title.lower())

        if pos == -1:
            # Try partial match (first 4 words)
            partial = " ".join(title.split()[:4]).lower()
            pos = full_text.lower().find(partial)

        if pos != -1:
            # Extract CHUNK_WORDS words starting from this position
            word_start = len(full_text[:pos].split())
            chunk_words = words[word_start: word_start + CHUNK_WORDS]
            content = " ".join(chunk_words)
        else:
            # Fallback: distribute pages evenly across topics
            fraction = i / max(len(toc_entries), 1)
            word_start = int(fraction * total_words)
            chunk_words = words[word_start: word_start + CHUNK_WORDS]
            content = " ".join(chunk_words)

        enriched.append({**entry, "content": content})

    return enriched


# ---------------------------------------------------------------------------
# Database seeding
# ---------------------------------------------------------------------------

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
                topic_id = str(uuid.uuid4())
                topic_code = f"{subject_code}.{t['number']}"
                parent_id = None

                if t["level"] == 2:
                    chapter_num = t["number"].split(".")[0]
                    parent_id = chapter_ids.get(chapter_num)

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
                    "topic_id": actual_id,
                    "title": t["title"],
                    "content": t["content"],
                    "topic_code": topic_code,
                })

    return seeded


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

def generate_embeddings(seeded: list[dict]) -> None:
    from plugins.embedders.minilm_embedder import MiniLMEmbedder
    embedder = MiniLMEmbedder()

    # Embed in batches of 64
    batch_size = 64
    for i in range(0, len(seeded), batch_size):
        batch = seeded[i: i + batch_size]
        texts = [f"{t['title']} {t['content']}" for t in batch]
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
# Content generation (lessons + questions)
# ---------------------------------------------------------------------------

async def generate_content(seeded: list[dict], settings: Settings) -> None:
    from core.models.topic import Topic
    from services.content_service import ContentService
    from infrastructure.repositories.resource_repo import ResourceRepository
    from infrastructure.repositories.topic_repo import TopicRepository
    from infrastructure.repositories.question_repo import QuestionRepository
    from plugins.generators.groq_generator import GroqGenerator

    svc = ContentService(
        generator=GroqGenerator(api_key=settings.GROQ_API_KEY),
        resource_repo=ResourceRepository(),
        topic_repo=TopicRepository(),
        question_repo=QuestionRepository(),
    )

    success, failed = 0, 0
    total = len(seeded)

    for i, t in enumerate(seeded, 1):
        try:
            await svc.generate_lesson(t["topic_id"])
            await asyncio.sleep(2)          # stay under 30 req/min
            await svc.generate_questions(t["topic_id"], count=5)
            await asyncio.sleep(2)
            success += 1
            print(f"  [{i}/{total}] ✓ {t['title']}")
        except Exception as e:
            failed += 1
            print(f"  [{i}/{total}] ✗ {t['title']}: {e}")
            await asyncio.sleep(5)          # back off on error

    print(f"\n  Content generation: {success}/{total} succeeded, {failed} failed")


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

    print("Step 2: Parsing table of contents...")
    toc_text = find_toc_page(pages)
    toc_entries = parse_toc(toc_text)
    print(f"  Detected {len(toc_entries)} topics")

    if not toc_entries:
        print("\n  ⚠️  No topics detected automatically.")
        print("  The PDF may use non-standard formatting.")
        print("  Options:")
        print("    1. Check that the PDF has a 'Table of Contents' page")
        print("    2. Manually provide a topics JSON file (see --help)")
        return

    print("\n  Detected topics:")
    for e in toc_entries[:20]:
        indent = "    " if e["level"] == 2 else "  "
        print(f"{indent}[{e['number']}] {e['title']}")
    if len(toc_entries) > 20:
        print(f"  ... and {len(toc_entries) - 20} more")

    if dry_run:
        print("\n  Dry run complete. Run without --dry-run to ingest.")
        return

    print("\nStep 3: Assigning textbook content to topics...")
    enriched = assign_content_to_topics(pages, toc_entries)

    print("Step 4: Seeding database...")
    subject_id = seed_subject(subject_name, grade, subject_code)
    seeded = seed_topics(subject_id, enriched, subject_code)
    print(f"  Seeded {len(seeded)} topics  (subject_id={subject_id})")

    print("Step 5: Generating embeddings...")
    generate_embeddings(seeded)

    if no_content:
        print("\n  Skipping content generation (--no-content flag set)")
    else:
        est_minutes = len(seeded) * 4 / 60
        print(f"Step 6: Generating AI lessons + questions (~{est_minutes:.0f} min)...")
        await generate_content(seeded, settings)

    print(f"\n✅  {subject_name} Grade {grade} ingested successfully.")
    print(f"    Topics in DB: {len(seeded)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest a Grade 9 textbook PDF into TriLink",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview detected topics without writing to DB
  python3 scripts/ingest_textbook.py --pdf data/textbooks/math.pdf --subject Mathematics --grade 9 --dry-run

  # Full ingest (topics + embeddings + AI content)
  python3 scripts/ingest_textbook.py --pdf data/textbooks/math.pdf --subject Mathematics --grade 9

  # Ingest topics + embeddings only (generate content later)
  python3 scripts/ingest_textbook.py --pdf data/textbooks/math.pdf --subject Mathematics --grade 9 --no-content
        """
    )
    parser.add_argument("--pdf",        required=True,  help="Path to PDF textbook")
    parser.add_argument("--subject",    required=True,  help="Subject name e.g. 'Mathematics'")
    parser.add_argument("--grade",      required=True,  type=int, help="Grade level e.g. 9")
    parser.add_argument("--dry-run",    action="store_true", help="Preview topics without writing to DB")
    parser.add_argument("--no-content", action="store_true", help="Skip AI lesson/question generation")
    args = parser.parse_args()

    if not os.path.exists(args.pdf):
        print(f"Error: PDF not found: {args.pdf}")
        sys.exit(1)

    asyncio.run(run(args.pdf, args.subject, args.grade, args.dry_run, args.no_content))
