from __future__ import annotations

import base64
import os
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

from autopatent.search.plugins.base import RequestSpec


class EpoOpsPlugin:
    _SOURCE = "EPO_OPS"
    _DEFAULT_ENDPOINT = "https://ops.epo.org/3.2/rest-services/published-data/search/biblio"

    def plugin_id(self) -> str:
        return "epo_ops"

    def supports(self, query: str, topic: str) -> bool:
        _ = query, topic
        return bool(self._credentials())

    def build_requests(self, query: str, topic: str, limit: int) -> list[RequestSpec]:
        _ = topic
        creds = self._credentials()
        if not creds:
            return []
        safe_limit = max(1, min(int(limit or 1), 25))
        url = self._DEFAULT_ENDPOINT + "?" + urllib.parse.urlencode(
            {"q": query, "Range": f"1-{safe_limit}"}
        )
        key, secret = creds
        token = base64.b64encode(f"{key}:{secret}".encode("utf-8")).decode("ascii")
        headers = {
            "Authorization": f"Basic {token}",
            "Accept": "application/xml",
        }
        return [RequestSpec(method="GET", url=url, headers=headers, timeout_sec=20, meta={"query": query})]

    def parse_response(self, payload: str | bytes, request: RequestSpec) -> list[dict[str, Any]]:
        text = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else str(payload)
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return []
        query = str(request.meta.get("query", "")).strip()
        hits: list[dict[str, Any]] = []
        rank = 1
        for exchange in root.iter():
            if not exchange.tag.lower().endswith("exchange-document"):
                continue
            title = ""
            doc_id = ""
            year: Any = ""
            for node in exchange.iter():
                tag = node.tag.lower()
                content = (node.text or "").strip()
                if not content:
                    continue
                if not title and tag.endswith("invention-title"):
                    title = content
                if not doc_id and tag.endswith("doc-number"):
                    doc_id = content
                if not year and tag.endswith("date") and len(content) >= 4 and content[:4].isdigit():
                    year = int(content[:4])
            if not title:
                continue
            url = f"https://worldwide.espacenet.com/patent/search/family/{doc_id}" if doc_id else ""
            hits.append(
                {
                    "plugin_id": self.plugin_id(),
                    "source": self._SOURCE,
                    "endpoint": self._DEFAULT_ENDPOINT,
                    "query": query,
                    "title": title,
                    "url": url,
                    "year": year,
                    "rank": rank,
                }
            )
            rank += 1
        return hits

    def fallback_urls(self, query: str, topic: str, limit: int) -> list[str]:
        _ = topic, limit
        return [
            "https://worldwide.espacenet.com/patent/search?q="
            + urllib.parse.quote_plus(query.strip())
        ]

    def parse_fallback(self, payload: str, url: str, query: str, source: str) -> list[dict[str, Any]]:
        lines = [line.strip() for line in str(payload or "").splitlines() if line.strip()]
        hits: list[dict[str, Any]] = []
        for idx, line in enumerate(lines[:5], start=1):
            if len(line) < 12:
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

    @staticmethod
    def _credentials() -> tuple[str, str] | None:
        key = str(os.getenv("EPO_OPS_CONSUMER_KEY", "")).strip()
        secret = str(os.getenv("EPO_OPS_CONSUMER_SECRET", "")).strip()
        if not key or not secret:
            return None
        return (key, secret)
