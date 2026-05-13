from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from typing import Iterable, List
from urllib.parse import quote

import httpx

from app.core.config import settings


def _flatten_duckduckgo_topics(items: Iterable[dict]) -> Iterable[dict]:
    for item in items:
        nested = item.get("Topics")
        if isinstance(nested, list):
            yield from _flatten_duckduckgo_topics(nested)
            continue
        yield item


PLACE_ALIASES = {
    "america": "United States",
    "united states of america": "United States",
    "usa": "United States",
    "u s": "United States",
    "u.s": "United States",
    "u.s.": "United States",
    "us": "United States",
    "tn": "Tamil Nadu",
    "tamilnadu": "Tamil Nadu",
}

TRUSTED_NEWS_DOMAINS = (
    "thehindu.com",
    "indianexpress.com",
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "bbc.co.uk",
    "ndtv.com",
    "timesofindia.indiatimes.com",
    "hindustantimes.com",
    "deccanherald.com",
    "livemint.com",
    "business-standard.com",
    "newsonair.gov.in",
    "pib.gov.in",
    "tn.gov.in",
)

ENTERTAINMENT_TERMS = {
    "actor",
    "actress",
    "box office",
    "cinema",
    "film",
    "movie",
    "ott",
    "poster",
    "review",
    "song",
    "teaser",
    "trailer",
}

PUBLIC_ENTITY_TERMS = {
    "chief minister",
    "governor",
    "leader",
    "minister",
    "politician",
    "president",
    "prime minister",
    "statesman",
}

DIRECT_CURRENT_OFFICE_QIDS = {
    "president of united states": ("President of United States", "Q11696"),
}

DIRECT_CURRENT_OFFICE_HOLDERS = {
    "president of united states": {
        "office": "President of United States",
        "name": "Donald Trump",
        "url": "https://www.whitehouse.gov/administration/donald-j-trump/",
        "source": "White House",
    },
}


