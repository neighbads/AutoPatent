from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
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
    produces: list[str] = field(
        default_factory=lambda: ["direction_candidates", "direction_analysis_report_path"]
    )

    def run(self, ctx: StageContext) -> StageResult:
        topic = str(ctx.metadata.get("topic", "") or "")
        existing = ctx.metadata.get("direction_candidates")
        if not isinstance(existing, list) or not existing:
            ctx.metadata["direction_candidates"] = _default_candidates(topic)

        report_path = _write_direction_report(
            work_dir=ctx.work_dir,
            topic=topic,
            candidates=ctx.metadata["direction_candidates"],
        )
        ctx.metadata["direction_analysis_report_path"] = str(report_path)

        result = StageResult(produces=list(self.produces))
        result.outputs = {
            "direction_candidates": ctx.metadata.get("direction_candidates"),
            "direction_analysis_report_path": str(report_path),
        }
        return result


def _write_direction_report(*, work_dir: Path, topic: str, candidates: List[Dict[str, Any]]) -> Path:
    lines = [
        "# 方向分析报告 (MVP stub)",
        "",
        f"- 主题: {topic or '未命名主题'}",
        f"- 候选方向数量: {len(candidates)}",
        "",
    ]
    for idx, candidate in enumerate(candidates, start=1):
        lines.extend(
            [
                f"## 方向 {idx}",
                f"- ID: {candidate.get('id')}",
                f"- 标题: {candidate.get('title', '')}",
                f"- 摘要: {candidate.get('summary', '')}",
                f"- 初始分: {candidate.get('score', 'N/A')}",
                "",
            ]
        )
    path = work_dir / "artifacts" / "direction_analysis_report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
