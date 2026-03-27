from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from autopatent.pipeline import StageContext, StageResult
from autopatent.search import (
    build_queries,
    deduplicate_hits,
    default_resources,
    get_search_provider,
    summarize_hits,
)


@dataclass
class PriorArtScanStage:
    """Stage 02: Prior-art scan pipeline for CN MVP.

    Behavior:
    - Build multi-source resource list (patent + paper).
    - Expand topic/candidate driven queries.
    - Collect hits from configured provider (offline/seed-only/online).
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
            "prior_art_provider",
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
        queries = _extend_queries_from_seed_artifacts(ctx=ctx, queries=queries)
        provider_name = _resolve_provider_name(ctx)
        provider = get_search_provider(
            provider_name,
            plugin_hub_config=_resolve_plugin_hub_config(ctx),
        )
        raw_hits = provider.collect(
            topic=topic,
            resources=resources,
            queries=queries,
            candidates=candidates,
        )
        provider_meta = _extract_provider_meta(provider)
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
            provider_name=provider.name,
            provider_meta=provider_meta,
        )

        ctx.metadata["prior_art_resources"] = resources
        ctx.metadata["prior_art_queries_path"] = str(queries_path)
        ctx.metadata["prior_art_search_meta_path"] = str(meta_path)
        ctx.metadata["prior_art_evidence_path"] = str(evidence_path)
        ctx.metadata["prior_art_provider"] = provider.name

        result = StageResult(produces=list(self.produces))
        result.outputs = {
            "prior_art_resources": resources,
            "prior_art_queries_path": str(queries_path),
            "prior_art_search_meta_path": str(meta_path),
            "prior_art_evidence_path": str(evidence_path),
            "prior_art_provider": provider.name,
        }
        return result


def _resolve_provider_name(ctx: StageContext) -> str:
    metadata_name = str(ctx.metadata.get("search_provider", "") or "").strip()
    if metadata_name:
        return metadata_name
    env_name = str(os.getenv("AUTOPATENT_SEARCH_PROVIDER", "") or "").strip()
    if env_name:
        return env_name
    return "offline"


def _resolve_plugin_hub_config(ctx: StageContext) -> Dict[str, Any]:
    search = ctx.metadata.get("search")
    if not isinstance(search, dict):
        return {}
    plugin_hub = search.get("plugin_hub")
    if not isinstance(plugin_hub, dict):
        return {}
    return dict(plugin_hub)


def _extract_provider_meta(provider: Any) -> Dict[str, Any]:
    payload = getattr(provider, "last_meta", None)
    if isinstance(payload, dict):
        return payload
    return {}


def _write_queries(*, work_dir: Path, queries: List[str]) -> Path:
    path = work_dir / "artifacts" / "prior_art_queries.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(queries, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _extend_queries_from_seed_artifacts(*, ctx: StageContext, queries: List[str]) -> List[str]:
    seeds: List[str] = []

    digest = _read_seed_file(ctx.metadata.get("input_doc_digest_path"), base_dir=ctx.work_dir)
    if digest:
        tokens = digest.replace("\n", " ").split()
        for token in tokens:
            cleaned = token.strip(",:;()[]{}<>\"'")
            if len(cleaned) <= 2:
                continue
            seeds.append(cleaned)
            if len(seeds) >= 12:
                break

    inventory_payload = _read_seed_json(ctx.metadata.get("code_inventory_path"), base_dir=ctx.work_dir)
    if isinstance(inventory_payload, dict):
        files = inventory_payload.get("files")
        if isinstance(files, list):
            for item in files:
                if not isinstance(item, dict):
                    continue
                rel = str(item.get("path", "")).strip()
                if not rel:
                    continue
                stem = Path(rel).stem
                if len(stem) <= 2:
                    continue
                seeds.append(stem)
                if len(seeds) >= 24:
                    break

    merged = list(queries)
    seen = {q.lower() for q in merged}
    base_topic = str(ctx.metadata.get("topic", "") or "").strip() or "未命名主题"
    for seed in seeds:
        q = f"{base_topic} {seed}"
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(q)
        if len(merged) >= 20:
            break
    return merged


def _read_seed_file(raw_path: Any, *, base_dir: Path) -> str:
    if raw_path is None:
        return ""
    path = Path(str(raw_path).strip())
    if not path:
        return ""
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    else:
        path = path.resolve()
    if not path.exists() or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _read_seed_json(raw_path: Any, *, base_dir: Path) -> Any:
    content = _read_seed_file(raw_path, base_dir=base_dir)
    if not content:
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


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
    provider_name: str,
    provider_meta: Dict[str, Any],
) -> Path:
    payload = {
        "query_count": len(queries),
        "resource_count": len(resources),
        "raw_hits": raw_hits_count,
        "deduped_hits": deduped_hits_count,
        "evidence_count": evidence_count,
        "provider": provider_name,
    }
    if provider_meta:
        payload.update(provider_meta)
        payload["provider"] = provider_name
    path = work_dir / "artifacts" / "search_meta.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
