from __future__ import annotations

import re
from collections import Counter
from hashlib import sha1
from typing import Iterable, List

from app.services.rag import tokenize


STOPWORDS = {
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
    "if",
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
    "should",
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
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")
PERSONA_IDENTIFIERS = {
    "haji",
    "hajihaz",
    "hajihaz ai",
    "syed hasan",
    "syed hasan kuddos",
    "kuddos sahib",
}
PERSONA_BUSINESS_MARKERS = {
    "business",
    "businesses",
    "business owner",
    "company",
    "companies",
    "venture",
    "ventures",
    "own",
    "owns",
    "owner",
    "portfolio",
    "focus",
}
PERSONA_EDUCATION_MARKERS = {
    "education",
    "qualifications",
    "qualification",
    "study",
    "studied",
    "degree",
    "degrees",
    "school",
    "college",
    "university",
    "certification",
    "certifications",
}
PERSONA_AI_MARKERS = {
    "hajihaz ai",
    "what can it do",
    "can it do",
    "what does it do",
    "what is hajihaz ai",
    "assistant",
    "system",
    "purpose",
}
PERSONA_RELATIONSHIP_MARKERS = {
    "friend",
    "friends",
    "wife",
    "husband",
    "partner",
    "father",
    "mother",
    "parents",
    "parent",
    "brother",
    "sister",
    "siblings",
    "sibling",
    "son",
    "daughter",
    "children",
    "child",
    "family",
    "grandfather",
    "grandmother",
    "grandparents",
    "maternal",
    "paternal",
    "girlfriend",
    "boyfriend",
}
PERSONA_RELATIONSHIP_SUBJECTS = {
    "mother": "mother",
    "father": "father",
    "wife": "wife",
    "husband": "husband",
    "partner": "partner",
    "brother": "brother",
    "sister": "sister",
    "son": "son",
    "daughter": "daughter",
    "child": "child",
    "children": "children",
    "parent": "parent",
    "parents": "parents",
}
FAMILY_RELATION_LABEL_PATTERN = (
    r"(?:mother|father|wife|husband|partner|brother|sister|son|daughter|parent|parents|child|children|"
    r"grandfather(?:\s*\((?:maternal|paternal)\))?|grandmother(?:\s*\((?:maternal|paternal)\))?|"
    r"maternal grandfather|maternal grandmother|paternal grandfather|paternal grandmother)"
)
FAMILY_ENTRY_RE = re.compile(
    rf"(?P<label>{FAMILY_RELATION_LABEL_PATTERN})\s+name\s*[:\-]\s*(?P<name>[A-Z][A-Za-z .'-]+?)"
    r"(?=\s+(?:nickname|nick\s*name|role|contribution|relationship(?: with haji)?|details|date of birth|influence|qualification)\b|$)",
    flags=re.IGNORECASE,
)
FAMILY_FIELD_LABEL_PATTERN = (
    r"(?:nickname|nick\s*name|role|contribution|relationship(?: with haji)?|details|date of birth|influence|qualification)"
)
FAMILY_ENTRY_START_PATTERN = rf"(?:{FAMILY_RELATION_LABEL_PATTERN})\s+name\s*[:\-]"
PERSONA_PROMPT_FILLER_TERMS = {
    "about",
    "tell",
    "name",
    "details",
    "detail",
    "person",
    "people",
    "full",
    "full name",
    "called",
    "known",
    "know",
    "based",
    "his",
    "her",
    "their",
    "he",
    "she",
    "they",
    "does",
    "did",
    "own",
    "owns",
}
PERSONA_DOC_KEYWORDS = {
    "haji",
    "hajihaz",
    "profile",
    "identity",
    "about",
    "bio",
    "biography",
    "background",
    "personality",
    "syed",
    "hasan",
    "kuddos",
}
PERSONA_BUSINESS_DOC_KEYWORDS = {
    "business",
    "businesses",
    "company",
    "companies",
    "venture",
    "ventures",
    "brand",
    "brands",
    "portfolio",
    "owns",
    "owner",
    "suplaykart",
}
PERSONA_EDUCATION_DOC_KEYWORDS = {
    "education",
    "qualification",
    "qualifications",
    "degree",
    "degrees",
    "school",
    "college",
    "university",
    "study",
    "studied",
    "certification",
}
PERSONA_AI_DOC_KEYWORDS = {
    "hajihaz ai",
    "assistant",
    "system",
    "purpose",
    "capability",
    "capabilities",
    "help",
    "workflow",
}
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
CASUAL_GREETING_PREFIXES = (
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
)
CASUAL_CHECKIN_PHRASES = {
    "how are you",
    "how are you doing",
    "how are you macha",
    "how are you today",
    "how r you",
    "how's it going",
    "hows it going",
    "what's up",
    "whats up",
    "you there",
    "are you there",
}
CASUAL_THANKS_PREFIXES = (
    "thanks",
    "thank you",
    "ok thanks",
    "okay thanks",
    "cool thanks",
)
CASUAL_SIGNOFF_PREFIXES = (
    "bye",
    "goodbye",
    "see you",
    "take care",
    "good night",
)
FOLLOW_UP_STARTERS = (
    "and ",
    "what about",
    "what else",
    "how about",
    "tell me more",
    "more on",
    "and his",
    "and her",
    "and their",
    "and the",
)
FOLLOW_UP_REFERENCE_MARKERS = {
    "his",
    "her",
    "him",
    "their",
    "that",
    "those",
    "it",
    "them",
    "he",
    "she",
}
KNOWLEDGE_ENTITY_FOLLOW_UP_MARKERS = {
    "her",
    "him",
    "them",
    "that person",
    "that one",
}
ANSWER_MODE_SET = {"balanced", "concise", "detailed", "strategic", "founder"}


def _keywords(text: str) -> List[str]:
    return [token for token in tokenize(text) if len(token) > 2 and token not in STOPWORDS]


def _tokens_match(left: str, right: str) -> bool:
    if left == right:
        return True
    shorter, longer = sorted((left, right), key=len)
    return len(shorter) >= 4 and longer.startswith(shorter)


def _split_sentences(text: str) -> List[str]:
    return [" ".join(sentence.split()).strip() for sentence in SENTENCE_RE.split(text) if sentence.strip()]


def _normalize_prompt(text: str) -> str:
    return " ".join(text.lower().split())


def _clean_family_field_value(value: str) -> str:
    cleaned = value.strip(" ,.-")
    cleaned = re.sub(r"\s*-\s*", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.-")
    return cleaned


def _split_family_role_fragments(value: str) -> List[str]:
    cleaned = _clean_family_field_value(value)
    if not cleaned:
        return []
    cleaned = re.sub(r"\s+(?=(?:Acts|Provides|Supports|Invested|Part of)\b)", ". ", cleaned)
    return [part.rstrip(".") for part in _split_sentences(cleaned) if part.strip()]


def _normalize_family_relationship_label(label: str, relationship: str = "") -> str:
    normalized_label = _normalize_prompt(label).strip()
    normalized_relationship = _normalize_prompt(relationship).strip()

    relationship_map = {
        "mother's father": "maternal grandfather",
        "mothers father": "maternal grandfather",
        "mother's mother": "maternal grandmother",
        "mothers mother": "maternal grandmother",
        "father's father": "paternal grandfather",
        "fathers father": "paternal grandfather",
        "father's mother": "paternal grandmother",
        "fathers mother": "paternal grandmother",
    }
    for marker, subject in relationship_map.items():
        if marker in normalized_relationship:
            return subject

    if "grandfather" in normalized_label and "maternal" in normalized_label:
        return "maternal grandfather"
    if "grandmother" in normalized_label and "maternal" in normalized_label:
        return "maternal grandmother"
    if "grandfather" in normalized_label and "paternal" in normalized_label:
        return "paternal grandfather"
    if "grandmother" in normalized_label and "paternal" in normalized_label:
        return "paternal grandmother"
    return normalized_label


def _extract_named_family_entries(contexts: List[dict]) -> List[dict]:
    stop_pattern = rf"(?=\s+(?:{FAMILY_FIELD_LABEL_PATTERN})\b|\s+{FAMILY_ENTRY_START_PATTERN}|$)"
    field_patterns = {
        "nickname": rf"(?:nickname|nick\s*name)\s*[:\-]\s*(.+?){stop_pattern}",
        "role": rf"role\s*[:\-]\s*(.+?){stop_pattern}",
        "contribution": rf"contribution\s*[:\-]\s*(.+?){stop_pattern}",
        "relationship": rf"relationship(?: with haji)?\s*[:\-]\s*(.+?){stop_pattern}",
        "details": rf"details\s*[:\-]\s*(.+?){stop_pattern}",
        "date_of_birth": rf"date of birth\s*[:\-]\s*(.+?){stop_pattern}",
        "influence": rf"influence\s*[:\-]\s*(.+?){stop_pattern}",
        "qualification": rf"qualification\s*[:\-]\s*(.+?){stop_pattern}",
    }
    entries: List[dict] = []
    for context in contexts:
        content = str(context.get("content", ""))
        if not content:
            continue
        normalized = re.sub(r"\s{2,}", " ", content.replace("---", " ").replace("\n", " "))
        matches = list(FAMILY_ENTRY_RE.finditer(normalized))
        for index, match in enumerate(matches):
            segment_start = match.start()
            segment_end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
            segment = normalized[segment_start:segment_end]
            raw_label = _clean_family_field_value(match.group("label"))
            name = _clean_family_field_value(match.group("name"))
            details: dict[str, str] = {}
            for key, pattern in field_patterns.items():
                field_match = re.search(pattern, segment, flags=re.IGNORECASE)
                if not field_match:
                    continue
                value = _clean_family_field_value(field_match.group(1))
                if value:
                    details[key] = value
            entries.append(
                {
                    "subject": _normalize_family_relationship_label(raw_label, details.get("relationship", "")),
                    "raw_label": raw_label,
                    "name": name,
                    "details": details,
                    "segment": segment,
                    "context": context,
                }
            )
    return entries


def conversational_prompt_intent(prompt: str) -> str | None:
    normalized = _normalize_prompt(prompt).strip(" ?!.,")
    if not normalized:
        return None

    word_count = len(normalized.split())
    if word_count > 10:
        return None

    if any(phrase in normalized for phrase in CASUAL_CHECKIN_PHRASES):
        return "checkin"

    if normalized.startswith(CASUAL_THANKS_PREFIXES):
        return "thanks"

    if normalized.startswith(CASUAL_SIGNOFF_PREFIXES):
        return "signoff"

    if normalized in {"yo", "sup", "hello macha", "hey macha", "hi macha"}:
        return "greeting"

    if normalized.startswith(CASUAL_GREETING_PREFIXES):
        return "greeting"

    return None


def looks_conversational_prompt(prompt: str) -> bool:
    return conversational_prompt_intent(prompt) is not None


def normalize_answer_mode(answer_mode: str | None) -> str:
    normalized = _normalize_prompt(answer_mode or "")
    return normalized if normalized in ANSWER_MODE_SET else "balanced"


def build_conversational_answer(prompt: str, answer_mode: str = "balanced") -> str:
    intent = conversational_prompt_intent(prompt) or "greeting"
    answer_mode = normalize_answer_mode(answer_mode)
    direct_address = " macha" if "macha" in _normalize_prompt(prompt) else ""
    variations = {
        "checkin": [
            f"Yep, I'm doing well{direct_address} and ready to help. What do you need me to assist with?",
            f"I'm doing well{direct_address} and fully here with you. What do you want help with right now?",
            f"Doing well{direct_address}. Tell me what you want to work through and I'll help.",
            f"All good here{direct_address}. I'm ready whenever you want to dive into something."
        ],
        "thanks": [
            f"Always{direct_address}. Happy to help. What do you want to do next?",
            f"You're welcome{direct_address}. I'm here whenever you want to keep going.",
            f"Anytime{direct_address}. Just tell me the next thing you want help with.",
            f"Glad that helped{direct_address}. We can keep going whenever you're ready."
        ],
        "signoff": [
            f"Anytime{direct_address}. Come back when you're ready and we'll pick it up from there.",
            f"Take care{direct_address}. I'm here when you need me again.",
            f"All good{direct_address}. Come back anytime and we'll continue from there.",
            f"Sounds good{direct_address}. I'll be here when you want to pick this back up."
        ],
        "greeting": [
            f"Hey{direct_address}, I'm here and ready. What do you want help with today?",
            f"Hello{direct_address}. I'm ready when you are. What shall we work on?",
            f"Hey{direct_address}. Good to see you. What do you need help with?",
            f"Hey{direct_address}. I'm with you. Tell me what you want to sort out."
        ],
    }
    pool = variations.get(intent, variations["greeting"])
    selection = int(sha1(_normalize_prompt(prompt).encode("utf-8")).hexdigest(), 16) % len(pool)
    answer = pool[selection]
    if answer_mode == "founder" and intent in {"greeting", "checkin"}:
        return f"{answer} We can keep it practical and move fast."
    if answer_mode == "concise":
        return answer.split(". ")[0].strip().rstrip(".") + "."
    return answer


def _history_items(history: List[dict] | None) -> List[dict]:
    if not history:
        return []
    cleaned: List[dict] = []
    for item in history[-8:]:
        role = str(item.get("role", "")).strip().lower()
        content = " ".join(str(item.get("content", "")).split()).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        cleaned.append({"role": role, "content": content})
    return cleaned


def _recent_user_messages(history: List[dict] | None, limit: int = 3) -> List[str]:
    items = [item["content"] for item in _history_items(history) if item["role"] == "user"]
    return items[-limit:]


def _recent_assistant_messages(history: List[dict] | None, limit: int = 2) -> List[str]:
    items = [item["content"] for item in _history_items(history) if item["role"] == "assistant"]
    return items[-limit:]


def _looks_follow_up_prompt(prompt: str) -> bool:
    normalized = _normalize_prompt(prompt).strip(" ?!.,")
    if not normalized:
        return False
    if normalized.startswith(FOLLOW_UP_STARTERS):
        return True
    if normalized in {
        "more details",
        "details",
        "detail",
        "tell me details",
        "give details",
        "give me details",
        "give more details",
    }:
        return True
    words = normalized.split()
    if len(words) <= 8 and any(marker in words for marker in FOLLOW_UP_REFERENCE_MARKERS):
        return True
    return normalized in {"what about that", "what about him", "what about her", "and then", "and now"}


def _infer_history_topic(history: List[dict] | None) -> str | None:
    recent_messages = [*_recent_user_messages(history, limit=3), *_recent_assistant_messages(history, limit=2)]
    for message in reversed(recent_messages):
        topic = persona_question_topic(message)
        if topic:
            return topic
    normalized_history = " ".join(_normalize_prompt(message) for message in recent_messages)
    if any(marker in normalized_history for marker in PERSONA_EDUCATION_MARKERS):
        return "education"
    if any(marker in normalized_history for marker in PERSONA_BUSINESS_MARKERS):
        return "business"
    if any(marker in normalized_history for marker in PERSONA_AI_MARKERS):
        return "ai"
    if any(marker in normalized_history for marker in PERSONA_IDENTIFIERS):
        return "identity"
    return None


def _follow_up_topic_hint(prompt: str) -> str | None:
    normalized = _normalize_prompt(prompt)
    if any(marker in normalized for marker in PERSONA_EDUCATION_MARKERS):
        return "education"
    if any(marker in normalized for marker in PERSONA_BUSINESS_MARKERS):
        return "business"
    if any(marker in normalized for marker in PERSONA_AI_MARKERS):
        return "ai"
    return None


def _infer_recent_knowledge_owned_entity(history: List[dict] | None) -> str | None:
    recent_messages = [*_recent_assistant_messages(history, limit=2), *_recent_user_messages(history, limit=2)]
    patterns = (
        r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})\s+is\s+Haji's\s+(?:mother|father|wife|husband|partner|brother|sister|son|daughter|parent|grandfather|grandmother|maternal grandfather|maternal grandmother|paternal grandfather|paternal grandmother)\b",
        r"\bHaji's\s+(?:mother|father|wife|husband|partner|brother|sister|son|daughter|parent|grandfather|grandmother|maternal grandfather|maternal grandmother|paternal grandfather|paternal grandmother)\s+is\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})\b",
        r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})\s+is\s+the\s+person\s+this\s+assistant\s+represents\b",
    )
    for message in recent_messages:
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(1).strip()
    return None


