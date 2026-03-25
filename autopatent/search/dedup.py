from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


_NORMALIZE_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


def normalize_title(title: str) -> str:
    text = _NORMALIZE_RE.sub(" ", str(title or "").lower()).strip()
    return " ".join(text.split())


def deduplicate_hits(hits: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for hit in hits:
        key = normalize_title(str(hit.get("title", "")))
        if not key:
            key = normalize_title(str(hit.get("query", "")))
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        item = dict(hit)
        item["dedup_key"] = key
        deduped.append(item)
    return deduped
