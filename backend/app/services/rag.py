from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlparse

from app.db import get_db


WORD_RE = re.compile(r"[a-zA-Z0-9]+")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
CHUNK_TARGET_WORDS = 170
CHUNK_OVERLAP_WORDS = 36
CHUNK_MIN_WORDS = 40
SEARCH_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "i",
    "in",
    "into",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "them",
    "this",
    "to",
    "we",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "you",
    "your",
}
SYNCABLE_SOURCES = {"url", "google-docs", "google-sheets", "google-drive", "notion"}
PERSONA_IDENTIFIERS = {
    "haji",
    "hajihaz",
    "hajihaz ai",
    "syed hasan",
    "syed hasan kuddos",
    "kuddos sahib",
}
PERSONA_BUSINESS_MARKERS = {"business", "businesses", "company", "companies", "venture", "ventures", "owner", "own", "owns"}
PERSONA_EDUCATION_MARKERS = {"education", "qualification", "qualifications", "degree", "school", "college", "university", "certification"}
PERSONA_AI_MARKERS = {"hajihaz ai", "assistant", "system", "purpose", "what can it do", "capability", "capabilities"}
PERSONA_DOC_KEYWORDS = {"haji", "hajihaz", "profile", "identity", "about", "bio", "biography", "background", "personality", "syed", "hasan", "kuddos"}
PERSONA_BUSINESS_DOC_KEYWORDS = {"business", "businesses", "company", "companies", "venture", "ventures", "owner", "owns", "portfolio", "suplaykart"}
PERSONA_EDUCATION_DOC_KEYWORDS = {"education", "qualification", "qualifications", "degree", "school", "college", "university", "certification"}
PERSONA_AI_DOC_KEYWORDS = {"hajihaz ai", "assistant", "system", "purpose", "workflow", "capabilities", "help"}
OPERATIONAL_QUERY_MARKERS = {
    "warranty",
    "claim",
    "claims",
    "response",
    "window",
    "policy",
    "checklist",
    "checklists",
    "onboarding",
    "client",
    "pricing",
    "support",
    "timeline",
    "timelines",
    "kickoff",
    "owner",
    "assignment",
    "sop",
    "faq",
}


def tokenize(text: str) -> List[str]:
    return [match.group(0).lower() for match in WORD_RE.finditer(text)]


def search_tokens(text: str) -> List[str]:
    return [token for token in tokenize(text) if len(token) > 2 and token not in SEARCH_STOPWORDS]


def normalize_tags(tags: List[str]) -> List[str]:
    seen: set[str] = set()
    normalized: List[str] = []
    for tag in tags:
        cleaned = " ".join(str(tag).split()).strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(cleaned)
    return normalized