def _looks_entity_detail_follow_up(prompt: str) -> bool:
    normalized = _normalize_prompt(prompt)
    if not _looks_follow_up_prompt(prompt):
        return False
    has_reference_marker = any(marker in normalized for marker in KNOWLEDGE_ENTITY_FOLLOW_UP_MARKERS)
    detail_only_followups = {
        "more details",
        "details",
        "detail",
        "tell me more",
        "give more details",
        "give details",
        "give me details",
    }
    if not has_reference_marker and normalized not in detail_only_followups:
        return False
    return any(
        phrase in normalized
        for phrase in {
            "details",
            "detail",
            "tell me more",
            "more about",
            "who is she",
            "who is he",
            "about her",
            "about him",
            "about them",
        }
    ) or normalized.startswith(("give me details", "tell me details", "what about"))


def _looks_entity_detail_prompt(prompt: str) -> bool:
    normalized = _normalize_prompt(prompt)
    return any(
        phrase in normalized
        for phrase in {
            "details",
            "detail",
            "tell me more",
            "more about",
            "about her",
            "about him",
            "about them",
            "role",
            "contribution",
            "relationship with",
        }
    ) or normalized.startswith(
        (
            "give more details",
            "give me details",
            "tell me details",
            "tell me more",
            "what about",
        )
    )


def expand_prompt_with_history(prompt: str, history: List[dict] | None = None) -> str:
    recent_user_messages = _recent_user_messages(history)
    if not recent_user_messages:
        return prompt

    if not _looks_follow_up_prompt(prompt):
        return prompt

    recent_entity = _infer_recent_knowledge_owned_entity(history)
    if recent_entity and _looks_entity_detail_follow_up(prompt):
        return f"Give more details about {recent_entity}."

    latest_topic_prompt = recent_user_messages[-1]
    history_topic = _follow_up_topic_hint(prompt) or _infer_history_topic(history)
    if looks_persona_question(latest_topic_prompt) or history_topic in {"identity", "business", "education", "ai"}:
        normalized_prompt = _normalize_prompt(prompt)
        if "haji" in normalized_prompt or "hajihaz ai" in normalized_prompt:
            return prompt
        if history_topic == "education":
            return f"About Haji's education and qualifications, {prompt}"
        if history_topic == "business":
            return f"About Haji's businesses and work, {prompt}"
        if history_topic == "ai":
            return f"About HajiHaz AI, {prompt}"
        return f"About Haji, {prompt}"

    if _looks_personal_or_internal(latest_topic_prompt):
        return f"In the context of our previous discussion, {prompt}"

    return prompt


