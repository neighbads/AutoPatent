from __future__ import annotations

import re
from typing import Any, Dict, List


_TOKEN_SPLIT_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)


def _extract_keywords(text: str) -> List[str]:
    raw_tokens = [tok for tok in _TOKEN_SPLIT_RE.split(text) if tok]
    keywords: List[str] = []
    for token in raw_tokens:
        item = token.strip()
        if not item:
            continue
        if len(item) <= 1:
            continue
        keywords.append(item)
    return keywords


def build_queries(topic: str, candidates: List[Dict[str, Any]], max_queries: int = 12) -> List[str]:
    topic_clean = str(topic or "").strip() or "未命名主题"
    queries: List[str] = [topic_clean]

    for candidate in candidates:
        title = str(candidate.get("title", "")).strip()
        if title:
            queries.append(f"{topic_clean} {title}")
        summary = str(candidate.get("summary", "")).strip()
        if summary:
            queries.append(f"{topic_clean} {summary}")

    for keyword in _extract_keywords(topic_clean):
        queries.append(f"{topic_clean} {keyword}")

    deduped: List[str] = []
    seen = set()
    for query in queries:
        key = query.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(query)
        if len(deduped) >= max_queries:
            break
    return deduped
