from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from autopatent.pipeline import StageContext, StageResult


def _stub_resources() -> List[Dict[str, str]]:
    # The endpoints are intentionally "stubs" for deterministic tests.
    return [
        {"source": "CNIPA", "endpoint": "https://pss-system.cnipa.gov.cn"},
        {"source": "WIPO_PATENTSCOPE", "endpoint": "https://patentscope.wipo.int"},
        {"source": "EPO_ESPACENET", "endpoint": "https://worldwide.espacenet.com"},
        {"source": "USPTO", "endpoint": "https://ppubs.uspto.gov"},
        {"source": "GOOGLE_PATENTS", "endpoint": "https://patents.google.com"},
        {"source": "GOOGLE_SCHOLAR", "endpoint": "https://scholar.google.com"},
        {"source": "SEMANTIC_SCHOLAR", "endpoint": "https://www.semanticscholar.org"},
        {"source": "ARXIV", "endpoint": "https://arxiv.org"},
        {"source": "IEEE_XPLORE", "endpoint": "https://ieeexplore.ieee.org"},
        {"source": "ACM_DL", "endpoint": "https://dl.acm.org"},
        {"source": "CNKI", "endpoint": "https://www.cnki.net"},
        {"source": "WANFANG", "endpoint": "https://www.wanfangdata.com.cn"},
        {"source": "CQVIP", "endpoint": "https://www.cqvip.com"},
    ]


@dataclass
class PriorArtScanStage:
    """Stage 02: Produce prior-art resource stubs for follow-up scanning.

    Minimal behavior:
    - Emits a fixed list of sources/endpoints (no network).
    - Stores it in `ctx.metadata['prior_art_resources']`.
    """

    stage_id: str = "STAGE_02"
    requires: list[str] = field(default_factory=lambda: ["direction_candidates"])
    produces: list[str] = field(
        default_factory=lambda: ["prior_art_resources", "prior_art_evidence_path"]
    )

    def run(self, ctx: StageContext) -> StageResult:
        if "direction_candidates" not in ctx.metadata:
            raise ValueError("Missing required input: direction_candidates")
        candidates = ctx.metadata.get("direction_candidates")
        if not isinstance(candidates, list):
            raise ValueError("ctx.metadata['direction_candidates'] must be a list")

        resources = _stub_resources()
        ctx.metadata["prior_art_resources"] = resources
        evidence_path = _write_prior_art_evidence(
            work_dir=ctx.work_dir,
            topic=str(ctx.metadata.get("topic", "") or ""),
            resources=resources,
            candidates=candidates,
        )
        ctx.metadata["prior_art_evidence_path"] = str(evidence_path)

        result = StageResult(produces=list(self.produces))
        result.outputs = {
            "prior_art_resources": resources,
            "prior_art_evidence_path": str(evidence_path),
        }
        return result


def _write_prior_art_evidence(
    *,
    work_dir: Path,
    topic: str,
    resources: List[Dict[str, str]],
    candidates: List[Dict[str, Any]],
) -> Path:
    lines: List[str] = []
    for idx, resource in enumerate(resources, start=1):
        record = {
            "id": f"e-{idx:03d}",
            "topic": topic or "未命名主题",
            "source": resource.get("source"),
            "endpoint": resource.get("endpoint"),
            "related_direction_ids": [str(c.get("id")) for c in candidates if "id" in c],
            "title": f"{topic or '主题'} 相关证据 {idx}",
            "snippet": f"来自 {resource.get('source')} 的占位证据摘要",
        }
        lines.append(json.dumps(record, ensure_ascii=False))
    path = work_dir / "artifacts" / "prior_art_evidence.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path
