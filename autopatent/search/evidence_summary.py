from __future__ import annotations

from typing import Any, Dict, Iterable, List


def summarize_hits(hits: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = []
    for idx, hit in enumerate(hits, start=1):
        source = str(hit.get("source", "UNKNOWN"))
        title = str(hit.get("title", "")).strip() or f"Evidence {idx}"
        query = str(hit.get("query", "")).strip()
        dedup_key = str(hit.get("dedup_key", "")).strip()
        related_direction_ids = hit.get("related_direction_ids")
        if not isinstance(related_direction_ids, list):
            related_direction_ids = []

        evidence.append(
            {
                "id": f"e-{idx:04d}",
                "source": source,
                "endpoint": hit.get("endpoint"),
                "query": query,
                "title": title,
                "dedup_key": dedup_key,
                "related_direction_ids": [str(i) for i in related_direction_ids],
                "snippet": f"[{source}] {title} — query: {query}",
            }
        )
    return evidence
