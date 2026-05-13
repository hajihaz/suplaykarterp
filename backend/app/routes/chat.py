from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user, get_optional_current_user
from app.schemas import (
    ChatCitation,
    ChatRequest,
    ChatResponse,
    ChatSessionResponse,
    ChatSessionSummary,
)
from app.services.anthropic_client import ai_service
from app.services.conversations import (
    append_chat_messages,
    delete_chat_session_for_user,
    ensure_chat_session,
    get_chat_session,
    list_chat_sessions,
)
from app.services.operations import record_usage_event
from app.services.orchestration import build_route_plan, filter_relevant_memories
from app.services.rag import retrieve_context


router = APIRouter(prefix="/chat", tags=["chat"])


def _serialize_citations(raw_items: list[dict]) -> list[ChatCitation]:
    return [
        ChatCitation(
            title=item["title"],
            excerpt=item["excerpt"],
            url=item.get("url"),
            kind=item.get("kind", "knowledge"),
            source=item.get("source"),
            group_name=item.get("group_name", ""),
        )
        for item in raw_items
    ]


def _record_chat_usage(
    message: str,
    answer: str,
    mode: str,
    citations: list[ChatCitation],
    notice: str | None,
    route: dict | None = None,
) -> None:
    provider_state = ai_service.status()
    route = route or {}
    record_usage_event(
        "chat",
        "/chat",
        mode=mode,
        prompt_length=len(message),
        answer_length=len(answer),
        citation_count=len(citations),
        provider=provider_state["provider"],
        metadata={
            "notice": notice or "",
            "intent": str(route.get("intent") or ""),
            "source_strategy": str(route.get("source_strategy") or ""),
            "memory_confidence": str(route.get("memory_confidence") or 0.0),
        },
    )


async def _build_chat_result(payload: ChatRequest, current_user: Optional[dict] = None) -> dict:
    history = [turn.model_dump() for turn in payload.history]
    if not history and payload.session_id:
        session_snapshot = get_chat_session(payload.session_id, user_id=int(current_user["id"]) if current_user else None)
        if session_snapshot:
            history = [
                {"role": message["role"], "content": message["content"]}
                for message in session_snapshot.get("messages", [])
                if message.get("role") in {"user", "assistant"} and message.get("content")
            ][-8:]
    route = build_route_plan(
        payload.message,
        history,
        answer_mode=payload.answer_mode,
        memory_enabled=payload.memory_enabled,
        ai_mode=payload.ai_mode,
    )
    contexts: list[dict] = []
    memory_confidence = 0.0
    if route.memory_allowed:
        raw_contexts = retrieve_context(route.memory_query, limit=8)
        contexts, memory_confidence = filter_relevant_memories(route, raw_contexts)
    route_payload = route.model_dump()
    route_payload["memory_confidence"] = memory_confidence
    model_history = history if route.include_history else []
    result = await ai_service.generate(
        payload.message,
        contexts,
        history=model_history,
        effective_prompt=route.effective_prompt,
        answer_mode=payload.answer_mode,
        route=route_payload,
    )
    citations = _serialize_citations(result["citations"])
    session = ensure_chat_session(
        payload.session_id,
        payload.message,
        payload.answer_mode,
        user_id=int(current_user["id"]) if current_user else None,
    )
    append_chat_messages(
        session["id"],
        [
            {"role": "user", "content": payload.message},
            {
                "role": "assistant",
                "content": result["answer"],
                "mode": result["mode"],
                "notice": result.get("notice"),
                "citations": [citation.model_dump() for citation in citations],
            },
        ],
        answer_mode=payload.answer_mode,
    )
    _record_chat_usage(payload.message, result["answer"], result["mode"], citations, result.get("notice"), route_payload)
    return {
        "answer": result["answer"],
        "citations": citations,
        "mode": result["mode"],
        "notice": result.get("notice"),
        "session_id": session["id"],
        "conversation_title": session["title"],
        "intent": route.intent,
        "source_strategy": route.source_strategy,
        "memory_confidence": memory_confidence,
    }


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, current_user: Optional[dict] = Depends(get_optional_current_user)) -> ChatResponse:
    result = await _build_chat_result(payload, current_user=current_user)
    return ChatResponse(**result)


@router.post("/stream")
async def chat_stream(payload: ChatRequest, current_user: Optional[dict] = Depends(get_optional_current_user)) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        yield _sse_event(
            "stage",
            {
                "status": "thinking",
                "message": "Thinking through your question...",
            },
        )
        await asyncio.sleep(0)
        try:
            result = await _build_chat_result(payload, current_user=current_user)
        except Exception as exc:  # pragma: no cover - handled in integration behavior
            yield _sse_event("error", {"detail": str(exc) or "Streaming failed"})
            return

        yield _sse_event(
            "session",
            {
                "session_id": result["session_id"],
                "conversation_title": result["conversation_title"],
            },
        )
        yield _sse_event(
            "meta",
            {
                "mode": result["mode"],
                "notice": result["notice"],
                "intent": result["intent"],
                "source_strategy": result["source_strategy"],
                "memory_confidence": result["memory_confidence"],
            },
        )

        words = result["answer"].split()
        chunk_size = 3 if len(words) > 18 else 2
        for index in range(0, len(words), chunk_size):
            chunk = " ".join(words[index : index + chunk_size])
            trailing_space = " " if index + chunk_size < len(words) else ""
            yield _sse_event("delta", {"text": f"{chunk}{trailing_space}"})
            await asyncio.sleep(0.03 if len(words) <= 48 else 0.02)

        yield _sse_event(
            "complete",
            {
                "answer": result["answer"],
                "citations": [citation.model_dump() for citation in result["citations"]],
                "mode": result["mode"],
                "notice": result["notice"],
                "session_id": result["session_id"],
                "conversation_title": result["conversation_title"],
                "intent": result["intent"],
                "source_strategy": result["source_strategy"],
                "memory_confidence": result["memory_confidence"],
            },
        )

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/session/{session_id}", response_model=ChatSessionResponse)
async def read_chat_session(session_id: str, current_user: Optional[dict] = Depends(get_optional_current_user)) -> ChatSessionResponse:
    session = get_chat_session(session_id, user_id=int(current_user["id"]) if current_user else None)
    if session is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return ChatSessionResponse(**session)


@router.get("/sessions", response_model=list[ChatSessionSummary])
async def read_user_chat_sessions(current_user: dict = Depends(get_current_user)) -> list[ChatSessionSummary]:
    sessions = list_chat_sessions(int(current_user["id"]))
    return [ChatSessionSummary(**item) for item in sessions]


@router.delete("/session/{session_id}")
async def remove_chat_session(session_id: str, current_user: Optional[dict] = Depends(get_optional_current_user)) -> dict:
    deleted = delete_chat_session_for_user(session_id, user_id=int(current_user["id"]) if current_user else None)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"deleted": True, "session_id": session_id}