def build_history_block(history: List[dict] | None, limit: int = 4) -> str:
    items = _history_items(history)
    if not items:
        return ""
    lines = []
    for item in items[-limit:]:
        role_label = "User" if item["role"] == "user" else "Assistant"
        lines.append(f"{role_label}: {item['content']}")
    return "\n".join(lines)


def persona_question_topic(prompt: str) -> str | None:
    normalized = _normalize_prompt(prompt)
    if "hajihaz ai" in normalized:
        return "ai"

    about_haji = any(marker in normalized for marker in PERSONA_IDENTIFIERS)
    if not about_haji:
        return None
    if any(marker in normalized for marker in PERSONA_EDUCATION_MARKERS):
        return "education"
    if any(marker in normalized for marker in PERSONA_BUSINESS_MARKERS):
        return "business"
    if any(marker in normalized for marker in PERSONA_AI_MARKERS):
        return "ai"
    return "identity"


def looks_persona_question(prompt: str) -> bool:
    return persona_question_topic(prompt) is not None


def _persona_doc_keyword_sets(topic: str) -> tuple[set[str], set[str]]:
    topic_keywords = {
        "identity": PERSONA_DOC_KEYWORDS,
        "business": PERSONA_BUSINESS_DOC_KEYWORDS,
        "education": PERSONA_EDUCATION_DOC_KEYWORDS,
        "ai": PERSONA_AI_DOC_KEYWORDS,
    }.get(topic, set())
    return PERSONA_DOC_KEYWORDS, topic_keywords


def _persona_context_rank(prompt: str, context: dict) -> float:
    topic = persona_question_topic(prompt)
    if not topic:
        return 0.0

    title = str(context.get("title", "")).lower()
    content = str(context.get("content", "")).lower()
    tags = " ".join(str(tag).lower() for tag in context.get("tags", []))
    haystack = f"{title} {tags} {content}"
    base_terms, topic_terms = _persona_doc_keyword_sets(topic)
    base_hits = sum(1 for keyword in base_terms if keyword in haystack)
    topic_hits = sum(1 for keyword in topic_terms if keyword in haystack)
    prompt_phrase = _normalize_prompt(prompt)
    exact_phrase = int(bool(prompt_phrase and (prompt_phrase in title or prompt_phrase in content)))
    title_boost = 1 if any(keyword in title for keyword in topic_terms.union(base_terms)) else 0
    tag_boost = 1 if any(keyword in tags for keyword in topic_terms.union(base_terms)) else 0
    base_score = float(context.get("score", 0.0))
    return (
        base_score
        + (base_hits * 0.3)
        + (topic_hits * 0.46)
        + (title_boost * 0.2)
        + (tag_boost * 0.12)
        + (exact_phrase * 0.6)
    )


def _persona_focus_terms(prompt: str) -> List[str]:
    topic = persona_question_topic(prompt)
    if not topic:
        return []

    prompt_keywords = _keywords(prompt)
    identifier_terms = {
        token
        for phrase in PERSONA_IDENTIFIERS.union(PERSONA_AI_MARKERS)
        for token in _keywords(phrase)
    }
    filler_terms = {
        token
        for phrase in PERSONA_PROMPT_FILLER_TERMS
        for token in _keywords(phrase)
    }
    topic_terms = {
        "identity": set(),
        "business": {token for phrase in PERSONA_BUSINESS_MARKERS for token in _keywords(phrase)},
        "education": {token for phrase in PERSONA_EDUCATION_MARKERS for token in _keywords(phrase)},
        "ai": {token for phrase in PERSONA_AI_MARKERS for token in _keywords(phrase)},
    }.get(topic, set())

    return [
        token
        for token in prompt_keywords
        if token not in identifier_terms and token not in filler_terms and token not in topic_terms
    ]


def persona_prompt_has_supported_context(prompt: str, contexts: List[dict]) -> bool:
    topic = persona_question_topic(prompt)
    if not topic:
        return False
    if not contexts:
        return False

    focus_terms = _persona_focus_terms(prompt)
    if not focus_terms:
        return True

    for context in contexts:
        title = str(context.get("title", ""))
        content = str(context.get("content", ""))
        tags = " ".join(str(tag) for tag in context.get("tags", []))
        haystack_tokens = set(_keywords(f"{title} {tags} {content}"))
        if any(any(_tokens_match(term, token) for token in haystack_tokens) for term in focus_terms):
            return True
    return False


def _persona_unknown_answer(prompt: str, answer_mode: str = "balanced") -> str:
    answer_mode = normalize_answer_mode(answer_mode)
    lower = _normalize_prompt(prompt)
    if any(marker in lower for marker in PERSONA_RELATIONSHIP_MARKERS):
        answer = "I don't know that from Haji's saved knowledge right now."
    elif persona_question_topic(prompt) == "business":
        answer = "I don't know that from Haji's saved business knowledge right now."
    elif persona_question_topic(prompt) == "education":
        answer = "I don't know that from Haji's saved education knowledge right now."
    elif persona_question_topic(prompt) == "ai":
        answer = "I don't know that from the saved HajiHaz AI notes right now."
    else:
        answer = "I don't know that from Haji's saved knowledge right now."

    return _founder_tone_prefix(answer) if answer_mode == "founder" else answer


def _persona_relationship_subject(prompt: str) -> str | None:
    lower = _normalize_prompt(prompt)
    for marker, subject in PERSONA_RELATIONSHIP_SUBJECTS.items():
        if marker in lower:
            return subject
    return None


def _relationship_subject_by_entity(entity_hint: str, contexts: List[dict]) -> tuple[str, str] | None:
    entity_tokens = _keywords(entity_hint)
    if not entity_tokens:
        return None

    for entry in _extract_named_family_entries(contexts):
        name_tokens = set(_keywords(entry["name"]))
        if entity_tokens and all(any(_tokens_match(token, candidate) for candidate in name_tokens) for token in entity_tokens):
            return entry["subject"], entry["name"]

    for subject in PERSONA_RELATIONSHIP_SUBJECTS.values():
        name = _extract_persona_relationship_name(subject, contexts)
        if not name:
            continue
        name_tokens = set(_keywords(name))
        if entity_tokens and all(any(_tokens_match(token, candidate) for candidate in name_tokens) for token in entity_tokens):
            return subject, name
    return None


def _entity_named_contexts(entity_hint: str, contexts: List[dict]) -> List[dict]:
    entity_tokens = _keywords(entity_hint)
    if not entity_tokens:
        return []

    scored: List[tuple[float, dict]] = []
    for context in contexts:
        title = str(context.get("title", "")).lower()
        tags = " ".join(str(tag).lower() for tag in context.get("tags", []))
        content = str(context.get("content", "")).lower()
        haystack = f"{title} {tags} {content}"
        token_hits = sum(1 for token in entity_tokens if token in haystack)
        title_hits = sum(1 for token in entity_tokens if token in title)
        tag_hits = sum(1 for token in entity_tokens if token in tags)
        persona_hits = sum(1 for keyword in PERSONA_RELATIONSHIP_MARKERS if keyword in haystack)
        field_hits = int("name:" in content or "relationship with haji" in content)
        score = (
            float(context.get("score", 0.0))
            + token_hits * 0.8
            + title_hits * 0.35
            + tag_hits * 0.22
            + persona_hits * 0.18
            + field_hits * 0.22
        )
        if token_hits:
            scored.append((score, context))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [context for _score, context in scored]


def _extract_persona_relationship_name(subject: str, contexts: List[dict]) -> str | None:
    normalized_subject = _normalize_family_relationship_label(subject)
    for entry in _extract_named_family_entries(contexts):
        if entry["subject"] == normalized_subject and entry["name"]:
            return entry["name"]

    patterns = (
        rf"\b{re.escape(subject)}\s+name\s*[:\-]\s*([A-Z][A-Za-z .'-]+?)(?=\s+(?:role|contribution|relationship|nickname|nick\s*name)\b|[,\n]|$)",
        rf"\b{re.escape(subject)}\b\s*[:\-]\s*([A-Z][A-Za-z .'-]+?)(?=\s+(?:role|contribution|relationship|nickname|nick\s*name)\b|[,\n]|$)",
    )
    for context in contexts:
        haystacks = [
            str(context.get("content", "")),
            str(context.get("excerpt", "")),
            str(context.get("title", "")),
        ]
        for haystack in haystacks:
            if not haystack:
                continue
            normalized = haystack.replace("---", "\n")
            for pattern in patterns:
                match = re.search(pattern, normalized, flags=re.IGNORECASE)
                if match:
                    candidate = re.sub(r"\s{2,}", " ", match.group(1)).strip(" ,.-")
                    if len(candidate) >= 3:
                        return candidate
    return None