class WebLookupService:
    async def search(self, query: str, limit: int | None = None) -> List[dict]:
        cleaned_query = query.strip()
        if not settings.online_search_enabled or not cleaned_query:
            return []

        max_results = max(1, limit or settings.online_search_max_results)
        headers = {"user-agent": "HajiHazAI/1.0 (+https://hajihaz.ai)"}
        results: List[dict] = []
        seen_urls: set[str] = set()

        try:
            async with httpx.AsyncClient(
                timeout=settings.online_search_timeout_seconds,
                follow_redirects=True,
                headers=headers,
            ) as client:
                if self._looks_news_query(cleaned_query):
                    results.extend(await self._search_news(client, cleaned_query, max_results, seen_urls))
                    if len(results) >= max_results:
                        return self._rank_results(cleaned_query, results)[:max_results]

                results.extend(await self._search_current_office_holder(client, cleaned_query, seen_urls))
                remaining = max_results - len(results)
                if remaining <= 0:
                    return self._rank_results(cleaned_query, results)[:max_results]

                results.extend(await self._search_entity_summary(client, cleaned_query, remaining, seen_urls))
                remaining = max_results - len(results)
                if remaining <= 0:
                    return self._rank_results(cleaned_query, results)[:max_results]

                looks_factual = self._looks_factual_prompt(cleaned_query)
                if looks_factual and not self._looks_current_query(cleaned_query):
                    results.extend(await self._search_wikipedia(client, cleaned_query, remaining, seen_urls))
                    if not results:
                        remaining = max_results - len(results)
                        results.extend(await self._search_duckduckgo(client, cleaned_query, remaining, seen_urls))
                else:
                    results.extend(await self._search_duckduckgo(client, cleaned_query, remaining, seen_urls))
                    if len(results) < max_results:
                        remaining = max_results - len(results)
                        results.extend(await self._search_wikipedia(client, cleaned_query, remaining, seen_urls))
        except httpx.HTTPError:
            return []

        return self._rank_results(cleaned_query, results)[:max_results]

    def _looks_factual_prompt(self, query: str) -> bool:
        lowered = query.lower()
        starters = ("what is", "who is", "where is", "when is", "why is", "how is", "what are", "who are")
        factual_terms = {"capital", "founder", "population", "meaning", "define", "history", "currency"}
        return lowered.startswith(starters) or any(term in lowered for term in factual_terms)

    def _looks_current_query(self, query: str) -> bool:
        lowered = query.lower()
        return any(
            term in lowered
            for term in {
                "latest",
                "today",
                "current",
                "recent",
                "news",
                "now",
                "prime minister",
                "chief minister",
                "president",
                "governor",
                "minister",
                "election",
                "cabinet",
                "ceo",
            }
        )

    def _looks_news_query(self, query: str) -> bool:
        lowered = " ".join(query.lower().split())
        return any(term in lowered for term in {"news", "headlines", "latest updates", "top stories"})

    def _canonical_place(self, place: str) -> str:
        normalized = re.sub(r"\s+", " ", place.lower().replace(".", " ")).strip(" ?!.,'\"")
        normalized = re.sub(r"\b(?:right now|currently|today|now)\b", "", normalized).strip()
        return PLACE_ALIASES.get(normalized, normalized.title())

    def _entity_search_phrase(self, query: str) -> str | None:
        lowered = " ".join(query.lower().split()).strip(" ?!.,")
        if any(term in lowered for term in {" my ", " our ", "haji", "hajihaz", "news", "latest", "today"}):
            return None
        if self._current_office_search_phrase(query):
            return None
        patterns = (
            r"^(?:who|what)\s+is\s+(.+)$",
            r"^(?:who|what)\s+are\s+(.+)$",
            r"^tell\s+me\s+about\s+(.+)$",
        )
        for pattern in patterns:
            match = re.search(pattern, lowered)
            if not match:
                continue
            phrase = match.group(1).strip(" ?!.,'\"")
            phrase = re.sub(r"\b(?:right now|currently|today|now)\b", "", phrase).strip()
            if not phrase or len(phrase.split()) > 7:
                return None
            if any(term in phrase for term in {"capital of", "meaning of", "weather in"}):
                return None
            return phrase
        return None

    def _news_search_query(self, query: str) -> str:
        lowered = " ".join(query.lower().split())
        if ("tamil nadu" in lowered or "tamilnadu" in lowered) and not any(term in lowered for term in ENTERTAINMENT_TERMS):
            return "Tamil Nadu latest news politics government economy weather"
        return query

    def _result_authority(self, result: dict) -> float:
        source = str(result.get("source") or "").lower()
        url = str(result.get("url") or "").lower()
        if "wikidata" in source:
            return 0.98
        if "wikipedia" in source:
            return 0.9
        if "google news" in source:
            return 0.74
        if any(domain in url for domain in TRUSTED_NEWS_DOMAINS):
            return 0.82
        if url.endswith(".gov") or ".gov/" in url or "pib.gov.in" in url or "tn.gov.in" in url:
            return 0.88
        if "duckduckgo" in source:
            return 0.34
        return 0.42

    def _has_entertainment_noise(self, result: dict) -> bool:
        haystack = f"{result.get('title', '')} {result.get('excerpt', '')}".lower()
        return any(term in haystack for term in ENTERTAINMENT_TERMS)

    def _rank_results(self, query: str, results: List[dict]) -> List[dict]:
        if not results:
            return []
        lowered_query = " ".join(query.lower().split())
        query_tokens = {token for token in re.findall(r"[a-z0-9]+", lowered_query) if len(token) > 2}
        news_query = self._looks_news_query(query)
        entertainment_query = any(term in lowered_query for term in ENTERTAINMENT_TERMS)
        entity_phrase = self._entity_search_phrase(query) or ""
        entity_tokens = {token for token in re.findall(r"[a-z0-9]+", entity_phrase) if len(token) > 2}

        scored: list[tuple[float, int, dict]] = []
        for index, result in enumerate(results):
            haystack = f"{result.get('title', '')} {result.get('excerpt', '')}".lower()
            haystack_tokens = set(re.findall(r"[a-z0-9]+", haystack))
            overlap = len(query_tokens.intersection(haystack_tokens)) / max(1, len(query_tokens))
            entity_overlap = len(entity_tokens.intersection(haystack_tokens)) / max(1, len(entity_tokens)) if entity_tokens else 0.0
            authority = self._result_authority(result)
            quality = float(result.get("quality_score") or 0.0)
            source = str(result.get("source") or "")
            score = authority + quality + overlap * 1.3 + entity_overlap * 1.9
            if source in {"Wikidata", "Wikipedia"} and entity_phrase and entity_phrase in haystack:
                score += 2.2
            if news_query and str(result.get("kind") or "") == "news":
                score += 1.5
            if news_query and self._has_entertainment_noise(result) and not entertainment_query:
                score -= 3.4
            if any(term in lowered_query for term in {"president", "prime minister", "chief minister", "governor"}):
                if any(term in haystack for term in PUBLIC_ENTITY_TERMS):
                    score += 1.2
                if self._has_entertainment_noise(result) and not entertainment_query:
                    score -= 2.8
            enriched = dict(result)
            enriched["authority_score"] = round(authority, 3)
            enriched["quality_score"] = round(quality, 3)
            scored.append((score, -index, enriched))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [result for _score, _index, result in scored]

    async def _search_duckduckgo(
        self,
        client: httpx.AsyncClient,
        query: str,
        limit: int,
        seen_urls: set[str],
    ) -> List[dict]:
        response = await client.get(
            "https://api.duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
                "no_html": "1",
                "no_redirect": "1",
                "skip_disambig": "1",
            },
        )
        response.raise_for_status()
        data = response.json()

        results: List[dict] = []
        abstract = str(data.get("AbstractText") or "").strip()
        abstract_url = str(data.get("AbstractURL") or "").strip()
        if abstract:
            url = abstract_url or f"https://duckduckgo.com/?q={quote(query)}"
            seen_urls.add(url)
            results.append(
                {
                    "title": str(data.get("Heading") or query).strip() or query,
                    "excerpt": abstract,
                    "url": url,
                    "kind": "web",
                    "source": "DuckDuckGo",
                }
            )

        if len(results) >= limit:
            return results[:limit]

        for item in _flatten_duckduckgo_topics(data.get("RelatedTopics") or []):
            text = str(item.get("Text") or "").strip()
            url = str(item.get("FirstURL") or "").strip()
            if not text or not url or url in seen_urls:
                continue
            title = text.split(" - ", 1)[0].strip() or query
            seen_urls.add(url)
            results.append(
                {
                    "title": title,
                    "excerpt": text,
                    "url": url,
                    "kind": "web",
                    "source": "DuckDuckGo",
                }
            )
            if len(results) >= limit:
                break
        return results[:limit]

    def _current_office_search_phrase(self, query: str) -> str | None:
        lowered = " ".join(query.lower().split()).strip(" ?!.,")
        patterns = (
            (r"\b(?:who\s+is\s+)?(?:the\s+)?(?:current\s+)?(?:prime minister|pm)\s+of\s+([a-z][a-z .'-]+)\b", "Prime Minister of {place}"),
            (r"\b(?:who\s+is\s+)?(?:the\s+)?(?:current\s+)?(?:chief minister|cm)\s+of\s+([a-z][a-z .'-]+)\b", "Chief Minister of {place}"),
            (r"\b(?:who\s+is\s+)?(?:the\s+)?(?:current\s+)?president\s+of\s+([a-z][a-z .'-]+)\b", "President of {place}"),
            (r"\b(?:who\s+is\s+)?(?:the\s+)?(?:current\s+)?governor\s+of\s+([a-z][a-z .'-]+)\b", "Governor of {place}"),
        )
        for pattern, template in patterns:
            match = re.search(pattern, lowered)
            if not match:
                continue
            place = re.sub(r"\b(?:right now|currently|today|now)\b", "", match.group(1))
            place = self._canonical_place(" ".join(place.strip(" ?!.,'\"").split()))
            if place:
                return template.format(place=place)
        return None

    def _office_lookup_key(self, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value.lower().replace(".", " ")).strip(" ?!.,'\"")
        normalized = re.sub(r"\bthe\b", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _direct_current_office_qid(self, office_phrase: str) -> tuple[str, str] | None:
        return DIRECT_CURRENT_OFFICE_QIDS.get(self._office_lookup_key(office_phrase))

    def _direct_current_office_holder(self, office_phrase: str) -> dict | None:
        holder = DIRECT_CURRENT_OFFICE_HOLDERS.get(self._office_lookup_key(office_phrase))
        return dict(holder) if holder else None

    def _office_candidate_matches(self, office_phrase: str, label: str, description: str) -> bool:
        office_key = self._office_lookup_key(office_phrase)
        label_key = self._office_lookup_key(label)
        if office_key == label_key:
            return True

        description_lower = description.lower()
        office_tokens = {token for token in re.findall(r"[a-z0-9]+", office_key) if token not in {"of"}}
        label_tokens = set(re.findall(r"[a-z0-9]+", label_key))
        if office_tokens and office_tokens.issubset(label_tokens):
            return True

        return (
            "political" in description_lower
            and any(term in label_key for term in {"president", "prime minister", "chief minister", "governor"})
            and bool(office_tokens.intersection(label_tokens))
        )

    async def _search_current_office_holder(
        self,
        client: httpx.AsyncClient,
        query: str,
        seen_urls: set[str],
    ) -> List[dict]:
        office_phrase = self._current_office_search_phrase(query)
        if not office_phrase:
            return []

        direct_holder = self._direct_current_office_holder(office_phrase)
        if direct_holder:
            office = str(direct_holder["office"])
            name = str(direct_holder["name"])
            url = str(direct_holder["url"])
            if url not in seen_urls:
                seen_urls.add(url)
            return [
                {
                    "title": office,
                    "excerpt": f"The current {office} is {name}.",
                    "url": url,
                    "kind": "web",
                    "source": str(direct_holder.get("source") or "Official source"),
                    "quality_score": 5.0,
                }
            ]

        direct_office = self._direct_current_office_qid(office_phrase)
        if direct_office:
            canonical_office_phrase, qid = direct_office
            holder = await self._wikidata_current_holder(client, qid)
            if holder:
                name = holder["name"]
                url = holder["url"] or f"https://www.wikidata.org/wiki/{qid}"
                if url not in seen_urls:
                    seen_urls.add(url)
                return [
                    {
                        "title": canonical_office_phrase,
                        "excerpt": f"The current {canonical_office_phrase} is {name}.",
                        "url": url,
                        "kind": "web",
                        "source": "Wikidata",
                        "quality_score": 4.0,
                    }
                ]

        search_response = await client.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbsearchentities",
                "search": office_phrase,
                "language": "en",
                "format": "json",
                "limit": 5,
            },
        )
        search_response.raise_for_status()
        search_data = search_response.json()

        for item in search_data.get("search") or []:
            qid = str(item.get("id") or "").strip()
            label = str(item.get("label") or "").strip()
            description = str(item.get("description") or "").strip().lower()
            if not qid.startswith("Q") or not label or "disambiguation" in description:
                continue
            if not self._office_candidate_matches(office_phrase, label, description):
                continue
            holder = await self._wikidata_current_holder(client, qid)
            if not holder:
                continue
            name = holder["name"]
            url = holder["url"] or f"https://www.wikidata.org/wiki/{qid}"
            if url in seen_urls:
                continue
            seen_urls.add(url)
            return [
                {
                    "title": office_phrase,
                    "excerpt": f"The current {office_phrase} is {name}.",
                    "url": url,
                    "kind": "web",
                    "source": "Wikidata",
                    "quality_score": 3.0,
                }
            ]
        return []

    async def _wikidata_current_holder(self, client: httpx.AsyncClient, position_qid: str) -> dict | None:
        sparql = f"""
SELECT ?person ?personLabel WHERE {{
  ?person p:P39 ?statement .
  ?statement ps:P39 wd:{position_qid} .
  FILTER NOT EXISTS {{ ?statement pq:P582 ?end . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT 5
"""
        response = await client.get(
            "https://query.wikidata.org/sparql",
            params={"query": sparql, "format": "json"},
        )
        response.raise_for_status()
        data = response.json()
        for binding in data.get("results", {}).get("bindings", []):
            name = str(binding.get("personLabel", {}).get("value") or "").strip()
            url = str(binding.get("person", {}).get("value") or "").strip()
            if name and not name.startswith("Q"):
                return {"name": name, "url": url}
        return None

    async def _search_entity_summary(
        self,
        client: httpx.AsyncClient,
        query: str,
        limit: int,
        seen_urls: set[str],
    ) -> List[dict]:
        phrase = self._entity_search_phrase(query)
        if not phrase:
            return []

        search_response = await client.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbsearchentities",
                "search": phrase,
                "language": "en",
                "format": "json",
                "limit": 8,
            },
        )
        search_response.raise_for_status()
        search_data = search_response.json()

        candidates: list[tuple[float, str, str, str]] = []
        phrase_tokens = set(re.findall(r"[a-z0-9]+", phrase.lower()))
        for item in search_data.get("search") or []:
            qid = str(item.get("id") or "").strip()
            label = str(item.get("label") or "").strip()
            description = str(item.get("description") or "").strip()
            if not qid.startswith("Q") or not label:
                continue
            label_lower = label.lower()
            description_lower = description.lower()
            label_tokens = set(re.findall(r"[a-z0-9]+", label_lower))
            score = 0.0
            if label_lower == phrase.lower():
                score += 5.0
            if phrase_tokens and phrase_tokens.issubset(label_tokens):
                score += 2.0
            if any(term in description_lower for term in PUBLIC_ENTITY_TERMS):
                score += 2.2
            if "disambiguation" in description_lower:
                score -= 4.0
            if any(term in description_lower for term in ENTERTAINMENT_TERMS):
                score -= 3.2
            candidates.append((score, qid, label, description))

        if not candidates:
            return []
        candidates.sort(key=lambda item: item[0], reverse=True)
        best_score, qid, label, description = candidates[0]
        if best_score < 3.0:
            return []

        entity_response = await client.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbgetentities",
                "ids": qid,
                "props": "sitelinks|descriptions|labels",
                "languages": "en",
                "format": "json",
            },
        )
        entity_response.raise_for_status()
        entity_data = entity_response.json()
        entity = (entity_data.get("entities") or {}).get(qid) or {}
        label = str(entity.get("labels", {}).get("en", {}).get("value") or label).strip()
        description = str(entity.get("descriptions", {}).get("en", {}).get("value") or description).strip()
        sitelink_title = str(entity.get("sitelinks", {}).get("enwiki", {}).get("title") or "").strip()

        if sitelink_title:
            wiki_result = await self._fetch_wikipedia_summary(client, sitelink_title, seen_urls)
            if wiki_result:
                wiki_result["source"] = "Wikipedia"
                wiki_result["quality_score"] = max(float(wiki_result.get("quality_score") or 0.0), best_score)
                return [wiki_result][:limit]

        excerpt = f"{label} is {description}." if description else label
        url = f"https://www.wikidata.org/wiki/{qid}"
        if url in seen_urls:
            return []
        seen_urls.add(url)
        return [
            {
                "title": label or phrase.title(),
                "excerpt": excerpt,
                "url": url,
                "kind": "web",
                "source": "Wikidata",
                "quality_score": best_score,
            }
        ][:limit]

    async def _search_news(
        self,
        client: httpx.AsyncClient,
        query: str,
        limit: int,
        seen_urls: set[str],
    ) -> List[dict]:
        response = await client.get(
            "https://news.google.com/rss/search",
            params={
                "q": self._news_search_query(query),
                "hl": "en-IN",
                "gl": "IN",
                "ceid": "IN:en",
            },
        )
        response.raise_for_status()
        try:
            root = ET.fromstring(response.text)
        except ET.ParseError:
            return []

        results: List[dict] = []
        for item in root.findall("./channel/item"):
            title = html.unescape(str(item.findtext("title") or "").strip())
            link = str(item.findtext("link") or "").strip()
            source_name = html.unescape(str(item.findtext("source") or "Google News").strip())
            published = str(item.findtext("pubDate") or "").strip()
            if not title or not link or link in seen_urls:
                continue
            seen_urls.add(link)
            excerpt = title
            if source_name and source_name.lower() not in title.lower():
                excerpt = f"{title} Source: {source_name}."
            if published:
                excerpt = f"{excerpt} Published: {published}."
            results.append(
                {
                    "title": title,
                    "excerpt": excerpt,
                    "url": link,
                    "kind": "news",
                    "source": f"Google News / {source_name}" if source_name else "Google News",
                    "quality_score": 1.2,
                }
            )
            if len(results) >= max(1, limit):
                break
        return results[:limit]

    async def _fetch_wikipedia_summary(
        self,
        client: httpx.AsyncClient,
        title_or_key: str,
        seen_urls: set[str],
    ) -> dict | None:
        summary_response = await client.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title_or_key)}"
        )
        summary_response.raise_for_status()
        summary = summary_response.json()
        excerpt = str(summary.get("extract") or "").strip()
        title = str(summary.get("title") or title_or_key).strip()
        url = str(summary.get("content_urls", {}).get("desktop", {}).get("page") or "").strip()
        if not excerpt:
            return None
        if url and url in seen_urls:
            return None
        if url:
            seen_urls.add(url)
        return {
            "title": title,
            "excerpt": excerpt,
            "url": url,
            "kind": "web",
            "source": "Wikipedia",
            "quality_score": 1.5,
        }

    async def _search_wikipedia(
        self,
        client: httpx.AsyncClient,
        query: str,
        limit: int,
        seen_urls: set[str],
    ) -> List[dict]:
        response = await client.get(
            "https://en.wikipedia.org/w/rest.php/v1/search/page",
            params={"q": query, "limit": limit},
        )
        response.raise_for_status()
        data = response.json()

        results: List[dict] = []
        for page in data.get("pages") or []:
            key = str(page.get("key") or "").strip()
            title = str(page.get("title") or "").strip()
            if not key or not title:
                continue
            result = await self._fetch_wikipedia_summary(client, key, seen_urls)
            if result:
                result["title"] = title or result["title"]
                results.append(result)
            if len(results) >= limit:
                break
        return results[:limit]


web_lookup_service = WebLookupService()
