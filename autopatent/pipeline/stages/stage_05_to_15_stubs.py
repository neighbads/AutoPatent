from __future__ import annotations

"""Stage 05-15 deterministic stubs (CN MVP).

Goal:
- Provide a stable artifact chain under `<work_dir>/artifacts/`.
- Export a minimal deliverable package under `<work_dir>/deliverables/`.

The only contract currently enforced by smoke tests is that:
- `deliverables/disclosure.md` exists
- `deliverables/oa_response_playbook.md` exists

Everything here is intentionally minimal and deterministic (no network, no LLM).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from autopatent.pipeline import StageContext, StageResult


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _read_text_if_exists(path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _topic(ctx: StageContext) -> str:
    raw = ctx.metadata.get("topic")
    t = str(raw or "").strip()
    return t or "未命名主题"


def _selected_direction_id(ctx: StageContext) -> str:
    raw = ctx.metadata.get("selected_direction_id")
    sid = str(raw or "").strip()
    return sid or "N/A"


def _render_disclosure_draft(ctx: StageContext) -> str:
    # Keep content short and stable; it is a scaffold for future real generation.
    t = _topic(ctx)
    sid = _selected_direction_id(ctx)
    return (
        "# 技术交底书 (MVP stub)\n"
        "\n"
        f"- 主题: {t}\n"
        f"- 选定方向ID: {sid}\n"
        "\n"
        "## 背景\n"
        "本文档为 CN MVP 阶段的占位产物，用于验证产物链路与导出包。\n"
        "\n"
        "## 技术方案概述\n"
        "以确定性规则生成的结构化描述 (stub)。\n"
    )


def _render_oa_response_playbook_draft(ctx: StageContext) -> str:
    t = _topic(ctx)
    sid = _selected_direction_id(ctx)
    return (
        "# OA 答复剧本 (MVP stub)\n"
        "\n"
        f"- 主题: {t}\n"
        f"- 选定方向ID: {sid}\n"
        "\n"
        "## 目标\n"
        "提供最小可用的答复框架，用于测试导出链路 (stub)。\n"
        "\n"
        "## 模板\n"
        "1. 识别审查意见类型\n"
        "2. 选择答复策略\n"
        "3. 准备对比表与修改说明\n"
    )


@dataclass
class _WriteArtifactStage:
    stage_id: str
    requires: list[str] = field(default_factory=list)
    produces: list[str] = field(default_factory=list)

    relpath: str = ""
    output_key: str = ""
    render: Optional[Callable[[StageContext], str]] = None

    def run(self, ctx: StageContext) -> StageResult:
        content = self.render(ctx) if self.render is not None else ""
        path = ctx.work_dir / self.relpath
        _atomic_write_text(path, content)
        ctx.metadata[self.output_key] = str(path)
        return StageResult(
            produces=list(self.produces) if self.produces else [self.output_key],
            outputs={self.output_key: str(path)},
        )


@dataclass
class _NoOpStage:
    stage_id: str
    requires: list[str] = field(default_factory=list)
    produces: list[str] = field(default_factory=list)

    def run(self, ctx: StageContext) -> StageResult:
        # Keep a trace in ctx so debugging pipelines is easier.
        history = ctx.metadata.get("stage_history")
        if not isinstance(history, list):
            history = []
        history.append(self.stage_id)
        ctx.metadata["stage_history"] = history
        return StageResult(produces=list(self.produces))


@dataclass
class DeliverablesExportStage:
    stage_id: str = "STAGE_15"
    requires: list[str] = field(
        default_factory=lambda: ["disclosure_draft_path", "oa_response_playbook_draft_path"]
    )
    produces: list[str] = field(
        default_factory=lambda: [
            "deliverables_disclosure_path",
            "deliverables_oa_response_playbook_path",
        ]
    )

    def run(self, ctx: StageContext) -> StageResult:
        disclosure_src = Path(str(ctx.metadata.get("disclosure_draft_path", "") or ""))
        playbook_src = Path(str(ctx.metadata.get("oa_response_playbook_draft_path", "") or ""))

        disclosure_content = _read_text_if_exists(disclosure_src) or _render_disclosure_draft(ctx)
        playbook_content = _read_text_if_exists(playbook_src) or _render_oa_response_playbook_draft(
            ctx
        )

        out_dir = ctx.work_dir / "deliverables"
        disclosure_out = out_dir / "disclosure.md"
        playbook_out = out_dir / "oa_response_playbook.md"

        _atomic_write_text(disclosure_out, disclosure_content)
        _atomic_write_text(playbook_out, playbook_content)

        ctx.metadata["deliverables_disclosure_path"] = str(disclosure_out)
        ctx.metadata["deliverables_oa_response_playbook_path"] = str(playbook_out)

        return StageResult(
            produces=list(self.produces),
            outputs={
                "deliverables_disclosure_path": str(disclosure_out),
                "deliverables_oa_response_playbook_path": str(playbook_out),
            },
        )


def stage_05_to_15_stages() -> List[object]:
    """Return Stage 05-15 instances for the CN MVP pipeline."""

    return [
        _WriteArtifactStage(
            stage_id="STAGE_05",
            requires=["selected_direction_id"],
            produces=["disclosure_draft_path"],
            relpath="artifacts/stage_05_disclosure_draft.md",
            output_key="disclosure_draft_path",
            render=_render_disclosure_draft,
        ),
        _NoOpStage(stage_id="STAGE_06"),
        _NoOpStage(stage_id="STAGE_07"),
        _NoOpStage(stage_id="STAGE_08"),
        _NoOpStage(stage_id="STAGE_09"),
        _NoOpStage(stage_id="STAGE_10"),
        _NoOpStage(stage_id="STAGE_11"),
        _NoOpStage(stage_id="STAGE_12"),
        _NoOpStage(stage_id="STAGE_13"),
        _WriteArtifactStage(
            stage_id="STAGE_14",
            requires=["selected_direction_id"],
            produces=["oa_response_playbook_draft_path"],
            relpath="artifacts/stage_14_oa_response_playbook_draft.md",
            output_key="oa_response_playbook_draft_path",
            render=_render_oa_response_playbook_draft,
        ),
        DeliverablesExportStage(),
    ]