def _extract_persona_relationship_detail_fields(subject: str, contexts: List[dict]) -> dict[str, str]:
    normalized_subject = _normalize_family_relationship_label(subject)
    matched_entries = [entry for entry in _extract_named_family_entries(contexts) if entry["subject"] == normalized_subject]
    if matched_entries:
        merged_details: dict[str, str] = {}
        for entry in matched_entries:
            details = dict(entry["details"])
            if entry.get("name") and "name" not in details:
                details["name"] = entry["name"]
            for key, value in details.items():
                cleaned_value = _clean_family_field_value(value)
                if not cleaned_value:
                    continue
                existing = merged_details.get(key, "")
                if not existing or len(cleaned_value) > len(existing):
                    merged_details[key] = cleaned_value
        return merged_details

    subject_patterns = (
        rf"{re.escape(subject)}\s+name\s*[:\-]\s*[A-Z][A-Za-z .'-]+?(?=\s+(?:role|contribution|relationship with haji|nickname|nick\s*name)\b|$)",
        rf"{re.escape(subject)}\s*[:\-]\s*[A-Z][A-Za-z .'-]+?(?=\s+(?:role|contribution|relationship with haji|nickname|nick\s*name)\b|$)",
    )
    stop_pattern = rf"(?=\s+(?:{FAMILY_FIELD_LABEL_PATTERN})\b|\s+{FAMILY_ENTRY_START_PATTERN}|$)"
    field_patterns = {
        "role": rf"role\s*[:\-]\s*(.+?){stop_pattern}",
        "contribution": rf"contribution\s*[:\-]\s*(.+?){stop_pattern}",
        "relationship": rf"relationship with haji\s*[:\-]\s*(.+?){stop_pattern}",
    }
    details: dict[str, str] = {}
    for context in contexts:
        content = str(context.get("content", "")).replace("---", " ")
        if not content:
            continue
        segment = ""
        for pattern in subject_patterns:
            match = re.search(pattern, content, flags=re.IGNORECASE)
            if match:
                start = match.start()
                remainder = content[start:]
                stop_markers = [
                    marker.start()
                    for marker in (
                        re.search(rf"\b{FAMILY_ENTRY_START_PATTERN}", remainder, flags=re.IGNORECASE),
                    )
                    if marker and marker.start() > 0
                ]
                end = min(stop_markers) if stop_markers else len(remainder)
                segment = remainder[:end]
                break
        if not segment:
            continue
        for key, pattern in field_patterns.items():
            if key in details:
                continue
            match = re.search(pattern, segment, flags=re.IGNORECASE)
            if not match:
                continue
            value = match.group(1).strip(" ,.-")
            value = re.sub(r"\s*-\s*", " ", value)
            value = re.sub(r"\s{2,}", " ", value).strip(" ,.-")
            if value:
                details[key] = value
    return details


def _is_simple_persona_relationship_prompt(prompt: str) -> bool:
    normalized = _normalize_prompt(prompt).strip(" ?!.,")
    if not _persona_relationship_subject(normalized):
        return False
    if any(term in normalized for term in {"tell me more", "details", "detail", "about", "role", "contribution", "relationship with"}):
        return False
    starters = (
        "who is haji ",
        "what is haji ",
        "what's haji ",
        "who is hajis ",
        "what is hajis ",
        "what's hajis ",
    )
    return normalized.startswith(starters) or normalized.startswith("who is haji's ") or normalized.startswith("what is haji's ")


def _build_persona_relationship_answer(prompt: str, contexts: List[dict], answer_mode: str = "balanced") -> str | None:
    subject = _persona_relationship_subject(prompt)
    if not subject:
        return None
    name = _extract_persona_relationship_name(subject, contexts)
    if not name:
        return None

    sentence = f"{name} is Haji's {subject}."
    if answer_mode == "founder":
        return _founder_tone_prefix(sentence)
    return sentence


def _relationship_subject_pronoun(subject: str) -> str:
    male_subjects = {"father", "brother", "husband", "son", "partner", "grandfather", "maternal grandfather", "paternal grandfather"}
    female_subjects = {"mother", "sister", "wife", "daughter", "grandmother", "maternal grandmother", "paternal grandmother"}
    normalized = subject.strip().lower()
    if normalized in male_subjects:
        return "He"
    if normalized in female_subjects:
        return "She"
    return "They"


def _build_persona_relationship_detail_answer(
    subject: str,
    name: str,
    contexts: List[dict],
    answer_mode: str = "balanced",
) -> str | None:
    detail_contexts = _entity_named_contexts(name, contexts) or contexts
    details = _extract_persona_relationship_detail_fields(subject, detail_contexts)
    summary_parts: List[str] = []
    subject_pronoun = _relationship_subject_pronoun(subject)

    role = details.get("role")
    contribution = details.get("contribution")
    relationship = details.get("relationship")
    details_text = details.get("details")
    influence = details.get("influence")
    qualification = details.get("qualification")
    nickname = details.get("nickname")

    def _with_pronoun(fragment: str) -> str:
        cleaned = fragment.rstrip(".")
        lowered = cleaned.lower()
        if lowered.startswith(("he ", "she ", "they ")):
            return cleaned[:1].upper() + cleaned[1:]
        if lowered.startswith(("is ", "was ", "acts ", "provides ", "supports ", "invested ", "part of ")):
            normalized_fragment = cleaned[:1].lower() + cleaned[1:] if cleaned[:1].isupper() else cleaned
            return f"{subject_pronoun} {normalized_fragment}"
        return f"{subject_pronoun} is {cleaned[:1].lower() + cleaned[1:] if cleaned[:1].isupper() else cleaned}"

    if details_text:
        summary_parts.append(_with_pronoun(details_text))
    if influence:
        summary_parts.append(_with_pronoun(influence))
    if role:
        role_fragments = _split_family_role_fragments(role)
        if role_fragments:
            cleaned_role = role_fragments[0][:1].lower() + role_fragments[0][1:] if role_fragments[0][:1].isupper() else role_fragments[0]
            summary_parts.append(f"{subject_pronoun} is {cleaned_role}")
            summary_parts.extend(_with_pronoun(fragment) for fragment in role_fragments[1:])
    if contribution:
        contribution_sentence = contribution.rstrip(".")
        summary_parts.append(_with_pronoun(contribution_sentence))
    if qualification:
        qualification_sentence = qualification.rstrip(".")
        summary_parts.append(f"{subject_pronoun} has {qualification_sentence[:1].lower() + qualification_sentence[1:] if qualification_sentence[:1].isupper() else qualification_sentence}")
    if nickname:
        summary_parts.append(f"{subject_pronoun} is also known as {nickname}")
    if relationship:
        cleaned_relationship = relationship.rstrip(".")
        if subject not in cleaned_relationship.lower():
            summary_parts.append(cleaned_relationship[:1].lower() + cleaned_relationship[1:] if cleaned_relationship[:1].isupper() else cleaned_relationship)

    opening = f"{name} is Haji's {subject}."
    if not summary_parts:
        return opening

    sentence_limit = _answer_sentence_limit(answer_mode, default_limit=2)
    if answer_mode == "concise":
        return opening

    if sentence_limit <= 2:
        detail_sentences = [part.rstrip(".") + "." for part in summary_parts[:2]]
        combined = " ".join([opening, *detail_sentences]).strip()
    else:
        combined = f"{opening} " + " ".join(
            part[:1].upper() + part[1:] + ("." if not part.endswith(".") else "")
            for part in summary_parts[: max(2, sentence_limit)]
        )
    combined = re.sub(r"\s{2,}", " ", combined).strip()
    if answer_mode == "founder":
        return _founder_tone_prefix(combined)
    return combined


def looks_knowledge_owned_entity_prompt(prompt: str, contexts: List[dict]) -> bool:
    if looks_persona_question(prompt):
        return True
    if not contexts:
        return False

    normalized = _normalize_prompt(prompt)
    if not normalized.startswith(
        (
            "who is ",
            "who's ",
            "what is ",
            "what's ",
            "tell me about ",
            "tell me more about ",
            "give more details about ",
            "give details about ",
            "give me details about ",
            "give more details of ",
            "give details of ",
            "give me details of ",
        )
    ):
        return False

    entity_hint = _entity_hint_from_prompt(prompt)
    if not entity_hint:
        return False
    relation_match = _relationship_subject_by_entity(entity_hint, contexts)
    if relation_match:
        return True

    entity_tokens = _keywords(entity_hint)
    if not entity_tokens:
        return False

    for context in contexts[:3]:
        haystack = " ".join(
            [
                str(context.get("title", "")).lower(),
                " ".join(str(tag).lower() for tag in context.get("tags", [])),
                str(context.get("content", "")).lower()[:1200],
            ]
        )
        if all(token in haystack for token in entity_tokens):
            persona_like = bool(context.get("core_persona")) or any(keyword in haystack for keyword in PERSONA_DOC_KEYWORDS.union(PERSONA_RELATIONSHIP_MARKERS))
            if persona_like:
                return True
    return False


def _build_knowledge_owned_entity_answer(prompt: str, contexts: List[dict], answer_mode: str = "balanced") -> str | None:
    entity_hint = _entity_hint_from_prompt(prompt)
    if not entity_hint:
        return None

    relation_match = _relationship_subject_by_entity(entity_hint, contexts)
    if relation_match:
        subject, name = relation_match
        if _looks_entity_detail_prompt(prompt):
            return _build_persona_relationship_detail_answer(subject, name, contexts, answer_mode=answer_mode)
        sentence = f"{name} is Haji's {subject}."
        return _founder_tone_prefix(sentence) if answer_mode == "founder" else sentence

    return None


def _sentence_score(sentence: str, prompt_keywords: List[str], title: str, position: int, base_score: float) -> float:
    sentence_tokens = set(_keywords(sentence))
    if not sentence_tokens:
        return 0.0
    overlap = len(sentence_tokens.intersection(prompt_keywords))
    title_overlap = len(set(_keywords(title)).intersection(prompt_keywords))
    early_bonus = 0.12 if position < 2 else 0.0
    density_bonus = min(0.18, overlap * 0.05)
    return base_score + overlap * 0.24 + title_overlap * 0.08 + early_bonus + density_bonus


