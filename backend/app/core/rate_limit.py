from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from math import ceil
from time import monotonic
from typing import Deque

from fastapi import Request

from app.core.config import settings


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    methods: frozenset[str]
    path_prefixes: tuple[str, ...]
    limit: int
    window_seconds: int


RATE_LIMIT_RULES = (
    RateLimitRule("admin-import-burst", frozenset({"POST"}), ("/admin/documents/import",), 6, 60),
    RateLimitRule("admin-import-hourly", frozenset({"POST"}), ("/admin/documents/import",), 20, 3600),
    RateLimitRule("admin-login-burst", frozenset({"POST"}), ("/auth/login",), 8, 60),
    RateLimitRule("admin-login-hourly", frozenset({"POST"}), ("/auth/login",), 30, 3600),
    RateLimitRule("user-login-burst", frozenset({"POST"}), ("/user-auth/google",), 20, 60),
    RateLimitRule("chat-burst", frozenset({"POST"}), ("/chat",), 40, 60),
    RateLimitRule("chat-hourly", frozenset({"POST"}), ("/chat",), 400, 3600),
    RateLimitRule("admin-api-burst", frozenset({"GET", "POST", "PUT", "DELETE"}), ("/admin/",), 180, 60),
)

_BUCKETS: dict[tuple[str, str], Deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or "unknown"
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def _matching_rules(method: str, path: str) -> list[RateLimitRule]:
    method = method.upper()
    return [
        rule
        for rule in RATE_LIMIT_RULES
        if method in rule.methods and any(path == prefix or path.startswith(f"{prefix}/") for prefix in rule.path_prefixes)
    ]


def rate_limit_retry_after(request: Request) -> int | None:
    if not settings.rate_limit_enabled:
        return None

    now = monotonic()
    client_ip = _client_ip(request)
    for rule in _matching_rules(request.method, request.url.path):
        key = (client_ip, rule.name)
        bucket = _BUCKETS[key]
        while bucket and now - bucket[0] >= rule.window_seconds:
            bucket.popleft()
        if len(bucket) >= rule.limit:
            return max(1, ceil(rule.window_seconds - (now - bucket[0])))
        bucket.append(now)
    return None
