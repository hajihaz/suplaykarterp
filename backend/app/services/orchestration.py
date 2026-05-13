from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Literal

from app.services.rag import search_tokens
from app.services.response_builder import expand_prompt_with_history, looks_conversational_prompt


IntentCategory = Literal[
    "conversation",
    "general_knowledge",
    "current_affairs",
    "personal_memory",
    "follow_up",
    "reasoning",
    "coding",
    "math",
    "creative_writing",
    "admin_system",
]
SourceStrategy = Literal["memory", "general", "web", "hybrid", "reasoning", "none"]
HistoryPolicy = Literal["none", "recent"]


PERSONAL_TERMS = {
    "haji",
    "hajihaz",
    "hajihaz ai",
    "syed hasan",
    "kuddos",
    "my",
    "me",
    "mine",
    "our",
    "ours",
}
RELATIONSHIP_TERMS = {
    "father",
    "mother",
    "wife",
    "husband",
    "partner",
    "brother",
    "sister",
    "son",
    "daughter",
    "family",
    "parents",
    "children",
    "grandfather",
    "grandmother",
}
BUSINESS_TERMS = {"business", "businesses", "company", "companies", "startup", "work", "run", "own", "owns"}
CURRENT_AFFAIRS_TERMS = {
    "current",
    "latest",
    "today",
    "now",
    "recent",
    "news",
    "prime minister",
    "pm of",
    "president",
    "chief minister",
    "governor",
    "minister",
    "election",
    "cabinet",
    "ceo",
}
POLITICS_HISTORY_SCIENCE_TERMS = {
    "prime minister",
    "president",
    "chief minister",
    "government",
    "parliament",
    "history",
    "science",
    "physics",
    "chemistry",
    "biology",
    "country",
    "capital",
    "state",
    "india",
    "tamil nadu",
}
CODING_TERMS = {
    "code",
    "debug",
    "function",
    "class",
    "api",
    "python",
    "javascript",
    "typescript",
    "react",
    "sql",
    "error",
    "stack trace",
}
CREATIVE_TERMS = {"write", "story", "poem", "caption", "script", "rewrite", "tagline", "creative"}
ADMIN_TERMS = {"admin", "settings", "login", "password", "dashboard", "backup", "document", "upload", "system"}
OPERATIONAL_TERMS = {
    "rag",
    "upload",
    "uploads",
    "document",
    "documents",
    "knowledge base",
    "pricing",
    "onboarding",
    "client",
    "customer",
    "workflow",
    "workflows",
    "support",
    "policy",
    "sop",
    "faq",
    "checklist",
    "proposal",
    "kickoff",
}
FOLLOW_UP_STARTERS = (
    "and ",
    "also ",
    "what about",
    "how about",
    "tell me more",
    "more about",
    "give details",
    "give me details",
    "give more details",
)
FOLLOW_UP_PRONOUNS = {"him", "her", "his", "their", "them", "that", "those", "it", "this"}
ANSWER_MODE_SET = {"balanced", "concise", "detailed", "strategic", "founder"}
AI_MODE_SET = {"auto", "general", "memory", "reasoning", "coding", "creative"}


@dataclass(frozen=True)
class ChatRoutePlan:
    intent: IntentCategory
    source_strategy: SourceStrategy
    effective_prompt: str
    memory_query: str
    memory_allowed: bool
    memory_required: bool
    memory_threshold: float
    memory_confidence: float = 0.0
    include_history: bool = False
    answer_mode: str = "balanced"
    ai_mode: str = "auto"
    reasons: list[str] = field(default_factory=list)

    def model_dump(self) -> dict:
        return asdict(self)


def normalize_ai_mode(value: str | None) -> str:
    normalized = " ".join(str(value or "").lower().split())
    return normalized if normalized in AI_MODE_SET else "auto"


def _normalized(text: str) -> str:
    return " ".join(str(text or "").lower().split()).strip()


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _looks_follow_up(prompt: str) -> bool:
    normalized = _normalized(prompt).strip(" ?!.,")
    if not normalized:
        return False
    if normalized.startswith(FOLLOW_UP_STARTERS):
        return True
    words = set(normalized.split())
    return len(words) <= 9 and bool(words.intersection(FOLLOW_UP_PRONOUNS))