def _candidate_sentences(prompt: str, contexts: List[dict], limit: int = 4) -> List[str]:
    prompt_keywords = _keywords(prompt)
    if not contexts:
        return []

    candidates: List[dict] = []
    seen_sentences: set[str] = set()
    for context in contexts:
        sentences = _split_sentences(context["content"])
        for index, sentence in enumerate(sentences):
            normalized = sentence.strip()
            if len(normalized) < 36:
                continue
            key = normalized.lower()
            if key in seen_sentences:
                continue
            score = _sentence_score(
                normalized,
                prompt_keywords,
                context["title"],
                index,
                float(context.get("score", 0.0)),
            )
            if score <= 0.0 and prompt_keywords:
                continue
            seen_sentences.add(key)
            candidates.append({"sentence": normalized, "score": score})

    if not candidates:
        return [context["excerpt"].strip() for context in contexts[:limit] if context.get("excerpt")]

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return [item["sentence"] for item in candidates[:limit]]


def _candidate_web_sentences(prompt: str, web_results: List[dict], limit: int = 3) -> List[str]:
    prompt_keywords = _keywords(prompt)
    focus_phrase = _focus_phrase_from_prompt(prompt)
    focus_keywords = set(_keywords(focus_phrase))
    relation_hint = _relation_hint_from_prompt(prompt)
    entity_hint = _entity_hint_from_prompt(prompt)
    generic_definition_prompt = _looks_generic_definition_question(prompt)
    if not web_results:
        return []

    candidates: List[dict] = []
    seen_sentences: set[str] = set()
    for result in rank_web_results_for_prompt(prompt, web_results):
        title = str(result.get("title", ""))
        title_tokens = set(_keywords(title))
        sentences = _split_sentences(str(result.get("excerpt", "")))
        for index, sentence in enumerate(sentences):
            normalized = sentence.strip()
            if len(normalized) < 24:
                continue
            key = normalized.lower()
            if key in seen_sentences:
                continue
            sentence_tokens = set(_keywords(normalized))
            score = _sentence_score(normalized, prompt_keywords, title, index, 0.0)
            sentence_only_overlap = len(sentence_tokens.intersection(prompt_keywords).difference(title_tokens))
            if sentence_only_overlap:
                score += sentence_only_overlap * 0.26
                if " is " in f" {normalized.lower()} " or " are " in f" {normalized.lower()} ":
                    score += 0.08
            if relation_hint and entity_hint:
                lowered_sentence = normalized.lower()
                lowered_title = title.lower()
                if relation_hint in lowered_sentence:
                    score += 0.58
                if entity_hint in lowered_sentence:
                    score += 0.82
                if entity_hint in lowered_title:
                    score += 0.46
                if focus_phrase and focus_phrase in lowered_sentence and (" is " in f" {lowered_sentence} " or " are " in f" {lowered_sentence} "):
                    score += 1.15
                if _is_subject_first_fact_sentence(normalized, relation_hint, entity_hint):
                    score += 2.35
            if generic_definition_prompt:
                if relation_hint and relation_hint in normalized.lower():
                    score += 1.45
                elif relation_hint:
                    score -= 0.72
                if entity_hint and entity_hint in normalized.lower():
                    score += 1.35
                if entity_hint and entity_hint in title.lower():
                    score += 0.95
                if focus_phrase and focus_phrase in normalized.lower():
                    score += 1.2
                if focus_phrase and focus_phrase in title.lower():
                    score += 0.8
                if focus_keywords:
                    phrase_overlap = len(sentence_tokens.intersection(focus_keywords))
                    score += phrase_overlap * 0.18
                if (" is " not in f" {normalized.lower()} " and " are " not in f" {normalized.lower()} "):
                    score -= 0.22
            if prompt_keywords and score <= 0.0:
                continue
            seen_sentences.add(key)
            candidates.append({"sentence": normalized, "score": score})

    if not candidates:
        return [str(result.get("excerpt", "")).strip() for result in web_results[:limit] if result.get("excerpt")]

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return [item["sentence"] for item in candidates[:limit]]


def _theme_summary(contexts: List[dict], maximum: int = 3) -> str:
    titles = [context.get("title", "") for context in contexts]
    tokens = [
        token
        for title in titles
        for token in _keywords(title)
        if token not in {"document", "notes", "note", "guide", "playbook", "profile"}
    ]
    if not tokens:
        return ""
    themes = [token for token, _count in Counter(tokens).most_common(maximum)]
    return ", ".join(themes)


def _looks_like_upload_question(prompt: str) -> bool:
    lower = prompt.lower()
    return "upload" in lower and ("next" in lower or "rag" in lower or "improve" in lower)


def _looks_like_summary_question(prompt: str) -> bool:
    lower = prompt.lower()
    return any(phrase in lower for phrase in {"summarize", "summary", "what do you know", "current knowledge"})


def _looks_personal_or_internal(prompt: str) -> bool:
    lower = prompt.lower()
    markers = {"my ", "our ", "internal", "knowledge base", "rag", "upload", "assistant", "documents"}
    return looks_persona_question(prompt) or looks_conversational_prompt(prompt) or any(marker in lower for marker in markers)


def _looks_generic_definition_question(prompt: str) -> bool:
    lower = " ".join(prompt.lower().split())
    starters = ("what is ", "who is ", "what are ", "who are ", "define ", "meaning of ")
    if not lower.startswith(starters):
        return False

    focus_phrase = re.sub(r"^(the|a|an)\s+", "", _focus_phrase_from_prompt(prompt)).strip()
    fact_markers = (
        "capital of ",
        "population of ",
        "currency of ",
        "president of ",
        "prime minister of ",
        "ceo of ",
        "founder of ",
        "age of ",
        "height of ",
    )
    return not any(marker in focus_phrase for marker in fact_markers)


def _looks_specific_operational_question(prompt: str) -> bool:
    normalized = _normalize_prompt(prompt)
    return any(marker in normalized for marker in OPERATIONAL_QUERY_MARKERS)


def _operational_context_hits(prompt: str, context: dict) -> tuple[int, int, int]:
    normalized_prompt = _normalize_prompt(prompt)
    active_markers = [marker for marker in OPERATIONAL_QUERY_MARKERS if marker in normalized_prompt]
    if not active_markers:
        return 0, 0, 0

    title = str(context.get("title", "")).lower()
    tags = " ".join(str(tag).lower() for tag in context.get("tags", []))
    content = str(context.get("content", "")).lower()
    haystack = f"{title} {tags} {content}"
    marker_hits = sum(1 for marker in active_markers if marker in haystack)
    title_hits = sum(1 for marker in active_markers if marker in title)
    tag_hits = sum(1 for marker in active_markers if marker in tags)
    return marker_hits, title_hits, tag_hits


def _focus_phrase_from_prompt(prompt: str) -> str:
    lowered = " ".join(prompt.lower().split()).strip(" ?!.,:")
    starters = (
        "what is ",
        "who is ",
        "what are ",
        "who are ",
        "where is ",
        "when is ",
        "define ",
        "meaning of ",
        "tell me about ",
        "tell me more about ",
        "give details about ",
        "give me details about ",
        "give more details about ",
        "give details of ",
        "give me details of ",
        "give more details of ",
    )
    for starter in starters:
        if lowered.startswith(starter):
            return lowered[len(starter):].strip()
    return lowered


def _is_subject_first_fact_sentence(sentence: str, relation_hint: str, entity_hint: str) -> bool:
    if not relation_hint or not entity_hint:
        return False
    normalized = _normalize_prompt(sentence)
    relation_pattern = re.escape(relation_hint)
    entity_pattern = re.escape(entity_hint)
    patterns = (
        rf"\b[A-Z][A-Za-z0-9' .-]{{1,80}}\s+is\s+the\s+{relation_pattern}\s+of\s+{entity_pattern}\b",
        rf"\b[A-Z][A-Za-z0-9' .-]{{1,80}}\s+is\s+{relation_pattern}\s+of\s+{entity_pattern}\b",
    )
    return any(re.search(pattern, sentence, flags=re.IGNORECASE) for pattern in patterns) or any(
        re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns
    )


def _relation_hint_from_prompt(prompt: str) -> str:
    phrase = _focus_phrase_from_prompt(prompt)
    if " of " not in phrase:
        return ""
    head = phrase.split(" of ", 1)[0].strip()
    head = re.sub(r"^(the|a|an)\s+", "", head).strip()
    return head


def _entity_hint_from_prompt(prompt: str) -> str:
    phrase = _focus_phrase_from_prompt(prompt)
    phrase = re.sub(r"^(the|a|an)\s+", "", phrase).strip()
    if " of " in phrase:
        tail = phrase.rsplit(" of ", 1)[-1].strip()
        if len(tail) >= 3:
            return tail
    return phrase


def _knowledge_owned_entity_context_rank(prompt: str, context: dict) -> float:
    entity_hint = _entity_hint_from_prompt(prompt)
    if not entity_hint:
        return 0.0
    detail_prompt = _looks_entity_detail_prompt(prompt)
    title = str(context.get("title", "")).lower()
    tags = " ".join(str(tag).lower() for tag in context.get("tags", []))
    content = str(context.get("content", "")).lower()
    haystack = f"{title} {tags} {content}"
    entity_tokens = _keywords(entity_hint)
    token_hits = sum(1 for token in entity_tokens if token in haystack)
    if not token_hits:
        return 0.0
    relationship_hits = sum(1 for marker in PERSONA_RELATIONSHIP_MARKERS if marker in haystack)
    field_hits = int("name:" in content) + int("relationship with haji" in content) + int("contribution:" in content) + int("role:" in content)
    title_hits = sum(1 for token in entity_tokens if token in title)
    tag_hits = sum(1 for token in entity_tokens if token in tags)
    base_score = float(context.get("score", 0.0))
    return (
        base_score
        + token_hits * 0.82
        + relationship_hits * 0.22
        + field_hits * (0.18 if detail_prompt else 0.1)
        + title_hits * 0.26
        + tag_hits * 0.14
    )


