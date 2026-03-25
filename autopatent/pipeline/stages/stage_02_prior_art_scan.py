from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from autopatent.pipeline import StageContext, StageResult
from autopatent.search import build_queries, deduplicate_hits, default_resources, summarize_hits


@dataclass
class PriorArtScanStage:
    """Stage 02: Offline prior-art scan pipeline for CN MVP.

    Behavior:
    - Build multi-source resource list (patent + paper).
    - Expand topic/candidate driven queries.
    - Generate deterministic pseudo-hits (offline, no network).
    - Deduplicate and summarize into evidence JSONL.
    - Persist queries/meta artifacts for traceability.
    """

    stage_id: str = "STAGE_02"
    requires: list[str] = field(default_factory=lambda: ["direction_candidates"])
    produces: list[str] = field(
        default_factory=lambda: [
            "prior_art_resources",
            "prior_art_queries_path",
            "prior_art_search_meta_path",
            "prior_art_evidence_path",
        ]
    )

    def run(self, ctx: StageContext) -> StageResult:
        if "direction_candidates" not in ctx.metadata:
            raise ValueError("Missing required input: direction_candidates")
        candidates = ctx.metadata.get("direction_candidates")
        if not isinstance(candidates, list):
            raise ValueError("ctx.metadata['direction_candidates'] must be a list")

        topic = str(ctx.metadata.get("topic", "") or "")
        resources = default_resources()
        queries = build_queries(topic, candidates)
        raw_hits = _generate_raw_hits(topic=topic, resources=resources, queries=queries, candidates=candidates)
        deduped_hits = deduplicate_hits(raw_hits)
        evidence = summarize_hits(deduped_hits)

        queries_path = _write_queries(work_dir=ctx.work_dir, queries=queries)
        evidence_path = _write_prior_art_evidence(work_dir=ctx.work_dir, evidence=evidence)
        meta_path = _write_search_meta(
            work_dir=ctx.work_dir,
            queries=queries,
            resources=resources,
            raw_hits_count=len(raw_hits),
            deduped_hits_count=len(deduped_hits),
            evidence_count=len(evidence),
        )

        ctx.metadata["prior_art_resources"] = resources
        ctx.metadata["prior_art_queries_path"] = str(queries_path)
        ctx.metadata["prior_art_search_meta_path"] = str(meta_path)
        ctx.metadata["prior_art_evidence_path"] = str(evidence_path)

        result = StageResult(produces=list(self.produces))
        result.outputs = {
            "prior_art_resources": resources,
            "prior_art_queries_path": str(queries_path),
            "prior_art_search_meta_path": str(meta_path),
            "prior_art_evidence_path": str(evidence_path),
        }
        return result


def _generate_raw_hits(
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

    # Keep runtime bounded and deterministic.
    sampled_queries = queries[: min(6, len(queries))]
    sampled_resources = resources[: min(10, len(resources))]
    for q_idx, query in enumerate(sampled_queries, start=1):
        for r_idx, resource in enumerate(sampled_resources, start=1):
            # Intentionally create repeated titles across resources so dedup has effect.
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


def _write_queries(*, work_dir: Path, queries: List[str]) -> Path:
    path = work_dir / "artifacts" / "prior_art_queries.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(queries, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _write_prior_art_evidence(
    *,
    work_dir: Path,
    evidence: List[Dict[str, Any]],
) -> Path:
    lines = [json.dumps(record, ensure_ascii=False) for record in evidence]
    path = work_dir / "artifacts" / "prior_art_evidence.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def _write_search_meta(
    *,
    work_dir: Path,
    queries: List[str],
    resources: List[Dict[str, str]],
    raw_hits_count: int,
    deduped_hits_count: int,
    evidence_count: int,
) -> Path:
    payload = {
        "query_count": len(queries),
        "resource_count": len(resources),
        "raw_hits": raw_hits_count,
        "deduped_hits": deduped_hits_count,
        "evidence_count": evidence_count,
    }
    path = work_dir / "artifacts" / "search_meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
