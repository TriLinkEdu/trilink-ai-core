"""
Seed free online book resources for all subjects.

Uses a curated list of high-quality, freely available textbooks from
OpenStax, CK-12, LibreTexts, and similar open education platforms.

Books are mapped at the subject level — every topic in that subject
gets the book as a resource. The recommender then ranks them by
semantic similarity to the student's weak topics.

Usage:
    python3 scripts/seed_books.py
    python3 scripts/seed_books.py --dry-run
"""
import sys
import os
import uuid
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config.settings import Settings
from infrastructure.db.postgres import init_pool, connection


# Curated free online books per subject
# Each entry: {title, url, description, subject_name, difficulty}
OPEN_BOOKS = [
    # ── Mathematics ──────────────────────────────────────────────────────────
    {
        "subject": "Mathematics",
        "title": "CK-12 Middle School Math Grade 9",
        "url": "https://www.ck12.org/student/",
        "description": (
            "Free interactive Grade 9 mathematics textbook covering number systems, "
            "algebra, geometry, trigonometry, statistics and probability. "
            "Includes practice problems and worked examples."
        ),
        "difficulty": "medium",
    },
    {
        "subject": "Mathematics",
        "title": "OpenStax Prealgebra and Algebra",
        "url": "https://openstax.org/subjects/math",
        "description": (
            "Free peer-reviewed mathematics textbooks from OpenStax covering "
            "sets, number systems, equations, inequalities, and introductory algebra. "
            "Used by millions of students worldwide."
        ),
        "difficulty": "easy",
    },
    {
        "subject": "Mathematics",
        "title": "Khan Academy Mathematics (Grade 9)",
        "url": "https://www.khanacademy.org/math",
        "description": (
            "Free online mathematics lessons covering algebra, geometry, trigonometry, "
            "statistics and probability. Includes videos, exercises and mastery challenges."
        ),
        "difficulty": "medium",
    },
    # ── Physics ───────────────────────────────────────────────────────────────
    {
        "subject": "Physics",
        "title": "OpenStax College Physics",
        "url": "https://openstax.org/books/college-physics-2e/pages/1-introduction-to-science-and-the-realm-of-physics-physical-quantities-and-units",
        "description": (
            "Free peer-reviewed physics textbook covering kinematics, Newton's laws, "
            "forces, energy, waves, sound, and temperature. "
            "Includes worked examples and conceptual questions."
        ),
        "difficulty": "medium",
    },
    {
        "subject": "Physics",
        "title": "CK-12 Physics - Intermediate",
        "url": "https://www.ck12.org/book/ck-12-physics-intermediate/",
        "description": (
            "Free Grade 9 physics textbook covering motion, forces, energy, "
            "simple machines, waves, sound, and heat. "
            "Interactive with simulations and practice problems."
        ),
        "difficulty": "easy",
    },
    {
        "subject": "Physics",
        "title": "Khan Academy Physics",
        "url": "https://www.khanacademy.org/science/physics",
        "description": (
            "Free physics lessons covering forces, motion, energy, waves, "
            "and thermodynamics. Includes videos and practice exercises."
        ),
        "difficulty": "medium",
    },
    # ── Biology ───────────────────────────────────────────────────────────────
    {
        "subject": "Biology",
        "title": "OpenStax Biology 2e",
        "url": "https://openstax.org/books/biology-2e/pages/1-introduction",
        "description": (
            "Free peer-reviewed biology textbook covering cell biology, "
            "classification of organisms, genetics, and ecology. "
            "Comprehensive with diagrams and review questions."
        ),
        "difficulty": "medium",
    },
    {
        "subject": "Biology",
        "title": "CK-12 Biology",
        "url": "https://www.ck12.org/book/ck-12-biology/",
        "description": (
            "Free Grade 9 biology textbook covering characteristics of living things, "
            "cell structure, classification, transport in cells, and microscopy. "
            "Includes interactive content and practice questions."
        ),
        "difficulty": "easy",
    },
    {
        "subject": "Biology",
        "title": "Khan Academy Biology",
        "url": "https://www.khanacademy.org/science/biology",
        "description": (
            "Free biology lessons covering cells, classification, evolution, "
            "and ecology. Includes videos, articles and practice exercises."
        ),
        "difficulty": "medium",
    },
    # ── Chemistry ─────────────────────────────────────────────────────────────
    {
        "subject": "Chemistry",
        "title": "OpenStax Chemistry: Atoms First 2e",
        "url": "https://openstax.org/books/chemistry-atoms-first-2e/pages/1-introduction",
        "description": (
            "Free peer-reviewed chemistry textbook covering atomic structure, "
            "periodic table, chemical reactions, and measurements. "
            "Includes worked examples and practice problems."
        ),
        "difficulty": "medium",
    },
    {
        "subject": "Chemistry",
        "title": "CK-12 Chemistry - Basic",
        "url": "https://www.ck12.org/book/ck-12-chemistry-basic/",
        "description": (
            "Free Grade 9 chemistry textbook covering atomic theory, "
            "periodic table, chemical reactions, and laboratory safety. "
            "Interactive with simulations."
        ),
        "difficulty": "easy",
    },
    {
        "subject": "Chemistry",
        "title": "Khan Academy Chemistry",
        "url": "https://www.khanacademy.org/science/chemistry",
        "description": (
            "Free chemistry lessons covering atomic structure, periodic table, "
            "chemical reactions, and stoichiometry. Includes videos and exercises."
        ),
        "difficulty": "medium",
    },
    # ── History ───────────────────────────────────────────────────────────────
    {
        "subject": "History",
        "title": "World History: Cultures, States, and Societies (UNG Press)",
        "url": "https://oer.galileo.usg.edu/history-textbooks/2/",
        "description": (
            "Free open-access world history textbook covering prehistoric humans, "
            "ancient civilizations, medieval kingdoms, and modern revolutions. "
            "Includes primary sources and discussion questions."
        ),
        "difficulty": "medium",
    },
    {
        "subject": "History",
        "title": "CK-12 World History",
        "url": "https://www.ck12.org/book/ck-12-world-history/",
        "description": (
            "Free world history textbook covering human evolution, ancient civilizations, "
            "African kingdoms, European history, and modern revolutions. "
            "Includes timelines and review questions."
        ),
        "difficulty": "easy",
    },
    {
        "subject": "History",
        "title": "Khan Academy World History",
        "url": "https://www.khanacademy.org/humanities/world-history",
        "description": (
            "Free world history lessons covering human origins, ancient civilizations, "
            "African empires, and modern revolutions including the French Revolution. "
            "Includes videos and articles."
        ),
        "difficulty": "medium",
    },
]