def _context_match_stats(prompt_keywords: List[str], context: dict) -> tuple[int, float, int, int]:
    title_tokens = set(_keywords(context.get("title", "")))
    content_tokens = set(_keywords(context.get("content", "")))
    tag_tokens = {
        token
        for tag in context.get("tags", [])
        for token in _keywords(str(tag))
    }
    prompt_set = list(dict.fromkeys(prompt_keywords))

    def _count_matches(target_tokens: set[str]) -> int:
        return sum(1 for keyword in prompt_set if any(_tokens_match(keyword, token) for token in target_tokens))

    all_tokens = title_tokens.union(content_tokens, tag_tokens)
    match_count = _count_matches(all_tokens)
    overlap_ratio = match_count / max(1, len(prompt_set))
    return match_count, overlap_ratio, _count_matches(title_tokens), _count_matches(tag_tokens)


def select_contexts_for_prompt(prompt: str, contexts: List[dict]) -> List[dict]:
    if not contexts:
        return []

    if _looks_like_upload_question(prompt) or _looks_like_summary_question(prompt):
        return contexts

    if looks_knowledge_owned_entity_prompt(prompt, contexts):
        ranked = []
        for context in contexts:
            entity_rank = _knowledge_owned_entity_context_rank(prompt, context)
            if entity_rank <= 0:
                continue
            ranked.append((entity_rank, context))
        ranked.sort(key=lambda item: item[0], reverse=True)
        selected = [context for rank, context in ranked if rank >= 0.2]
        return selected[:3] or [context for _rank, context in ranked[: min(2, len(ranked))]]

    persona_topic = persona_question_topic(prompt)
    if persona_topic:
        ranked = []
        for context in contexts:
            persona_rank = _persona_context_rank(prompt, context)
            if persona_rank <= 0:
                continue
            ranked.append((persona_rank, context))
        ranked.sort(key=lambda item: item[0], reverse=True)
        selected = [context for rank, context in ranked if rank >= 0.22]
        return selected[:4] or [context for _rank, context in ranked[: min(3, len(ranked))]]

    prompt_keywords = _keywords(prompt)
    if not prompt_keywords:
        return []

    internal_prompt = _looks_personal_or_internal(prompt)
    operational_prompt = _looks_specific_operational_question(prompt)
    generic_definition_prompt = _looks_generic_definition_question(prompt) and not internal_prompt
    filtered: List[dict] = []
    normalized_prompt = prompt.strip().lower()
    for context in contexts:
        title = str(context.get("title", ""))
        content = str(context.get("content", ""))
        match_count, overlap_ratio, title_hits, tag_hits = _context_match_stats(prompt_keywords, context)
        operational_hits, operational_title_hits, operational_tag_hits = _operational_context_hits(prompt, context)
        exact_phrase = normalized_prompt and (
            normalized_prompt in title.lower() or normalized_prompt in content.lower()
        )
        score = float(context.get("score", 0.0))

        if len(prompt_keywords) == 1 and match_count >= 1:
            filtered.append(context)
            continue

        if exact_phrase:
            filtered.append(context)
            continue

        if operational_prompt:
            if operational_hits >= 1 and (
                operational_title_hits >= 1
                or operational_tag_hits >= 1
                or overlap_ratio >= 0.22
                or score >= 0.14
            ):
                filtered.append(context)
            continue

        if internal_prompt and (match_count >= 1 and (overlap_ratio >= 0.22 or score >= 0.045)):
            filtered.append(context)
            continue

        if generic_definition_prompt:
            if len(prompt_keywords) == 1 and title_hits >= 1 and score >= 0.12:
                filtered.append(context)
                continue

            if exact_phrase:
                filtered.append(context)
                continue

            if _looks_specific_operational_question(prompt) and score >= 0.3 and match_count >= 1:
                filtered.append(context)
                continue

            if match_count >= 2 and overlap_ratio >= 0.8 and title_hits >= 1 and tag_hits >= 1 and score >= 0.18:
                filtered.append(context)
            continue

        if not internal_prompt and match_count >= 2:
            filtered.append(context)

    return filtered


def rank_web_results_for_prompt(prompt: str, web_results: List[dict]) -> List[dict]:
    prompt_keywords = _keywords(prompt)
    if not prompt_keywords:
        return web_results

    focus_phrase = _focus_phrase_from_prompt(prompt)
    focus_keywords = _keywords(focus_phrase)
    entity_hint = _entity_hint_from_prompt(prompt)
    generic_definition_prompt = _looks_generic_definition_question(prompt)

    entertainment_terms = {
        "actor",
        "actress",
        "box office",
        "cinema",
        "film",
        "movie",
        "ott",
        "review",
        "song",
        "teaser",
        "trailer",
    }
    prompt_lower = prompt.lower()
    entertainment_prompt = any(term in prompt_lower for term in entertainment_terms)

    scored: List[tuple[tuple[int, int, int, int, int, int, int, int, float, int], dict]] = []
    for result in web_results:
        title = str(result.get("title", ""))
        excerpt = str(result.get("excerpt", ""))
        haystack = f"{title} {excerpt}".lower()
        title_lower = title.lower()
        entity_title_match = int(bool(entity_hint and entity_hint in title_lower))
        entity_excerpt_match = int(bool(entity_hint and entity_hint in excerpt.lower()))
        exact_title_phrase = int(bool(focus_phrase and focus_phrase in title_lower))
        exact_excerpt_phrase = int(bool(focus_phrase and focus_phrase in excerpt.lower()))
        match_count, overlap_ratio, title_hits, _tag_hits = _context_match_stats(
            prompt_keywords,
            {
                "title": title,
                "content": excerpt,
                "tags": [result.get("source", "")],
            },
        )
        focus_match_count = sum(1 for keyword in focus_keywords if keyword in haystack)
        source_fit = 0 if (not entertainment_prompt and any(term in haystack for term in entertainment_terms)) else 1
        authority_score = int(round(float(result.get("authority_score") or 0.0) * 1000))
        quality_score = int(round(float(result.get("quality_score") or 0.0) * 1000))
        scored.append(
            (
                (
                    entity_title_match,
                    entity_excerpt_match,
                    exact_title_phrase,
                    exact_excerpt_phrase,
                    source_fit,
                    authority_score,
                    quality_score,
                    focus_match_count or match_count,
                    overlap_ratio,
                    title_hits,
                ),
                result,
            )
        )

    scored.sort(key=lambda item: item[0], reverse=True)
    ranked = [result for _score, result in scored]
    if not generic_definition_prompt:
        return ranked

    filtered: List[dict] = []
    for score, result in scored:
        (
            entity_title_match,
            entity_excerpt_match,
            exact_title_phrase,
            exact_excerpt_phrase,
            _source_fit,
            _authority_score,
            _quality_score,
            focus_match_count,
            overlap_ratio,
            title_hits,
        ) = score
        if entity_title_match or entity_excerpt_match:
            filtered.append(result)
            continue
        if exact_title_phrase or exact_excerpt_phrase:
            filtered.append(result)
            continue
        if focus_keywords and focus_match_count >= min(2, len(focus_keywords)):
            filtered.append(result)
            continue
        if not focus_keywords and overlap_ratio >= 0.75 and title_hits >= 1:
            filtered.append(result)

    return filtered or ranked


def _join_items(items: Iterable[str]) -> str:
    parts = [item.strip().rstrip(".") for item in items if item.strip()]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{', '.join(parts[:-1])}, and {parts[-1]}"


def _build_upload_answer(prompt: str, contexts: List[dict]) -> str:
    themes = _theme_summary(contexts)
    mentions_profile_material = any(
        keyword in " ".join(context.get("title", "").lower() for context in contexts)
        for keyword in {"profile", "personality", "system", "team"}
    )

    opening = (
        "Upload the documents that answer repeatable business questions in one hop."
        if not themes
        else f"Upload the documents that deepen the areas you already have around {themes} and add more operational detail."
    )

    guidance = [
        "Pricing, policy, and objection-handling FAQs so the assistant can answer customer-facing questions fast.",
        "Step-by-step SOPs or checklists for support, sales, delivery, and admin work.",
        "Real examples like proposals, client conversations, or completed workflows so replies feel concrete instead of generic.",
        "Decision rules, exceptions, and edge cases that your team repeats often but that are not obvious from a single document.",
    ]
    if mentions_profile_material:
        guidance.insert(
            0,
            "Your current library leans more toward internal profile or system material, so the fastest improvement will come from practical operating documents.",
        )

    return (
        f"{opening}\n\n"
        "Best next uploads:\n"
        + "\n".join(f"- {item}" for item in guidance[:4])
    )


def _build_summary_answer(prompt: str, contexts: List[dict], web_results: List[dict]) -> str:
    themes = _theme_summary(contexts)
    supporting_sentences = _candidate_sentences(prompt, contexts, limit=3)
    opening = (
        f"Right now your knowledge base mainly covers {themes}."
        if themes
        else "Right now your knowledge base is strongest where you have saved direct operating notes and reference material."
    )
    if supporting_sentences:
        opening += f" The clearest themes are {_join_items(supporting_sentences[:2])}."
    if web_results:
        opening += " I also filled a few gaps with broader live reference material where your library was thin."
    return opening


