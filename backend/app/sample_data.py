from __future__ import annotations

from app.db import get_db
from app.services.rag import chunk_text


SEED_DOCUMENTS = [
    {
        "title": "Haji profile",
        "tags": "identity,business",
        "source": "seed",
        "content": (
            "Haji is the central persona for HajiHaz AI. The assistant should answer in a clear, confident, "
            "supportive style and help with business operations, planning, research, and legal-admin workflows."
        ),
    },
    {
        "title": "Business focus",
        "tags": "strategy,suplaykart",
        "source": "seed",
        "content": (
            "Primary areas include Suplaykart operations, intraday market analysis, corporate advisory, "
            "product planning, and knowledge-base management for repeatable decisions."
        ),
    },
    {
        "title": "Deployment notes",
        "tags": "deployment,ops",
        "source": "seed",
        "content": (
            "Deploy backend first, then set API_BASE_URL to the live FastAPI URL so the frontend proxy can reach "
            "it at runtime. For zero-cost local AI, run Ollama and set AI_PROVIDER=ollama with a local model."
        ),
    },
]


def seed_if_empty() -> None:
    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) AS total FROM documents").fetchone()
        if row and int(row["total"]) > 0:
            return

        for document in SEED_DOCUMENTS:
            cursor = conn.execute(
                """
                INSERT INTO documents (title, content, source, tags)
                VALUES (?, ?, ?, ?)
                """,
                (document["title"], document["content"], document["source"], document["tags"]),
            )
            document_id = cursor.lastrowid
            for index, chunk in enumerate(chunk_text(document["content"])):
                conn.execute(
                    """
                    INSERT INTO chunks (document_id, content, chunk_index)
                    VALUES (?, ?, ?)
                    """,
                    (document_id, chunk, index),
                )
        conn.commit()
