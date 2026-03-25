from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Protocol


class SearchProvider(Protocol):
    name: str

    def collect(
        self,
        *,
        topic: str,
        resources: List[Dict[str, str]],
        queries: List[str],
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]: ...


@dataclass(frozen=True)
class OfflinePseudoProvider:
    name: str = "offline"

    def collect(
        self,
        *,
        topic: str,
        resources: List[Dict[str, str]],
        queries: List[str],
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        direction_ids = [str(c.get("id")) for c in candidates if "id" in c]
        hits: List[Dict[str, Any]] = []
        if not queries or not resources:
            return hits

        sampled_queries = queries[: min(6, len(queries))]
        sampled_resources = resources[: min(10, len(resources))]
        for q_idx, query in enumerate(sampled_queries, start=1):
            for r_idx, resource in enumerate(sampled_resources, start=1):
                duplicate_bucket = (q_idx % 3) + 1
                title = f"{topic or '主题'} 相关方案 {duplicate_bucket}"
                hits.append(
                    {
                        "source": resource.get("source"),
                        "endpoint": resource.get("endpoint"),
                        "query": query,
                        "title": title,
                        "related_direction_ids": direction_ids,
                        "rank": r_idx,
                    }
                )
        return hits


@dataclass(frozen=True)
class SeedOnlyProvider:
    name: str = "seed-only"

    def collect(
        self,
        *,
        topic: str,
        resources: List[Dict[str, str]],
        queries: List[str],
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        hits: List[Dict[str, Any]] = []
        direction_ids = [str(c.get("id")) for c in candidates if "id" in c]
        if not queries:
            return hits
        fallback_source = resources[0]["source"] if resources else "SEED"
        fallback_endpoint = resources[0]["endpoint"] if resources else ""
        for idx, query in enumerate(queries, start=1):
            hits.append(
                {
                    "source": fallback_source,
                    "endpoint": fallback_endpoint,
                    "query": query,
                    "title": f"{topic or '主题'} seed result {idx}",
                    "related_direction_ids": direction_ids,
                    "rank": idx,
                }
            )
        return hits


def get_search_provider(name: str | None) -> SearchProvider:
    normalized = str(name or "").strip().lower() or "offline"
    if normalized == "offline":
        return OfflinePseudoProvider()
    if normalized == "seed-only":
        return SeedOnlyProvider()
    raise ValueError(f"Unknown search provider: {normalized}")