def _build_general_guidance(prompt: str) -> str:
    lower = prompt.lower()
    if looks_persona_question(prompt):
        return (
            "I couldn’t find enough saved profile knowledge to answer that confidently as Haji yet. "
            "Add a focused note for this topic in the admin knowledge base, and I’ll answer it as a grounded profile response instead of falling back to generic web information."
        )
    if "strategy" in lower or "plan" in lower:
        return (
            "Start by clarifying the goal, the constraint, and the next measurable action. "
            "Then break the problem into priorities, owner, deadline, and feedback loop."
        )
    if "what" in lower or "how" in lower or "why" in lower:
        return (
            "I could not find a strong local match for that question, so the safest move is to answer at a general guidance level and point out where more source material would sharpen it."
        )
    return "I could not find a strong local match, so I’m giving the most practical general guidance I can from the question itself."


def _humanize_persona_sentence(sentence: str) -> str:
    cleaned = re.sub(r"^\s*[-*•]\s*", "", sentence).strip()
    replacements = [
        (r"^this ai represents haji\b", "Haji is the person this assistant represents"),
        (
            r"\band must behave, think, and respond in alignment with\b",
            ", and the assistant is designed to reflect",
        ),
        (
            r"\bmust behave, think, and respond in alignment with\b",
            "The assistant is designed to reflect",
        ),
        (r"^haji is the central persona for hajihaz ai\b", "Haji is the central person behind HajiHaz AI"),
        (r"^primary areas include\b", "His main focus areas include"),
        (r"^current focus areas include\b", "His current focus areas include"),
        (r"^the assistant should\b", "The assistant is expected to"),
    ]
    for pattern, replacement in replacements:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\band and\b", "and", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned.strip()


def _clean_web_sentence(sentence: str) -> str:
    cleaned = re.sub(r"^\s*[-*•]\s*", "", sentence).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = cleaned.strip(" \n\t")
    if cleaned and cleaned[-1] not in ".!?":
        cleaned = f"{cleaned}."
    return cleaned


def _clean_local_sentence(sentence: str) -> str:
    cleaned = re.sub(r"^\s*[-*•]\s*", "", sentence).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = cleaned.strip(" \n\t")
    if cleaned and cleaned[-1] not in ".!?":
        cleaned = f"{cleaned}."
    return cleaned


def _looks_structured_knowledge_context(contexts: List[dict]) -> bool:
    for context in contexts[:2]:
        content = str(context.get("content", ""))
        if re.search(r"(^|\n)\s*[-*•]\s+", content):
            return True
        if re.search(r"\s[-*•]\s", content):
            return True
        if content.count("\n") >= 2:
            return True
        if content.count(",") >= 2:
            return True
        if "---" in content:
            return True
        if re.search(r"(?:^|\s)\d+[.)]\s+", content):
            return True
        if re.search(r",\s*(then|next|after that|followed by|and then|finally|also)\b", content, flags=re.IGNORECASE):
            return True
    return False


def _split_knowledge_summary_units(text: str) -> List[str]:
    units: List[str] = []
    normalized_text = text.replace("---", "\n")
    normalized_text = re.sub(r"\s+(?:[-*•]|\d+[.)])\s+", "\n", normalized_text)
    for block in re.split(r"\n+", normalized_text):
        cleaned_block = re.sub(r"^\s*[-*•]\s*", "", block).strip()
        if not cleaned_block:
            continue
        sentence_parts = [part.strip() for part in _split_sentences(cleaned_block) if part.strip()]
        for part in sentence_parts or [cleaned_block]:
            if part.count(",") >= 2:
                comma_parts = [piece.strip() for piece in re.split(r",\s*", part) if piece.strip()]
                if len(comma_parts) >= 2:
                    units.extend(comma_parts)
                    continue
            units.append(part)
    return units


def _knowledge_summary_fragments(contexts: List[dict], sentences: List[str], limit: int = 3) -> List[str]:
    fragments: List[str] = []
    seen: set[str] = set()
    raw_units: List[str] = []
    for context in contexts[:3]:
        raw_units.extend(_split_knowledge_summary_units(str(context.get("content", ""))))
        if len(raw_units) >= max(limit * 3, 6):
            break

    if not raw_units:
        raw_units.extend(sentences)

    for raw_unit in raw_units:
        cleaned = _clean_local_sentence(raw_unit).strip().rstrip(".!?")
        cleaned = re.sub(r"^(then|next|after that|finally|also|and|so)\s+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^[A-Z][A-Za-z ]{1,40}:\s+", "", cleaned)
        cleaned = cleaned.strip(' "\'“”')
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,")
        if len(cleaned) < 8:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        fragments.append(cleaned)
        if len(fragments) >= limit:
            break
    return fragments


def _knowledge_prompt_frame(prompt: str) -> tuple[str, str] | None:
    normalized = _normalize_prompt(prompt).strip(" ?!.,")
    patterns = (
        (r"^how does (.+?) start$", "starts with"),
        (r"^how do (.+?) start$", "start with"),
        (r"^what does (.+?) cover$", "covers"),
        (r"^what is included in (.+)$", "includes"),
        (r"^what are the steps (?:for|in) (.+)$", "usually includes"),
        (r"^how does (.+?) work$", "works through"),
        (r"^how do (.+?) work$", "work through"),
    )
    for pattern, verb in patterns:
        match = re.match(pattern, normalized)
        if not match:
            continue
        subject = match.group(1).strip()
        if subject:
            return subject, verb
    return None


def _strip_summary_prefix(fragment: str, subject: str, verb: str) -> str:
    raw = fragment.strip()
    variants = [
        f"{subject} {verb}",
        f"the {subject} {verb}",
    ]
    lowered = raw.lower()
    for variant in variants:
        if lowered.startswith(variant.lower()):
            trimmed = raw[len(variant) :].strip(" ,:")
            return trimmed
    return raw


def _knowledge_label(contexts: List[dict]) -> str:
    title = str((contexts[0] if contexts else {}).get("title", "")).strip()
    if not title:
        return "knowledge base"
    title = re.sub(r"\s+", " ", title).strip()
    return title[:1].lower() + title[1:] if title[:1].isupper() else title


def _build_structured_knowledge_summary(
    prompt: str,
    contexts: List[dict],
    knowledge_sentences: List[str],
    answer_mode: str = "balanced",
) -> str:
    fragment_limit = 2 if answer_mode == "concise" else max(4, _answer_sentence_limit(answer_mode, default_limit=3) + 1)
    fragments = _knowledge_summary_fragments(
        contexts,
        knowledge_sentences,
        limit=fragment_limit,
    )
    if len(fragments) < 2:
        return ""

    frame = _knowledge_prompt_frame(prompt)
    if frame:
        subject, verb = frame
        reduced_fragments = [
            reduced
            for fragment in fragments
            if (reduced := _strip_summary_prefix(fragment, subject, verb))
        ]
        if len(reduced_fragments) < 2:
            return ""
        summary = f"{subject[:1].upper() + subject[1:]} {verb} {_join_items(reduced_fragments)}."
    else:
        summary = f"The key points are {_join_items(fragments)}."

    if answer_mode == "founder":
        return _founder_tone_prefix(summary)
    if answer_mode == "strategic":
        tail = _strategic_tail(prompt)
        return f"{summary} {tail}".strip() if tail else summary
    if answer_mode == "concise":
        return summary
    return summary


def _answer_sentence_limit(answer_mode: str, default_limit: int = 2) -> int:
    answer_mode = normalize_answer_mode(answer_mode)
    if answer_mode == "concise":
        return 1
    if answer_mode == "detailed":
        return max(default_limit, 3)
    return default_limit