def _history_is_personal(history: list[dict] | None) -> bool:
    if not history:
        return False
    recent = " ".join(_normalized(item.get("content", "")) for item in history[-6:])
    if _contains_any(recent, PERSONAL_TERMS.union(RELATIONSHIP_TERMS).union(BUSINESS_TERMS)):
        return True
    return "haji's" in recent or "hajis" in recent


def _looks_personal_memory_prompt(prompt: str) -> bool:
    normalized = _normalized(prompt)
    if "hajihaz ai" in normalized:
        return True
    if any(term in normalized for term in {"haji ", " haji", "haji's", "hajis", "syed hasan", "kuddos"}):
        return True
    memory_terms = "|".join(re.escape(term) for term in sorted(RELATIONSHIP_TERMS.union(BUSINESS_TERMS)))
    if re.search(r"\b(my|our)\s+(" + memory_terms + r")\b", normalized):
        return True
    if re.search(r"\b(what|which)\s+business(?:es)?\s+do\s+i\s+(?:run|own|have)\b", normalized):
        return True
    if re.search(r"\bwho\s+is\s+my\s+\w+", normalized):
        return True
    return False


def _looks_current_affairs(prompt: str) -> bool:
    normalized = _normalized(prompt)
    if _contains_any(normalized, CURRENT_AFFAIRS_TERMS):
        return True
    if re.search(r"\b(pm|cm)\s+of\s+[a-z][a-z ]+\b", normalized):
        return True
    return False


def _looks_named_memory_candidate(prompt: str) -> bool:
    # Public-style named entity questions are intentionally treated as general knowledge.
    # Memory should activate through explicit personal language ("my father",
    # "Haji's business") or a personal follow-up, not through a bare name match.
    return False


def _looks_math(prompt: str) -> bool:
    normalized = _normalized(prompt)
    if any(term in normalized for term in {"calculate", "solve", "equation", "percentage", "percent"}):
        return True
    return bool(re.search(r"\d+\s*[-+*/x×÷]\s*\d+", normalized))


def _classify_intent(prompt: str, history: list[dict] | None, ai_mode: str) -> tuple[IntentCategory, list[str]]:
    normalized = _normalized(prompt)
    reasons: list[str] = []

    if ai_mode == "coding":
        return "coding", ["ai_mode=coding"]
    if ai_mode == "creative":
        return "creative_writing", ["ai_mode=creative"]
    if ai_mode == "reasoning":
        return "reasoning", ["ai_mode=reasoning"]
    if ai_mode == "memory":
        reasons.append("ai_mode=memory")

    if looks_conversational_prompt(prompt):
        return "conversation", ["casual_conversation"]

    if _looks_follow_up(prompt) and history:
        reasons.append("follow_up_marker")
        if _history_is_personal(history):
            return "follow_up", [*reasons, "personal_recent_history"]
        return "follow_up", [*reasons, "general_recent_history"]

    if _looks_personal_memory_prompt(prompt):
        return "personal_memory", ["explicit_personal_memory"]

    if _looks_current_affairs(prompt):
        return "current_affairs", ["current_or_public_office_marker"]

    if _looks_math(prompt):
        return "math", ["math_marker"]

    if _contains_any(normalized, CODING_TERMS):
        return "coding", ["coding_marker"]

    if _contains_any(normalized, CREATIVE_TERMS) and not normalized.startswith(("what is ", "who is ")):
        return "creative_writing", ["creative_marker"]

    if _contains_any(normalized, ADMIN_TERMS) and _contains_any(normalized, {"admin", "settings", "dashboard", "backup", "upload"}):
        return "admin_system", ["admin_marker"]

    if normalized.startswith(("why ", "how ", "compare ", "analyze ", "explain ", "reason ")):
        return "reasoning", ["reasoning_marker"]

    return "general_knowledge", ["default_general"]


def _memory_query_for(prompt: str, effective_prompt: str, intent: IntentCategory) -> str:
    normalized = _normalized(effective_prompt)
    if intent in {"personal_memory", "follow_up"}:
        prefixes: list[str] = []
        if _contains_any(normalized, RELATIONSHIP_TERMS):
            prefixes.append("Haji family relationship")
        if _contains_any(normalized, BUSINESS_TERMS):
            prefixes.append("Haji business company portfolio")
        if any(term in normalized for term in {"education", "study", "college", "degree", "qualification"}):
            prefixes.append("Haji education qualification")
        if not prefixes:
            prefixes.append("Haji profile identity")
        return f"{' '.join(prefixes)} {effective_prompt}".strip()
    return effective_prompt or prompt