def normalize_group_name(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip()


def normalize_source_url(value: str | None) -> str | None:
    cleaned = " ".join(str(value or "").split()).strip()
    return cleaned or None


def source_domain(source_url: str | None) -> str:
    if not source_url:
        return ""
    parsed = urlparse(source_url)
    return parsed.netloc.lower()


def _split_sentences(text: str) -> List[str]:
    return [" ".join(sentence.split()).strip() for sentence in SENTENCE_RE.split(text) if sentence.strip()]


def _split_paragraphs(text: str) -> List[str]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n+", text) if paragraph.strip()]
    return paragraphs or [" ".join(text.split()).strip()]


def chunk_text(text: str) -> List[str]:
    paragraphs = _split_paragraphs(text)
    chunks: List[str] = []
    current_parts: List[str] = []
    current_words = 0

    def flush() -> None:
        nonlocal current_parts, current_words
        if not current_parts:
            return
        chunk = " ".join(current_parts).strip()
        if chunk:
            chunks.append(chunk)
        overlap_words = chunk.split()[-CHUNK_OVERLAP_WORDS:]
        current_parts = [" ".join(overlap_words)] if overlap_words else []
        current_words = len(overlap_words)

    for paragraph in paragraphs:
        sentences = _split_sentences(paragraph) or [paragraph]
        for sentence in sentences:
            words = sentence.split()
            if not words:
                continue
            if current_parts and current_words + len(words) > CHUNK_TARGET_WORDS and current_words >= CHUNK_MIN_WORDS:
                flush()
            current_parts.append(sentence)
            current_words += len(words)

        if current_words >= CHUNK_TARGET_WORDS:
            flush()

    if current_parts:
        chunk = " ".join(current_parts).strip()
        if chunk:
            chunks.append(chunk)

    return [chunk for chunk in chunks if len(chunk.split()) >= 8]


def _vectorize(tokens: List[str]) -> Dict[str, float]:
    counts = Counter(tokens)
    total = sum(counts.values()) or 1
    return {token: count / total for token, count in counts.items()}


def _cosine_similarity(left: Dict[str, float], right: Dict[str, float]) -> float:
    intersection = set(left).intersection(right)
    numerator = sum(left[token] * right[token] for token in intersection)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _token_overlap(left_tokens: List[str], right_tokens: List[str]) -> float:
    left_set = set(left_tokens)
    right_set = set(right_tokens)
    if not left_set or not right_set:
        return 0.0
    return len(left_set.intersection(right_set)) / len(left_set)


def _checksum(title: str, content: str, source: str, group_name: str, source_url: str | None) -> str:
    normalized = "|".join(
        [
            " ".join(title.split()).lower(),
            " ".join(content.split()).lower(),
            source.strip().lower(),
            normalize_group_name(group_name).lower(),
            (source_url or "").strip().lower(),
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _excerpt_for_query(content: str, query_tokens: List[str], maximum: int = 280) -> str:
    sentences = _split_sentences(content)
    if not sentences:
        return content[:maximum].strip()

    scored = sorted(
        (
            (
                len(set(search_tokens(sentence)).intersection(query_tokens)),
                -index,
                sentence,
            )
            for index, sentence in enumerate(sentences)
        ),
        reverse=True,
    )
    best = scored[0][2].strip()
    if len(best) >= maximum or len(sentences) == 1:
        return best[: maximum - 1].rstrip() + "…" if len(best) > maximum else best

    second_sentence = ""
    best_index = next((index for index, sentence in enumerate(sentences) if sentence == best), None)
    if best_index is not None:
        for neighbor_index in (best_index + 1, best_index - 1):
            if 0 <= neighbor_index < len(sentences):
                candidate = sentences[neighbor_index].strip()
                if candidate:
                    second_sentence = candidate
                    break
    combined = " ".join(item for item in [best, second_sentence] if item).strip()
    if len(combined) <= maximum:
        return combined
    return combined[: maximum - 1].rstrip() + "…"


def _document_source_key(source: str, document_id: int, source_url: str | None) -> str:
    normalized_url = normalize_source_url(source_url)
    if normalized_url:
        return f"{source}:{normalized_url.lower()}"
    return f"{source}:{document_id}"


def _persona_query_topic(query: str) -> str | None:
    normalized = " ".join(query.lower().split())
    if "hajihaz ai" in normalized:
        return "ai"
    if not any(identifier in normalized for identifier in PERSONA_IDENTIFIERS):
        return None
    if any(marker in normalized for marker in PERSONA_EDUCATION_MARKERS):
        return "education"
    if any(marker in normalized for marker in PERSONA_BUSINESS_MARKERS):
        return "business"
    if any(marker in normalized for marker in PERSONA_AI_MARKERS):
        return "ai"
    return "identity"


def _persona_document_bonus(query: str, title: str, tags: List[str], content: str) -> float:
    topic = _persona_query_topic(query)
    if not topic:
        return 0.0

    haystack = " ".join([title.lower(), " ".join(tag.lower() for tag in tags), content.lower()[:900]])
    base_hits = sum(1 for keyword in PERSONA_DOC_KEYWORDS if keyword in haystack)
    topic_keywords = {
        "identity": PERSONA_DOC_KEYWORDS,
        "business": PERSONA_BUSINESS_DOC_KEYWORDS,
        "education": PERSONA_EDUCATION_DOC_KEYWORDS,
        "ai": PERSONA_AI_DOC_KEYWORDS,
    }.get(topic, set())
    topic_hits = sum(1 for keyword in topic_keywords if keyword in haystack)
    title_hits = sum(1 for keyword in topic_keywords.union(PERSONA_DOC_KEYWORDS) if keyword in title.lower())
    tag_hits = sum(1 for keyword in topic_keywords.union(PERSONA_DOC_KEYWORDS) if keyword in " ".join(tag.lower() for tag in tags))

    bonus = 0.0
    if base_hits:
        bonus += min(0.55, base_hits * 0.16)
    if topic_hits:
        bonus += min(0.85, topic_hits * 0.22)
    if title_hits:
        bonus += min(0.32, title_hits * 0.14)
    if tag_hits:
        bonus += min(0.18, tag_hits * 0.08)
    return bonus


def _looks_specific_operational_query(query: str) -> bool:
    normalized = " ".join(query.lower().split())
    return any(marker in normalized for marker in OPERATIONAL_QUERY_MARKERS)


def _operational_document_adjustment(query: str, title: str, tags: List[str], content: str) -> float:
    if _persona_query_topic(query) or not _looks_specific_operational_query(query):
        return 0.0

    normalized_query = " ".join(query.lower().split())
    active_markers = [marker for marker in OPERATIONAL_QUERY_MARKERS if marker in normalized_query]
    if not active_markers:
        return 0.0

    lowered_title = title.lower()
    lowered_tags = " ".join(tag.lower() for tag in tags)
    lowered_content = content.lower()[:1200]
    haystack = f"{lowered_title} {lowered_tags} {lowered_content}"

    marker_hits = sum(1 for marker in active_markers if marker in haystack)
    title_hits = sum(1 for marker in active_markers if marker in lowered_title)
    tag_hits = sum(1 for marker in active_markers if marker in lowered_tags)

    persona_hits = sum(
        1
        for keyword in PERSONA_DOC_KEYWORDS.union(PERSONA_BUSINESS_DOC_KEYWORDS).union(PERSONA_EDUCATION_DOC_KEYWORDS).union(PERSONA_AI_DOC_KEYWORDS)
        if keyword in haystack
    )

    bonus = 0.0
    if marker_hits:
        bonus += min(0.9, marker_hits * 0.26)
    if title_hits:
        bonus += min(0.55, title_hits * 0.22)
    if tag_hits:
        bonus += min(0.32, tag_hits * 0.12)

    if persona_hits and marker_hits == 0:
        bonus -= min(1.25, persona_hits * 0.22)

    return bonus


def _syncable_source(source: str, source_url: str | None) -> bool:
    return bool(source_url and source in SYNCABLE_SOURCES)


def _row_to_document(row) -> dict:
    return {
        "id": int(row["id"]),
        "title": str(row["title"]),
        "content": str(row["content"]),
        "tags": [tag for tag in str(row["tags"]).split(",") if tag],
        "source": str(row["source"]),
        "group_name": str(row["group_name"] or ""),
        "core_persona": bool(row["core_persona"]),
        "source_url": str(row["source_url"]) if row["source_url"] else None,
        "source_key": str(row["source_key"] or ""),
        "source_enabled": bool(row["source_enabled"]),
        "last_synced_at": str(row["last_synced_at"]) if row["last_synced_at"] else None,
        "sync_status": str(row["sync_status"] or "ready"),
        "sync_error": str(row["sync_error"] or ""),
        "updated_at": str(row["updated_at"]),
    }


def _rebuild_chunks(conn, document_id: int, content: str) -> None:
    conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
    for index, chunk in enumerate(chunk_text(content)):
        conn.execute(
            """
            INSERT INTO chunks (document_id, content, chunk_index, token_count)
            VALUES (?, ?, ?, ?)
            """,
            (document_id, chunk, index, len(search_tokens(chunk))),
        )


def _repair_source_metadata(conn) -> None:
    rows = conn.execute(
        """
        SELECT id, source, source_url, source_key, last_synced_at, sync_status
        FROM documents
        WHERE source_key = '' OR source_key IS NULL OR sync_status = '' OR sync_status IS NULL
        """
    ).fetchall()
    for row in rows:
        source = str(row["source"])
        source_url = str(row["source_url"]) if row["source_url"] else None
        source_key = str(row["source_key"] or "") or _document_source_key(source, int(row["id"]), source_url)
        last_synced_at = row["last_synced_at"]
        if not last_synced_at and source_url:
            last_synced_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            UPDATE documents
            SET source_key = ?, last_synced_at = COALESCE(?, last_synced_at), sync_status = COALESCE(NULLIF(sync_status, ''), 'ready')
            WHERE id = ?
            """,
            (source_key, last_synced_at, int(row["id"])),
        )


def repair_source_metadata() -> None:
    with get_db() as conn:
        _repair_source_metadata(conn)
        conn.commit()


def _insert_document(
    conn,
    title: str,
    content: str,
    tags: List[str],
    source: str,
    group_name: str = "",
    core_persona: bool = False,
    source_url: str | None = None,
    *,
    source_key: str | None = None,
    source_enabled: bool = True,
    sync_status: str = "ready",
    sync_error: str = "",
    last_synced_at: str | None = None,
) -> int:
    normalized_tags = normalize_tags(tags)
    normalized_group = normalize_group_name(group_name)
    normalized_source_url = normalize_source_url(source_url)
    checksum = _checksum(title, content, source, normalized_group, normalized_source_url)
    tags_csv = ",".join(normalized_tags)
    cursor = conn.execute(
        """
        INSERT INTO documents (
            title,
            content,
            source,
            tags,
            group_name,
            core_persona,
            source_url,
            checksum,
            source_key,
            source_enabled,
            last_synced_at,
            sync_status,
            sync_error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            title,
            content,
            source,
            tags_csv,
            normalized_group,
            1 if core_persona else 0,
            normalized_source_url,
            checksum,
            source_key or "",
            1 if source_enabled else 0,
            last_synced_at,
            sync_status,
            sync_error[:600],
        ),
    )
    document_id = int(cursor.lastrowid)
    final_source_key = source_key or _document_source_key(source, document_id, normalized_source_url)
    conn.execute(
        """
        UPDATE documents
        SET source_key = ?, last_synced_at = COALESCE(last_synced_at, ?)
        WHERE id = ?
        """,
        (
            final_source_key,
            datetime.now(timezone.utc).isoformat() if normalized_source_url else None,
            document_id,
        ),
    )
    _rebuild_chunks(conn, document_id, content)
    return document_id


def add_document(
    title: str,
    content: str,
    tags: List[str],
    source: str,
    group_name: str = "",
    core_persona: bool = False,
    source_url: str | None = None,
) -> int:
    with get_db() as conn:
        document_id = _insert_document(conn, title, content, tags, source, group_name, core_persona, source_url)
        conn.commit()
    return document_id


def get_document(document_id: int) -> Optional[dict]:
    with get_db() as conn:
        _repair_source_metadata(conn)
        row = conn.execute(
            """
            SELECT
                id,
                title,
                content,
                tags,
                source,
                group_name,
                core_persona,
                source_url,
                source_key,
                source_enabled,
                last_synced_at,
                sync_status,
                sync_error,
                updated_at
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()
        conn.commit()
    if row is None:
        return None
    return _row_to_document(row)


def update_document(
    document_id: int,
    title: str,
    content: str,
    tags: List[str],
    source: str,
    group_name: str = "",
    core_persona: bool = False,
    source_url: str | None = None,
) -> Optional[dict]:
    normalized_tags = normalize_tags(tags)
    normalized_group = normalize_group_name(group_name)
    normalized_source_url = normalize_source_url(source_url)
    checksum = _checksum(title, content, source, normalized_group, normalized_source_url)
    tags_csv = ",".join(normalized_tags)
    with get_db() as conn:
        _repair_source_metadata(conn)
        existing = conn.execute(
            """
            SELECT id, source_key, source_enabled, last_synced_at
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()
        if existing is None:
            return None
        current_key = str(existing["source_key"] or "")
        if normalized_source_url:
            current_key = _document_source_key(source, document_id, normalized_source_url)
        elif not current_key:
            current_key = _document_source_key(source, document_id, normalized_source_url)
        conn.execute(
            """
            UPDATE documents
            SET title = ?, content = ?, source = ?, tags = ?, group_name = ?, core_persona = ?, source_url = ?, checksum = ?, source_key = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                title,
                content,
                source,
                tags_csv,
                normalized_group,
                1 if core_persona else 0,
                normalized_source_url,
                checksum,
                current_key,
                document_id,
            ),
        )
        _rebuild_chunks(conn, document_id, content)
        conn.commit()
    return get_document(document_id)


def set_document_core_persona(document_id: int, enabled: bool) -> Optional[dict]:
    with get_db() as conn:
        cursor = conn.execute(
            """
            UPDATE documents
            SET core_persona = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (1 if enabled else 0, document_id),
        )
        conn.commit()
    if cursor.rowcount <= 0:
        return None
    return get_document(document_id)


def delete_document(document_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        conn.commit()
    return cursor.rowcount > 0


def import_documents(documents: List[dict], skip_duplicates: bool = True) -> dict:
    imported_ids: List[int] = []
    skipped = 0
    with get_db() as conn:
        _repair_source_metadata(conn)
        for item in documents[:]:
            checksum = _checksum(
                item["title"],
                item["content"],
                item["source"],
                item.get("group_name", ""),
                item.get("source_url"),
            )
            if skip_duplicates:
                duplicate = conn.execute(
                    """
                    SELECT id
                    FROM documents
                    WHERE checksum = ?
                    LIMIT 1
                    """,
                    (checksum,),
                ).fetchone()
                if duplicate is not None:
                    skipped += 1
                    continue
            imported_ids.append(
                _insert_document(
                    conn,
                    item["title"],
                    item["content"],
                    item.get("tags", []),
                    item["source"],
                    item.get("group_name", ""),
                    bool(item.get("core_persona", False)),
                    item.get("source_url"),
                    source_key=item.get("source_key"),
                )
            )
        conn.commit()

    imported_documents = [document for document in list_documents() if document["id"] in set(imported_ids)]
    imported_documents.sort(key=lambda item: imported_ids.index(item["id"]))
    return {
        "imported": len(imported_documents),
        "skipped": skipped,
        "documents": imported_documents,
    }


def list_documents() -> List[dict]:
    with get_db() as conn:
        _repair_source_metadata(conn)
        rows = conn.execute(
            """
            SELECT
                id,
                title,
                content,
                tags,
                source,
                group_name,
                core_persona,
                source_url,
                source_key,
                source_enabled,
                last_synced_at,
                sync_status,
                sync_error,
                updated_at
            FROM documents
            ORDER BY updated_at DESC, id DESC
            """
        ).fetchall()
        conn.commit()
    return [_row_to_document(row) for row in rows]


def stats() -> dict:
    with get_db() as conn:
        _repair_source_metadata(conn)
        documents = conn.execute("SELECT COUNT(*) AS total FROM documents").fetchone()
        chunks = conn.execute("SELECT COUNT(*) AS total FROM chunks").fetchone()
        groups = conn.execute("SELECT COUNT(DISTINCT NULLIF(group_name, '')) AS total FROM documents").fetchone()
        sources = conn.execute("SELECT COUNT(DISTINCT source_key) AS total FROM documents").fetchone()
        active_sources = conn.execute("SELECT COUNT(DISTINCT source_key) AS total FROM documents WHERE source_enabled = 1").fetchone()
        conn.commit()
    return {
        "documents": int(documents["total"]) if documents else 0,
        "chunks": int(chunks["total"]) if chunks else 0,
        "groups": int(groups["total"]) if groups else 0,
        "sources": int(sources["total"]) if sources else 0,
        "active_sources": int(active_sources["total"]) if active_sources else 0,
    }


def export_documents(export_format: str = "json") -> tuple[str, str, str]:
    documents = list_documents()
    if export_format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=[
                "id",
                "title",
                "content",
                "tags",
                "source",
                "group_name",
                "core_persona",
                "source_url",
                "source_key",
                "source_enabled",
                "last_synced_at",
                "sync_status",
                "updated_at",
            ],
        )
        writer.writeheader()
        for document in documents:
            writer.writerow(
                {
                    **document,
                    "tags": ", ".join(document["tags"]),
                }
            )
        return buffer.getvalue(), "text/csv", "hajihaz-library.csv"

    if export_format == "markdown":
        blocks = []
        for document in documents:
            metadata = [
                f"- source: {document['source']}",
                f"- group: {document['group_name'] or 'ungrouped'}",
                f"- core_persona: {'yes' if document['core_persona'] else 'no'}",
                f"- tags: {', '.join(document['tags']) or 'none'}",
                f"- source_key: {document['source_key']}",
                f"- enabled: {'yes' if document['source_enabled'] else 'no'}",
                f"- sync_status: {document['sync_status']}",
            ]
            if document["source_url"]:
                metadata.append(f"- source_url: {document['source_url']}")
            blocks.append(
                "\n".join(
                    [
                        f"# {document['title']}",
                        *metadata,
                        "",
                        document["content"],
                    ]
                )
            )
        return "\n\n---\n\n".join(blocks), "text/markdown", "hajihaz-library.md"

    payload = io.StringIO()
    payload.write(json.dumps({"documents": documents}, indent=2))
    return payload.getvalue(), "application/json", "hajihaz-library.json"


def list_sources() -> List[dict]:
    with get_db() as conn:
        _repair_source_metadata(conn)
        rows = conn.execute(
            """
            SELECT
                source_key,
                source,
                MIN(title) AS source_label,
                COALESCE(NULLIF(group_name, ''), 'Ungrouped') AS group_name,
                MAX(source_url) AS source_url,
                COUNT(*) AS documents,
                SUM(CASE WHEN source_enabled = 1 THEN 1 ELSE 0 END) AS enabled_documents,
                MAX(updated_at) AS last_updated,
                MAX(last_synced_at) AS last_synced_at,
                GROUP_CONCAT(DISTINCT sync_status) AS sync_statuses,
                MAX(sync_error) AS sync_error
            FROM documents
            GROUP BY source_key, source, COALESCE(NULLIF(group_name, ''), 'Ungrouped')
            ORDER BY enabled_documents DESC, documents DESC, source ASC, group_name ASC
            """
        ).fetchall()
        conn.commit()

    items: List[dict] = []
    for row in rows:
        source = str(row["source"])
        source_url = str(row["source_url"]) if row["source_url"] else None
        enabled = int(row["enabled_documents"] or 0) > 0
        sync_statuses = {item for item in str(row["sync_statuses"] or "").split(",") if item}
        health = "healthy"
        if not enabled:
            health = "disabled"
        elif "error" in sync_statuses:
            health = "sync-error"
        elif not int(row["documents"] or 0):
            health = "empty"

        syncable = _syncable_source(source, source_url)
        detail_parts = [f"{int(row['documents'])} document(s) in this source"]
        if source_url:
            detail_parts.append(source_domain(source_url) or source_url)
        if not enabled:
            detail_parts.append("currently disabled for retrieval")
        elif syncable:
            detail_parts.append("syncable from the original URL")

        items.append(
            {
                "source_key": str(row["source_key"]),
                "source": source,
                "source_label": str(row["source_label"]),
                "group_name": str(row["group_name"]),
                "documents": int(row["documents"]),
                "last_updated": str(row["last_updated"]),
                "last_synced_at": str(row["last_synced_at"]) if row["last_synced_at"] else None,
                "total_characters": 0,
                "health": health,
                "detail": ". ".join(detail_parts).strip() + ".",
                "source_url": source_url,
                "enabled": enabled,
                "syncable": syncable,
                "sync_status": "error" if "error" in sync_statuses else "ready",
                "sync_error": str(row["sync_error"] or ""),
            }
        )
    return items


def source_health() -> List[dict]:
    return list_sources()


def get_source(source_key: str) -> Optional[dict]:
    normalized = source_key.strip()
    if not normalized:
        return None
    for item in list_sources():
        if item["source_key"] == normalized:
            return item
    return None


def set_source_enabled(source_key: str, enabled: bool) -> Optional[dict]:
    normalized = source_key.strip()
    if not normalized:
        return None
    with get_db() as conn:
        cursor = conn.execute(
            """
            UPDATE documents
            SET source_enabled = ?, updated_at = CURRENT_TIMESTAMP
            WHERE source_key = ?
            """,
            (1 if enabled else 0, normalized),
        )
        conn.commit()
    if cursor.rowcount <= 0:
        return None
    return get_source(normalized)


def reindex_source(source_key: str) -> Optional[dict]:
    normalized = source_key.strip()
    if not normalized:
        return None
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, content
            FROM documents
            WHERE source_key = ?
            ORDER BY id ASC
            """,
            (normalized,),
        ).fetchall()
        if not rows:
            return None
        for row in rows:
            _rebuild_chunks(conn, int(row["id"]), str(row["content"]))
        conn.commit()
    return get_source(normalized)


async def sync_source(source_key: str) -> Optional[dict]:
    normalized = source_key.strip()
    if not normalized:
        return None

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, source, source_url, group_name, tags, source_enabled
            FROM documents
            WHERE source_key = ?
            ORDER BY id ASC
            """,
            (normalized,),
        ).fetchall()
    if not rows:
        return None

    source = str(rows[0]["source"])
    source_url = str(rows[0]["source_url"]) if rows[0]["source_url"] else None
    if not _syncable_source(source, source_url):
        raise ValueError("This source does not support sync because it has no syncable origin URL.")

    existing_tags = normalize_tags(
        [tag for row in rows for tag in str(row["tags"]).split(",") if tag]
    )
    group_name = normalize_group_name(rows[0]["group_name"])

    from app.services.ingestion import import_documents_from_url
    from app.services.monitoring import record_alert

    try:
        synced_documents = await import_documents_from_url(source_url or "", group_name, existing_tags)
    except Exception as exc:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE documents
                SET sync_status = 'error', sync_error = ?, updated_at = CURRENT_TIMESTAMP
                WHERE source_key = ?
                """,
                (str(exc)[:600], normalized),
            )
            conn.commit()
        record_alert("error", "Source sync failed", str(exc), source=normalized)
        raise

    with get_db() as conn:
        enabled_value = 1 if bool(rows[0]["source_enabled"]) else 0
        conn.execute("DELETE FROM documents WHERE source_key = ?", (normalized,))
        for item in synced_documents:
            _insert_document(
                conn,
                item["title"],
                item["content"],
                item.get("tags", []),
                item["source"],
                item.get("group_name", group_name),
                bool(item.get("core_persona", False)),
                item.get("source_url", source_url),
                source_key=normalized,
                source_enabled=bool(enabled_value),
                sync_status="ready",
                last_synced_at=datetime.now(timezone.utc).isoformat(),
            )
        conn.commit()
    return get_source(normalized)


def _bm25_score(query_terms: List[str], doc_terms: List[str], doc_freqs: Dict[str, int], corpus_size: int, avg_len: float) -> float:
    if not query_terms or not doc_terms:
        return 0.0
    frequencies = Counter(doc_terms)
    doc_len = max(1, len(doc_terms))
    k1 = 1.5
    b = 0.75
    score = 0.0
    for term in query_terms:
        frequency = frequencies.get(term, 0)
        if not frequency:
            continue
        doc_frequency = doc_freqs.get(term, 0)
        idf = math.log(1 + ((corpus_size - doc_frequency + 0.5) / (doc_frequency + 0.5)))
        denominator = frequency + k1 * (1 - b + b * (doc_len / max(1.0, avg_len)))
        score += idf * ((frequency * (k1 + 1)) / denominator)
    return score


def retrieve_context(query: str, limit: int = 4) -> List[dict]:
    query_tokens = search_tokens(query)
    query_vector = _vectorize(query_tokens)
    if not query_vector:
        return []

    with get_db() as conn:
        _repair_source_metadata(conn)
        rows = conn.execute(
            """
            SELECT
                chunks.content,
                chunks.chunk_index,
                chunks.token_count,
                documents.id AS document_id,
                documents.title,
                documents.tags,
                documents.source,
                documents.group_name,
                documents.core_persona,
                documents.source_url,
                documents.source_key,
                documents.updated_at
            FROM chunks
            JOIN documents ON documents.id = chunks.document_id
            WHERE documents.source_enabled = 1
            """
        ).fetchall()
        conn.commit()

    doc_terms_list: List[List[str]] = [search_tokens(str(row["content"])) for row in rows]

    doc_freqs: Dict[str, int] = Counter()
    for doc_terms in doc_terms_list:
        for token in set(doc_terms):
            doc_freqs[token] += 1
    avg_len = sum(len(terms) for terms in doc_terms_list) / max(1, len(doc_terms_list))

    scored: List[dict] = []
    lowered_query = " ".join(query.lower().split())
    for index, row in enumerate(rows):
        content = str(row["content"])
        title = str(row["title"])
        tags = [tag for tag in str(row["tags"]).split(",") if tag]
        content_tokens = doc_terms_list[index]
        title_tokens = search_tokens(title)
        tag_tokens = [token for tag in tags for token in search_tokens(tag)]
        combined_tokens = content_tokens + title_tokens + tag_tokens
        if not combined_tokens:
            continue
        cosine_score = _cosine_similarity(query_vector, _vectorize(combined_tokens))
        overlap_score = _token_overlap(query_tokens, combined_tokens)
        title_overlap = _token_overlap(query_tokens, title_tokens)
        tag_overlap = _token_overlap(query_tokens, tag_tokens)
        coverage = len(set(query_tokens).intersection(combined_tokens)) / max(1, len(set(query_tokens)))
        bm25_score = _bm25_score(query_tokens, content_tokens + title_tokens, doc_freqs, len(rows), avg_len)
        phrase_boost = 0.0
        if lowered_query and lowered_query in content.lower():
            phrase_boost += 0.55
        if lowered_query and lowered_query in title.lower():
            phrase_boost += 0.9
        domain_bonus = 0.0
        source_url = str(row["source_url"]) if row["source_url"] else None
        domain = source_domain(source_url)
        if domain and any(token in domain for token in query_tokens):
            domain_bonus = 0.18
        core_persona_bonus = 0.65 if bool(row["core_persona"]) and _persona_query_topic(query) else 0.0
        persona_bonus = _persona_document_bonus(query, title, tags, content)
        operational_adjustment = _operational_document_adjustment(query, title, tags, content)
        recency_bonus = 0.06 if str(row["updated_at"]).startswith(str(datetime.now(timezone.utc).year)) else 0.0
        score = (
            (bm25_score * 0.82)
            + (cosine_score * 0.48)
            + (overlap_score * 0.62)
            + (title_overlap * 0.6)
            + (tag_overlap * 0.4)
            + (coverage * 0.35)
            + phrase_boost
            + domain_bonus
            + core_persona_bonus
            + persona_bonus
            + operational_adjustment
            + recency_bonus
        )
        if score <= 0:
            continue
        scored.append(
            {
                "document_id": int(row["document_id"]),
                "title": title,
                "excerpt": _excerpt_for_query(content, query_tokens),
                "content": content,
                "tags": tags,
                "source": str(row["source"]),
                "group_name": str(row["group_name"] or ""),
                "core_persona": bool(row["core_persona"]),
                "source_url": source_url,
                "url": source_url,
                "kind": "knowledge",
                "score": round(score, 4),
                "chunk_index": int(row["chunk_index"]),
                "source_key": str(row["source_key"] or ""),
            }
        )

    ranked = sorted(scored, key=lambda item: item["score"], reverse=True)
    selected: List[dict] = []
    per_document_counts: Dict[int, int] = Counter()
    per_source_counts: Dict[str, int] = Counter()
    for item in ranked:
        if per_document_counts[item["document_id"]] >= 2:
            continue
        if item["source_key"] and per_source_counts[item["source_key"]] >= 3:
            continue
        selected.append(item)
        per_document_counts[item["document_id"]] += 1
        if item["source_key"]:
            per_source_counts[item["source_key"]] += 1
        if len(selected) >= limit:
            break
    return selected
