from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from autopatent.pipeline import StageContext, StageResult


def _default_candidates(topic: str) -> List[Dict[str, Any]]:
    # Deterministic yet dynamic candidate set around 5 items.
    base = topic.strip() or "通用"
    count = _candidate_count(base)
    templates = [
        ("可专利化方向探索", 0.35),
        ("差异化实现路径", 0.55),
        ("工程落地与系统方案", 0.45),
        ("协议协商与状态机优化", 0.50),
        ("密钥管理与接口抽象", 0.52),
        ("部署与运维自动化", 0.48),
    ]
    candidates: List[Dict[str, Any]] = []
    for i in range(1, count + 1):
        idx = i - 1
        label, score = templates[idx % len(templates)]
        candidates.append(
            {
                "id": str(i),
                "title": f"{base} 方向 {i}",
                "summary": f"{base} 的{label} (stub)",
                "score": score,
            }
        )
    return candidates


def _candidate_count(base_topic: str) -> int:
    # Produce 4-6 candidates, targeting ~5.
    clean_len = len(base_topic.replace(" ", ""))
    if clean_len <= 6:
        return 4
    if clean_len >= 20:
        return 6
    return 5


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