def _personal_effective_prompt(prompt: str, intent: IntentCategory) -> str:
    if intent != "personal_memory":
        return prompt
    normalized = _normalized(prompt)
    for relationship in sorted(RELATIONSHIP_TERMS, key=len, reverse=True):
        if re.search(rf"\bwho\s+is\s+my\s+{re.escape(relationship)}\b", normalized):
            return f"Who is Haji's {relationship}?"
        if re.search(rf"\bwhat\s+is\s+my\s+{re.escape(relationship)}\b", normalized):
            return f"What is Haji's {relationship}?"
    if re.search(r"\bwhat\s+business(?:es)?\s+do\s+i\s+(?:run|own|have)\b", normalized):
        return "What businesses does Haji run or own?"
    if re.search(r"\bwhat\s+(?:is|are)\s+my\s+business(?:es)?\b", normalized):
        return "What are Haji's businesses?"
    return prompt


def build_route_plan(
    prompt: str,
    history: list[dict] | None,
    *,
    answer_mode: str = "balanced",
    memory_enabled: bool = True,
    ai_mode: str = "auto",
) -> ChatRoutePlan:
    normalized_answer_mode = _normalized(answer_mode)
    if normalized_answer_mode not in ANSWER_MODE_SET:
        normalized_answer_mode = "balanced"
    normalized_ai_mode = normalize_ai_mode(ai_mode)
    intent, reasons = _classify_intent(prompt, history, normalized_ai_mode)
    effective_prompt = expand_prompt_with_history(prompt, history) if intent == "follow_up" else _personal_effective_prompt(prompt, intent)

    memory_allowed = False
    memory_required = False
    threshold = 0.32
    include_history = intent == "follow_up"
    strategy: SourceStrategy = "general"

    if intent == "conversation":
        strategy = "none"
    elif intent == "current_affairs":
        strategy = "web"
        reasons.append("memory_blocked_for_current_affairs")
    elif intent in {"coding", "math", "creative_writing", "admin_system"}:
        if intent == "admin_system" and _contains_any(_normalized(prompt), OPERATIONAL_TERMS):
            memory_allowed = memory_enabled
            strategy = "hybrid" if memory_enabled else "reasoning"
            threshold = 0.26
            reasons.append("operational_admin_request_can_use_memory")
        else:
            strategy = "reasoning" if intent != "creative_writing" else "general"
            reasons.append("memory_blocked_for_task_intent")
    elif intent == "reasoning":
        strategy = "reasoning"
        if _history_is_personal(history) and _looks_follow_up(prompt):
            memory_allowed = memory_enabled
            strategy = "hybrid"
            threshold = 0.38
        elif _contains_any(_normalized(prompt), OPERATIONAL_TERMS):
            memory_allowed = memory_enabled
            strategy = "hybrid" if memory_enabled else "reasoning"
            threshold = 0.28
            reasons.append("operational_reasoning_can_use_memory")
    elif intent == "personal_memory":
        memory_allowed = memory_enabled
        memory_required = memory_enabled
        strategy = "memory" if memory_enabled else "general"
        threshold = 0.18
    elif intent == "follow_up":
        if _history_is_personal(history):
            memory_allowed = memory_enabled
            strategy = "hybrid" if memory_enabled else "general"
            threshold = 0.24
        else:
            strategy = "general"
    else:
        if _looks_named_memory_candidate(prompt):
            memory_allowed = memory_enabled
            strategy = "hybrid" if memory_enabled else "web"
            threshold = 0.42
            reasons.append("high_confidence_memory_probe_for_named_entity")
        else:
            normalized_prompt = _normalized(prompt)
            strategy = "web" if (
                normalized_prompt.startswith(("who is ", "what is ", "who are ", "what are ", "where is ", "when is ", "define "))
                or _contains_any(normalized_prompt, POLITICS_HISTORY_SCIENCE_TERMS)
            ) else "general"
        reasons.append("memory_blocked_for_general_knowledge")

    if normalized_ai_mode == "general":
        memory_allowed = False
        memory_required = False
        strategy = "web" if intent in {"current_affairs", "general_knowledge"} else "general"
        reasons.append("ai_mode_general_blocks_memory")
    elif normalized_ai_mode == "memory" and intent not in {"current_affairs", "general_knowledge", "coding", "math"}:
        memory_allowed = memory_enabled
        memory_required = memory_enabled and intent in {"personal_memory", "follow_up"}
        strategy = "memory" if memory_required else "hybrid"
        threshold = min(threshold, 0.2)

    if not memory_enabled:
        memory_allowed = False
        memory_required = False
        reasons.append("memory_disabled_by_user")

    memory_query = _memory_query_for(prompt, effective_prompt, intent)
    return ChatRoutePlan(
        intent=intent,
        source_strategy=strategy,
        effective_prompt=effective_prompt,
        memory_query=memory_query,
        memory_allowed=memory_allowed,
        memory_required=memory_required,
        memory_threshold=threshold,
        include_history=include_history,
        answer_mode=normalized_answer_mode,
        ai_mode=normalized_ai_mode,
        reasons=reasons,
    )