def _founder_tone_prefix(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped
    if stripped.lower().startswith(("in simple terms,", "at a practical level,", "from haji's point of view,")):
        return stripped
    return f"In simple terms, {stripped[:1].lower() + stripped[1:]}" if stripped[:1].isupper() else f"In simple terms, {stripped}"


def _strategic_tail(prompt: str) -> str:
    lower = _normalize_prompt(prompt)
    if any(term in lower for term in {"strategy", "business", "plan", "planning", "workflow", "operations"}):
        return "What matters most is turning that into a clear decision, owner, and next step."
    if any(term in lower for term in {"education", "qualification", "profile", "businesses", "company"}):
        return "If you want, I can also turn that into a clearer profile-style summary."
    return ""


def _build_clean_web_answer(prompt: str, web_results: List[dict], limit: int = 3, answer_mode: str = "balanced") -> str:
    answer_mode = normalize_answer_mode(answer_mode)
    web_sentences = _dedupe_sentences(
        [_clean_web_sentence(sentence) for sentence in _candidate_web_sentences(prompt, web_results, limit=limit + 1)],
        limit=max(limit, _answer_sentence_limit(answer_mode, default_limit=2)),
    )
    if not web_sentences:
        return _build_general_guidance(prompt)

    first_sentence = web_sentences[0]
    simple_fact_prompt = len(prompt.split()) <= 10 and (
        _looks_generic_definition_question(prompt)
        or any(
            marker in _focus_phrase_from_prompt(prompt)
            for marker in (
                "capital of ",
                "population of ",
                "currency of ",
                "president of ",
                "prime minister of ",
                "ceo of ",
                "founder of ",
                "age of ",
                "height of ",
            )
        )
    )
    if simple_fact_prompt and len(first_sentence) <= 180:
        return _founder_tone_prefix(first_sentence) if answer_mode == "founder" else first_sentence

    if len(web_sentences) == 1:
        if answer_mode == "founder":
            return _founder_tone_prefix(first_sentence)
        return first_sentence

    supporting_sentences = [sentence for sentence in web_sentences[1:] if sentence.lower() != first_sentence.lower()]
    if not supporting_sentences:
        if answer_mode == "founder":
            return _founder_tone_prefix(first_sentence)
        return first_sentence

    sentence_limit = _answer_sentence_limit(answer_mode, default_limit=2)
    combined = " ".join([first_sentence, *supporting_sentences[: max(0, sentence_limit - 1)] ]).strip()
    if answer_mode == "strategic":
        tail = _strategic_tail(prompt)
        return f"{combined} {tail}".strip() if tail else combined
    if answer_mode == "founder":
        return _founder_tone_prefix(combined)
    return combined


def _build_clean_knowledge_answer(
    prompt: str,
    contexts: List[dict],
    web_results: List[dict],
    limit: int = 3,
    answer_mode: str = "balanced",
) -> str:
    answer_mode = normalize_answer_mode(answer_mode)
    knowledge_sentences = _dedupe_sentences(
        [_clean_local_sentence(sentence) for sentence in _candidate_sentences(prompt, contexts, limit=limit + 2)],
        limit=max(limit, _answer_sentence_limit(answer_mode, default_limit=2)),
    )
    if not knowledge_sentences:
        return ""

    first_sentence = knowledge_sentences[0]
    structured_summary = ""
    if _looks_structured_knowledge_context(contexts):
        structured_summary = _build_structured_knowledge_summary(
            prompt,
            contexts,
            knowledge_sentences,
            answer_mode=answer_mode,
        )
    simple_prompt = len(prompt.split()) <= 10 and (
        _looks_generic_definition_question(prompt) or _looks_specific_operational_question(prompt)
    )
    if structured_summary:
        return structured_summary
    if simple_prompt and len(first_sentence) <= 200:
        return _founder_tone_prefix(first_sentence) if answer_mode == "founder" else first_sentence

    if len(knowledge_sentences) == 1:
        supporting_web = []
        if web_results and not _looks_personal_or_internal(prompt):
            supporting_web = _dedupe_sentences(
                [_clean_web_sentence(sentence) for sentence in _candidate_web_sentences(prompt, web_results, limit=1)],
                limit=1,
            )
        if supporting_web and supporting_web[0].lower() != first_sentence.lower():
            combined = f"{first_sentence} {supporting_web[0]}".strip()
            return _founder_tone_prefix(combined) if answer_mode == "founder" else combined
        return _founder_tone_prefix(first_sentence) if answer_mode == "founder" else first_sentence

    supporting_sentences = [
        sentence for sentence in knowledge_sentences[1:] if sentence.lower() != first_sentence.lower()
    ]
    if not supporting_sentences and web_results and not _looks_personal_or_internal(prompt):
        supporting_sentences = _dedupe_sentences(
            [_clean_web_sentence(sentence) for sentence in _candidate_web_sentences(prompt, web_results, limit=1)],
            limit=1,
        )

    if not supporting_sentences:
        return _founder_tone_prefix(first_sentence) if answer_mode == "founder" else first_sentence

    sentence_limit = _answer_sentence_limit(answer_mode, default_limit=2)
    combined = " ".join([first_sentence, *supporting_sentences[: max(0, sentence_limit - 1)] ]).strip()
    if answer_mode == "strategic":
        tail = _strategic_tail(prompt)
        return f"{combined} {tail}".strip() if tail else combined
    if answer_mode == "founder":
        return _founder_tone_prefix(combined)
    return combined


def _dedupe_sentences(sentences: List[str], limit: int = 3) -> List[str]:
    deduped: List[str] = []
    seen: set[str] = set()
    for sentence in sentences:
        normalized = sentence.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(sentence.strip())
        if len(deduped) >= limit:
            break
    return deduped


def _build_persona_answer(prompt: str, contexts: List[dict], answer_mode: str = "balanced") -> str:
    answer_mode = normalize_answer_mode(answer_mode)
    if not persona_prompt_has_supported_context(prompt, contexts):
        return _persona_unknown_answer(prompt, answer_mode=answer_mode)

    if _is_simple_persona_relationship_prompt(prompt):
        relationship_answer = _build_persona_relationship_answer(prompt, contexts, answer_mode=answer_mode)
        if relationship_answer:
            return relationship_answer

    topic = persona_question_topic(prompt) or "identity"
    sentences = _dedupe_sentences(
        [_humanize_persona_sentence(sentence) for sentence in _candidate_sentences(prompt, contexts, limit=5)],
        limit=_answer_sentence_limit(answer_mode, default_limit=3),
    )

    if not sentences:
        sentences = _dedupe_sentences(
            [_humanize_persona_sentence(context.get("excerpt", "")) for context in contexts if context.get("excerpt")],
            limit=_answer_sentence_limit(answer_mode, default_limit=3),
        )
    if not sentences:
        return _build_general_guidance(prompt)

    if topic == "business":
        intro = "Based on your saved business notes,"
    elif topic == "education":
        intro = "Based on your saved education and qualification notes,"
    elif topic == "ai":
        intro = "Based on your saved HajiHaz AI notes,"
    else:
        intro = "Based on your saved profile,"

    opening = sentences[0]
    if topic != "identity" and not opening.lower().startswith("based on "):
        opening = f"{intro} {opening[:1].lower() + opening[1:]}" if opening[:1].isupper() else f"{intro} {opening}"
    elif not opening.lower().startswith(("haji ", "hajihaz ai ", "his ", "based on ")):
        opening = f"{intro} {opening[:1].lower() + opening[1:]}" if opening[:1].isupper() else f"{intro} {opening}"

    supporting = " ".join(sentence for sentence in sentences[1:] if sentence)
    combined = f"{opening}\n\n{supporting}".strip() if supporting else opening.strip()
    if answer_mode == "founder":
        parts = combined.split("\n\n", 1)
        parts[0] = _founder_tone_prefix(parts[0])
        return "\n\n".join(parts).strip()
    if answer_mode == "strategic":
        tail = _strategic_tail(prompt)
        return f"{combined}\n\n{tail}".strip() if tail else combined
    if answer_mode == "concise":
        return opening.strip()
    return combined


def _contexts_look_persona(contexts: List[dict]) -> bool:
    combined_keywords = PERSONA_DOC_KEYWORDS.union(PERSONA_BUSINESS_DOC_KEYWORDS).union(PERSONA_EDUCATION_DOC_KEYWORDS)
    for context in contexts:
        haystack = " ".join(
            [
                str(context.get("title", "")).lower(),
                " ".join(str(tag).lower() for tag in context.get("tags", [])),
                str(context.get("content", "")).lower()[:400],
            ]
        )
        if any(keyword in haystack for keyword in combined_keywords):
            return True
    return False


def build_response(prompt: str, contexts: List[dict], web_results: List[dict], answer_mode: str = "balanced") -> str:
    answer_mode = normalize_answer_mode(answer_mode)
    ranked_web_results = rank_web_results_for_prompt(prompt, web_results)

    if looks_conversational_prompt(prompt):
        return build_conversational_answer(prompt, answer_mode=answer_mode)

    if _looks_like_upload_question(prompt):
        return _build_upload_answer(prompt, contexts)

    if _looks_like_summary_question(prompt):
        return _build_summary_answer(prompt, contexts, ranked_web_results)

    if looks_persona_question(prompt):
        return _build_persona_answer(prompt, contexts, answer_mode=answer_mode)

    if looks_knowledge_owned_entity_prompt(prompt, contexts):
        entity_answer = _build_knowledge_owned_entity_answer(prompt, contexts, answer_mode=answer_mode)
        if entity_answer:
            return entity_answer

    knowledge_sentences = _candidate_sentences(prompt, contexts, limit=4)
    web_sentences = _candidate_web_sentences(prompt, ranked_web_results, limit=3)
    generic_definition_prompt = _looks_generic_definition_question(prompt) and not _looks_personal_or_internal(prompt)

    if generic_definition_prompt and web_sentences and not looks_knowledge_owned_entity_prompt(prompt, contexts):
        return _build_clean_web_answer(prompt, ranked_web_results or web_results, limit=3, answer_mode=answer_mode)

    if knowledge_sentences:
        return _build_clean_knowledge_answer(prompt, contexts, ranked_web_results, limit=3, answer_mode=answer_mode)

    if web_sentences:
        return _build_clean_web_answer(prompt, ranked_web_results, limit=3, answer_mode=answer_mode)

    return _build_general_guidance(prompt)


def build_notice(
    contexts: List[dict],
    web_results: List[dict],
    live_provider: str | None = None,
    prompt: str = "",
) -> str | None:
    if looks_conversational_prompt(prompt):
        return None
    if looks_persona_question(prompt) and not persona_prompt_has_supported_context(prompt, contexts):
        return "That specific detail is not present in Haji's saved knowledge right now."
    if looks_knowledge_owned_entity_prompt(prompt, contexts):
        return "Grounded in Haji's saved profile and family knowledge."
    persona_prompt_context = bool(contexts and _contexts_look_persona(contexts))
    if live_provider in {"anthropic", "ollama"}:
        provider_label = "Anthropic" if live_provider == "anthropic" else "Ollama"
        if contexts and web_results:
            return f"Used your saved knowledge, added live web context where needed, and answered with {provider_label}."
        if contexts:
            if persona_prompt_context:
                return f"Grounded in Haji's saved profile and answered with {provider_label}."
            return f"Grounded in your saved knowledge base and answered with {provider_label}."
        if web_results:
            return f"Used live web context and answered with {provider_label}."
        return f"Answered with {provider_label}."
    if contexts and web_results:
        return "Grounded in your saved knowledge base with live web backup where needed."
    if web_results:
        return "No strong local match, so this answer used live web context."
    if contexts:
        if persona_prompt_context:
            return "Grounded in Haji's saved profile and business knowledge."
        return "Grounded in your saved knowledge base."
    return None
