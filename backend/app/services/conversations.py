from __future__ import annotations

import json
import re
from typing import Iterable
from uuid import uuid4

from app.db import get_db
from app.schemas import ChatCitation
from app.services.response_builder import normalize_answer_mode


SESSION_ID_RE = re.compile(r"^[a-z0-9-]{12,64}$")


def _normalize_session_id(session_id: str | None) -> str:
    candidate = (session_id or "").strip().lower()
    if SESSION_ID_RE.fullmatch(candidate):
        return candidate
    return uuid4().hex


def _derive_title(message: str) -> str:
    cleaned = " ".join(message.split()).strip(" \n\t")
    if not cleaned:
        return "New conversation"
    cleaned = cleaned.rstrip("?.!")
    if len(cleaned) > 72:
        cleaned = f"{cleaned[:69].rstrip()}..."
    return cleaned or "New conversation"


def ensure_chat_session(session_id: str | None, title_seed: str, answer_mode: str = "balanced", user_id: int | None = None) -> dict:
    normalized_id = _normalize_session_id(session_id)
    normalized_mode = normalize_answer_mode(answer_mode)
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id, user_id, title, answer_mode, created_at, updated_at FROM chat_sessions WHERE id = ?",
            (normalized_id,),
        ).fetchone()
        if existing is not None:
            existing_user_id = existing["user_id"]
            if existing_user_id is not None and user_id is None:
                existing = None
                normalized_id = uuid4().hex
            elif existing_user_id is not None and user_id is not None and int(existing_user_id) != int(user_id):
                existing = None
                normalized_id = uuid4().hex
        if existing:
            title = existing["title"] or _derive_title(title_seed)
            conn.execute(
                """
                UPDATE chat_sessions
                SET user_id = COALESCE(user_id, ?), title = ?, answer_mode = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (user_id, title, normalized_mode, normalized_id),
            )
        else:
            title = _derive_title(title_seed)
            conn.execute(
                """
                INSERT INTO chat_sessions (id, user_id, title, answer_mode)
                VALUES (?, ?, ?, ?)
                """,
                (normalized_id, user_id, title, normalized_mode),
            )
        conn.commit()
        row = conn.execute(
            "SELECT id, user_id, title, answer_mode, created_at, updated_at FROM chat_sessions WHERE id = ?",
            (normalized_id,),
        ).fetchone()
    return dict(row) if row is not None else {
        "id": normalized_id,
        "user_id": user_id,
        "title": _derive_title(title_seed),
        "answer_mode": normalized_mode,
        "created_at": "",
        "updated_at": "",
    }


def append_chat_messages(
    session_id: str,
    messages: Iterable[dict],
    answer_mode: str = "balanced",
) -> None:
    normalized_mode = normalize_answer_mode(answer_mode)
    with get_db() as conn:
        for message in messages:
            role = str(message.get("role", "")).strip().lower()
            content = str(message.get("content", "")).strip()
            if role not in {"user", "assistant"} or not content:
                continue
            citations_json = json.dumps(message.get("citations", []), ensure_ascii=False)
            conn.execute(
                """
                INSERT INTO chat_messages (session_id, role, content, mode, notice, citations_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    role,
                    content,
                    str(message.get("mode", "")).strip(),
                    message.get("notice"),
                    citations_json,
                ),
            )
        conn.execute(
            """
            UPDATE chat_sessions
            SET answer_mode = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (normalized_mode, session_id),
        )
        conn.commit()


def get_chat_session(session_id: str, user_id: int | None = None) -> dict | None:
    normalized_id = _normalize_session_id(session_id)
    if normalized_id != session_id:
        return None

    with get_db() as conn:
        session = conn.execute(
            """
            SELECT id, user_id, title, answer_mode, created_at, updated_at
            FROM chat_sessions
            WHERE id = ?
            """,
            (normalized_id,),
        ).fetchone()
        if session is None:
            return None
        if session["user_id"] is not None and user_id is None:
            return None
        if session["user_id"] is not None and user_id is not None and int(session["user_id"]) != int(user_id):
            return None
        messages = conn.execute(
            """
            SELECT id, role, content, mode, notice, citations_json, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (normalized_id,),
        ).fetchall()

    parsed_messages = []
    for row in messages:
        citations = []
        try:
            raw_citations = json.loads(row["citations_json"] or "[]")
        except json.JSONDecodeError:
            raw_citations = []
        for item in raw_citations:
            citations.append(
                ChatCitation(
                    title=item.get("title", "Source"),
                    excerpt=item.get("excerpt", ""),
                    url=item.get("url"),
                    kind=item.get("kind", "knowledge"),
                    source=item.get("source"),
                    group_name=item.get("group_name", ""),
                ).model_dump()
            )
        parsed_messages.append(
            {
                "id": int(row["id"]),
                "role": row["role"],
                "content": row["content"],
                "mode": row["mode"] or "",
                "notice": row["notice"],
                "citations": citations,
                "created_at": row["created_at"],
            }
        )

    return {
        "session": {
            "id": session["id"],
            "title": session["title"],
            "answer_mode": session["answer_mode"] or "balanced",
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "message_count": len(parsed_messages),
        },
        "messages": parsed_messages,
    }


def delete_chat_session(session_id: str) -> bool:
    return delete_chat_session_for_user(session_id, None)


def delete_chat_session_for_user(session_id: str, user_id: int | None = None) -> bool:
    normalized_id = _normalize_session_id(session_id)
    if normalized_id != session_id:
        return False
    with get_db() as conn:
        existing = conn.execute("SELECT user_id FROM chat_sessions WHERE id = ?", (normalized_id,)).fetchone()
        if existing is None:
            return False
        if existing["user_id"] is not None and user_id is None:
            return False
        if existing["user_id"] is not None and user_id is not None and int(existing["user_id"]) != int(user_id):
            return False
        deleted = conn.execute("DELETE FROM chat_sessions WHERE id = ?", (normalized_id,)).rowcount > 0
        conn.commit()
    return deleted


def list_chat_sessions(user_id: int, limit: int = 20) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT
                chat_sessions.id,
                chat_sessions.title,
                chat_sessions.answer_mode,
                chat_sessions.created_at,
                chat_sessions.updated_at,
                COUNT(chat_messages.id) AS message_count
            FROM chat_sessions
            LEFT JOIN chat_messages ON chat_messages.session_id = chat_sessions.id
            WHERE chat_sessions.user_id = ?
            GROUP BY chat_sessions.id
            ORDER BY chat_sessions.updated_at DESC, chat_sessions.created_at DESC
            LIMIT ?
            """,
            (user_id, max(1, min(limit, 50))),
        ).fetchall()
    return [
        {
            "id": str(row["id"]),
            "title": str(row["title"] or "New conversation"),
            "answer_mode": str(row["answer_mode"] or "balanced"),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
            "message_count": int(row["message_count"] or 0),
        }
        for row in rows
    ]


def claim_chat_session(session_id: str | None, user_id: int) -> str | None:
    normalized_id = _normalize_session_id(session_id)
    if not session_id or normalized_id != session_id:
        return None
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, user_id FROM chat_sessions WHERE id = ?",
            (normalized_id,),
        ).fetchone()
        if row is None:
            return None
        if row["user_id"] is None:
            conn.execute(
                """
                UPDATE chat_sessions
                SET user_id = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (user_id, normalized_id),
            )
            conn.commit()
            return normalized_id
        if int(row["user_id"]) == int(user_id):
            return normalized_id
    return None
