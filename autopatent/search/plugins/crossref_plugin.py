from __future__ import annotations

import json
import urllib.parse
from typing import Any

from autopatent.search.plugins.base import RequestSpec


class CrossrefPlugin:
    _SOURCE = "CROSSREF"
    _DEFAULT_ENDPOINT = "https://api.crossref.org/works"

    def plugin_id(self) -> str:
        return "crossref"

    def supports(self, query: str, topic: str) -> bool:
        return bool(str(query).strip() or str(topic).strip())

    def build_requests(self, query: str, topic: str, limit: int) -> list[RequestSpec]:
        _ = topic
        safe_limit = max(1, min(int(limit or 1), 20))
        url = self._DEFAULT_ENDPOINT + "?" + urllib.parse.urlencode({"query": query, "rows": safe_limit})
        return [RequestSpec(method="GET", url=url, timeout_sec=20, meta={"query": query})]

    def parse_response(self, payload: str | bytes, request: RequestSpec) -> list[dict[str, Any]]:
        text = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else str(payload)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        message = data.get("message")
        if not isinstance(message, dict):
            return []
        rows = message.get("items")
        if not isinstance(rows, list):
            return []
        query = str(request.meta.get("query", "")).strip()
        hits: list[dict[str, Any]] = []
        for idx, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            title = _first_text(row.get("title"))
            if not title:
                continue
            authors: list[str] = []
            raw_authors = row.get("author")
            if isinstance(raw_authors, list):
                for author in raw_authors[:10]:
                    if not isinstance(author, dict):
                        continue
                    given = str(author.get("given", "")).strip()
                    family = str(author.get("family", "")).strip()
                    full = " ".join(part for part in [given, family] if part).strip()
                    if full:
                        authors.append(full)
            doi = str(row.get("DOI", "")).strip()
            year = _extract_year(row)
            hits.append(
                {
                    "plugin_id": self.plugin_id(),
                    "source": self._SOURCE,
                    "endpoint": self._DEFAULT_ENDPOINT,
                    "query": query,
                    "title": title,
                    "url": str(row.get("URL", "")).strip() or (f"https://doi.org/{doi}" if doi else ""),
                    "year": year,
                    "doi": doi,
                    "authors": authors,
                    "rank": idx,
                }
            )
        return hits

    def fallback_urls(self, query: str, topic: str, limit: int) -> list[str]:
        _ = topic, limit
        return [f"https://search.crossref.org/?q={urllib.parse.quote_plus(query)}"]

    def parse_fallback(self, payload: str, url: str, query: str, source: str) -> list[dict[str, Any]]:
        lines = [line.strip() for line in str(payload or "").splitlines() if line.strip()]
        hits: list[dict[str, Any]] = []
        for idx, line in enumerate(lines[:5], start=1):
            if len(line) < 10:
                continue
            hits.append(
                {
                    "plugin_id": self.plugin_id(),
                    "source": self._SOURCE,
                    "endpoint": url,
                    "query": query,
                    "title": line[:200],
                    "url": url,
                    "rank": idx,
                    "via_fallback": True,
                    "fallback_source": source,
                }
            )
        return hits


def _first_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
    return ""


def _extract_year(item: dict[str, Any]) -> Any:
    for key in ("published-print", "published-online", "issued", "created"):
        value = item.get(key)
        if not isinstance(value, dict):
            continue
        parts = value.get("date-parts")
        if not isinstance(parts, list) or not parts:
            continue
        first = parts[0]
        if not isinstance(first, list) or not first:
            continue
        year = first[0]
        if isinstance(year, int):
            return year
        if isinstance(year, str) and year.isdigit():
            return int(year)
    return ""