def get_subject_topics(subject_name: str) -> list[dict]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.topic_id, t.topic_name
                FROM topic t JOIN subject s ON s.subject_id = t.subject_id
                WHERE s.subject_name = %s
                """,
                (subject_name,),
            )
            return [{"topic_id": str(r[0]), "name": r[1]} for r in cur.fetchall()]


def already_seeded(url: str, topic_id: str) -> bool:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM resource WHERE topic_id=%s AND url=%s LIMIT 1",
                (topic_id, url),
            )
            return cur.fetchone() is not None


def save_book(topic_id: str, book: dict) -> None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO resource(
                    resource_id, topic_id, title, type, difficulty,
                    content, url, source, needs_review
                )
                VALUES(%s, %s, %s, 'book', %s, %s, %s, 'open_library', FALSE)
                ON CONFLICT DO NOTHING
                """,
                (
                    str(uuid.uuid4()), topic_id,
                    book["title"],
                    book["difficulty"],
                    f"{book['title']}\n{book['description']}",
                    book["url"],
                ),
            )


def run(dry_run: bool):
    print(f"\nSeeding {len(OPEN_BOOKS)} open books across all subjects...\n")

    total_saved = 0
    total_skipped = 0

    for book in OPEN_BOOKS:
        topics = get_subject_topics(book["subject"])
        if not topics:
            print(f"  ⚠️  No topics found for {book['subject']}")
            continue

        saved = 0
        for topic in topics:
            if dry_run:
                print(f"  Would add: [{book['subject']}] {book['title'][:50]} → {topic['name'][:40]}")
                continue
            if already_seeded(book["url"], topic["topic_id"]):
                total_skipped += 1
                continue
            save_book(topic["topic_id"], book)
            saved += 1
            total_saved += 1

        if not dry_run and saved > 0:
            print(f"  ✓ [{book['subject']}] {book['title'][:60]} → {saved} topics")

    if not dry_run:
        print(f"\n✅ Done. {total_saved} book resources saved, {total_skipped} already existed.")
        print("Run generate_embeddings.py to embed the new resources.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed open book resources")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    init_pool(Settings().POSTGRES_URL)
    run(args.dry_run)
