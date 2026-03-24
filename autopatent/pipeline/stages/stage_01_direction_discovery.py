from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from autopatent.pipeline import StageContext, StageResult


def _default_candidates(topic: str) -> List[Dict[str, Any]]:
    # Deterministic stub candidates.
    base = topic.strip() or "通用"
    return [
        {
            "id": "1",
            "title": f"{base} 方向 1",
            "summary": f"{base} 的可专利化方向探索 (stub)",
            "score": 0.35,
        },
        {
            "id": "2",
            "title": f"{base} 方向 2",
            "summary": f"{base} 的差异化实现路径 (stub)",
            "score": 0.55,
        },
        {
            "id": "3",
            "title": f"{base} 方向 3",
            "summary": f"{base} 的工程落地与系统方案 (stub)",
            "score": 0.45,
        },
    ]


@dataclass
class DirectionDiscoveryStage:
    """Stage 01: Produce candidate "directions" for further scanning/scoring."""

    stage_id: str = "STAGE_01"
    requires: list[str] = field(default_factory=list)
    produces: list[str] = field(default_factory=lambda: ["direction_candidates"])

    def run(self, ctx: StageContext) -> StageResult:
        topic = str(ctx.metadata.get("topic", "") or "")
        existing = ctx.metadata.get("direction_candidates")
        if not isinstance(existing, list) or not existing:
            ctx.metadata["direction_candidates"] = _default_candidates(topic)

        result = StageResult(produces=list(self.produces))
        result.outputs = {"direction_candidates": ctx.metadata.get("direction_candidates")}
        return result