def _context_text(context: dict) -> str:
    tags = " ".join(str(tag) for tag in context.get("tags", []))
    return " ".join(
        [
            str(context.get("title", "")),
            tags,
            str(context.get("group_name", "")),
            str(context.get("content", ""))[:1600],
        ]
    )


def score_memory_relevance(plan: ChatRoutePlan, context: dict) -> float:
    query_tokens = search_tokens(plan.memory_query)
    if not query_tokens:
        return 0.0
    context_tokens = search_tokens(_context_text(context))
    if not context_tokens:
        return 0.0

    query_set = set(query_tokens)
    context_set = set(context_tokens)
    overlap = len(query_set.intersection(context_set)) / max(1, len(query_set))
    title_tokens = set(search_tokens(str(context.get("title", ""))))
    tag_tokens = {
        token
        for tag in context.get("tags", [])
        for token in search_tokens(str(tag))
    }
    title_overlap = len(query_set.intersection(title_tokens)) / max(1, len(query_set))
    tag_overlap = len(query_set.intersection(tag_tokens)) / max(1, len(query_set))
    retrieval_score = min(1.0, float(context.get("score", 0.0)) / 2.5)
    core_boost = 0.16 if context.get("core_persona") and plan.intent in {"personal_memory", "follow_up"} else 0.0

    relation_boost = 0.0
    lower_context = _normalized(_context_text(context))
    if _contains_any(plan.memory_query.lower(), RELATIONSHIP_TERMS) and _contains_any(lower_context, RELATIONSHIP_TERMS):
        relation_boost += 0.12
    if _contains_any(plan.memory_query.lower(), BUSINESS_TERMS) and _contains_any(lower_context, BUSINESS_TERMS):
        relation_boost += 0.1

    score = (
        overlap * 0.44
        + title_overlap * 0.2
        + tag_overlap * 0.14
        + retrieval_score * 0.18
        + core_boost
        + relation_boost
    )
    memory_probe_reason = any(
        reason in plan.reasons
        for reason in {
            "high_confidence_memory_probe_for_named_entity",
            "operational_admin_request_can_use_memory",
            "operational_reasoning_can_use_memory",
        }
    )
    if plan.intent not in {"personal_memory", "follow_up"} and not memory_probe_reason:
        score -= 0.28
    return max(0.0, min(1.0, score))


def filter_relevant_memories(plan: ChatRoutePlan, contexts: list[dict], *, limit: int = 4) -> tuple[list[dict], float]:
    if not plan.memory_allowed or not contexts:
        return [], 0.0

    scored: list[tuple[float, dict]] = []
    for context in contexts:
        score = score_memory_relevance(plan, context)
        if score < plan.memory_threshold:
            continue
        enriched = dict(context)
        enriched["memory_score"] = round(score, 4)
        enriched["memory_confidence"] = "high" if score >= 0.68 else "medium" if score >= 0.42 else "low"
        scored.append((score, enriched))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [context for _score, context in scored[:limit]]
    confidence = scored[0][0] if scored else 0.0
    return selected, round(confidence, 4)
