from __future__ import annotations

"""Stage 05-15 deterministic stubs (CN MVP).

Goal:
- Provide a stable artifact chain under `<work_dir>/artifacts/`.
- Export a minimal deliverable package under `<work_dir>/deliverables/` and
  `<work_dir>/final_package/`.

Everything here is deterministic (no network, no LLM).
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from autopatent.pipeline import Stage, StageContext, StageResult
from autopatent.templates.renderer import DEFAULT_TEMPLATE_NAME, render_disclosure


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def _read_text_if_exists(path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    if not path.exists() or not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _read_json_if_exists(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if path is None:
        return None
    if not path.exists() or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed JSON artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in artifact: {path}")
    return payload


def _safe_artifact_source(ctx: StageContext, key: str) -> Optional[Path]:
    raw = ctx.metadata.get(key)
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None

    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = (ctx.work_dir / candidate).resolve()
    else:
        candidate = candidate.resolve()

    allowed_root = (ctx.work_dir / "artifacts").resolve()
    try:
        candidate.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(f"Unsafe artifact source outside work_dir/artifacts: {candidate}") from exc
    return candidate


def _topic(ctx: StageContext) -> str:
    raw = ctx.metadata.get("topic")
    t = str(raw or "").strip()
    return t or "未命名主题"


def _selected_direction_id(ctx: StageContext) -> str:
    raw = ctx.metadata.get("selected_direction_id")
    sid = str(raw or "").strip()
    return sid or "N/A"


def _build_disclosure_context(ctx: StageContext) -> Dict[str, Any]:
    t = _topic(ctx)
    sid = _selected_direction_id(ctx)
    code_dir = str(ctx.metadata.get("code_dir") or "").strip()
    return {
        # Template placeholders used by cn_invention_default.*.j2
        "title": f"{t} 的系统与方法",
        "technical_field": f"{t} 相关密码协议与网络安全技术",
        "background": f"围绕 {t} 的工程部署与兼容需求，现有方案存在迁移成本高的问题。",
        "summary": f"提出面向方向 {sid} 的分层实现方案，兼顾安全性、可实施性与迁移可行性。",
        "embodiments": "示例实施方式包括控制面协商、数据面封装与策略编排三个子模块。",
        # CN MVP design doc required context fields
        "invention_title": f"{t} 的系统与方法",
        "technical_field_cn": f"{t} 相关密码协议与网络安全技术",
        "background_art": "现有方案在兼容性、性能与可验证性方面存在权衡。",
        "problems_to_solve": "如何在保证兼容性的前提下提升安全性与可部署性。",
        "core_solution": "采用分层架构与可验证组件，实现协议协商与数据面处理解耦。",
        "technical_effects": "提升握手鲁棒性、降低迁移风险并形成清晰证据链。",
        "embodiments_detail": "提供控制面与数据面的联合实施路径。",
        "optional_figures_desc": ["系统模块图", "协商时序图", "数据处理流程图"],
        "claim_seed_points": [
            "混合协商状态机",
            "分层密钥派生接口",
            "策略驱动的数据面转换机制",
        ],
        "evidence_refs": [
            "artifacts/prior_art_evidence.jsonl",
            "artifacts/direction_scores.json",
            "artifacts/direction_analysis_report.md",
        ],
        "code_evidence": [code_dir] if code_dir else [],
    }


def _render_title_finalization(ctx: StageContext) -> str:
    t = _topic(ctx)
    sid = _selected_direction_id(ctx)
    return (
        "# 题目与主保护点确认 (MVP stub)\n\n"
        f"- 主题: {t}\n"
        f"- 选定方向ID: {sid}\n"
        "- 题目: 一种面向网络安全协议的混合抗量子实现系统与方法\n"
        "- 主保护点: 混合协商流程、分层密钥管理、策略驱动实现路径\n"
    )


def _render_disclosure_outline(ctx: StageContext) -> str:
    return (
        "# 技术交底书大纲 (MVP stub)\n\n"
        "1. 技术领域\n"
        "2. 背景技术\n"
        "3. 发明内容\n"
        "4. 附图说明\n"
        "5. 具体实施方式\n"
    )


def _render_disclosure_validation_report(ctx: StageContext) -> str:
    t = _topic(ctx)
    return (
        "# 技术交底书校验报告 (MVP stub)\n\n"
        f"- 主题: {t}\n"
        "- 结构完整性: 通过\n"
        "- 必填字段完整性: 通过\n"
        "- 可专利性链路: 占位评估为中风险\n"
    )


def _render_claim_strategy(ctx: StageContext) -> str:
    return (
        "# 权利要求布局策略 (MVP stub)\n\n"
        "1. 主权利要求聚焦系统架构约束\n"
        "2. 从属权利要求覆盖流程细节与参数范围\n"
        "3. 预留实现变体用于后续迭代补强\n"
    )


def _render_claims_draft(ctx: StageContext) -> str:
    return (
        "# 权利要求书草案 (MVP stub)\n\n"
        "1. 一种系统，其特征在于包括协商模块、密钥模块与策略模块。\n"
        "2. 根据权利要求1所述系统，其中协商模块支持多策略切换。\n"
        "3. 根据权利要求1所述系统，其中密钥模块支持分层派生。\n"
    )


def _render_spec_draft(ctx: StageContext) -> str:
    return (
        "# 说明书草案 (MVP stub)\n\n"
        "## 背景技术\n"
        "现有方案在兼容性与可验证性方面存在不足。\n\n"
        "## 发明内容\n"
        "提出一种分层架构方案，支持工程部署与策略扩展。\n\n"
        "## 具体实施方式\n"
        "描述控制面与数据面协同的实施流程。\n"
    )


def _render_patent_legal_validate(ctx: StageContext) -> str:
    return (
        "# 法律与格式校验 (MVP stub)\n\n"
        "- CN 口径格式检查: 通过\n"
        "- 用语一致性: 通过\n"
        "- 术语歧义风险: 低\n"
    )


def _render_novelty_risk_report(ctx: StageContext) -> str:
    return (
        "# 新颖性/创造性风险报告 (MVP stub)\n\n"
        "- 风险等级: 中\n"
        "- 主要风险点: 现有技术可能覆盖部分流程性特征\n"
        "- 建议: 强化系统约束与实施细节限定\n"
    )


def _render_oa_response_playbook_draft(ctx: StageContext) -> str:
    t = _topic(ctx)
    sid = _selected_direction_id(ctx)
    return (
        "# OA 答复剧本 (MVP stub)\n\n"
        f"- 主题: {t}\n"
        f"- 选定方向ID: {sid}\n\n"
        "## 目标\n"
        "提供最小可用的答复框架，用于测试导出链路 (stub)。\n\n"
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
class _WriteJsonArtifactStage:
    stage_id: str
    requires: list[str] = field(default_factory=list)
    produces: list[str] = field(default_factory=list)

    relpath: str = ""
    output_key: str = ""
    render_json: Optional[Callable[[StageContext], Dict[str, Any]]] = None

    def run(self, ctx: StageContext) -> StageResult:
        payload = self.render_json(ctx) if self.render_json is not None else {}
        path = ctx.work_dir / self.relpath
        _atomic_write_json(path, payload)
        ctx.metadata[self.output_key] = str(path)
        return StageResult(
            produces=list(self.produces) if self.produces else [self.output_key],
            outputs={self.output_key: str(path)},
        )


@dataclass
class _RenderDisclosureStage:
    stage_id: str = "STAGE_07"
    requires: list[str] = field(default_factory=lambda: ["disclosure_context_path"])
    produces: list[str] = field(
        default_factory=lambda: [
            "disclosure_draft_path",
            "disclosure_docx_markdown_path",
            "template_used",
        ]
    )

    def run(self, ctx: StageContext) -> StageResult:
        context_path = _safe_artifact_source(ctx, "disclosure_context_path")
        disclosure_context = _read_json_if_exists(context_path) or _build_disclosure_context(ctx)

        template_name = str(ctx.metadata.get("template") or DEFAULT_TEMPLATE_NAME)
        rendered = render_disclosure(context=disclosure_context, template_name=template_name)

        markdown_path = ctx.work_dir / "artifacts" / "disclosure.md"
        docx_markdown_path = ctx.work_dir / "artifacts" / "disclosure.docx.md"
        _atomic_write_text(markdown_path, rendered.markdown)
        _atomic_write_text(docx_markdown_path, rendered.docx_markdown)

        ctx.metadata["disclosure_draft_path"] = str(markdown_path)
        ctx.metadata["disclosure_docx_markdown_path"] = str(docx_markdown_path)
        ctx.metadata["template_used"] = rendered.template_name

        return StageResult(
            produces=list(self.produces),
            outputs={
                "disclosure_draft_path": str(markdown_path),
                "disclosure_docx_markdown_path": str(docx_markdown_path),
                "template_used": rendered.template_name,
            },
        )


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
            "deliverables_disclosure_validation_report_path",
            "final_package_dir",
        ]
    )

    def run(self, ctx: StageContext) -> StageResult:
        disclosure_src = _safe_artifact_source(ctx, "disclosure_draft_path")
        playbook_src = _safe_artifact_source(ctx, "oa_response_playbook_draft_path")

        disclosure_content = _read_text_if_exists(disclosure_src) or ""
        playbook_content = _read_text_if_exists(playbook_src) or _render_oa_response_playbook_draft(ctx)
        validation_content = _read_text_if_exists(
            _safe_artifact_source(ctx, "disclosure_validation_report_path")
        ) or _render_disclosure_validation_report(ctx)
        claims_content = _read_text_if_exists(_safe_artifact_source(ctx, "claims_draft_path")) or _render_claims_draft(
            ctx
        )
        spec_content = _read_text_if_exists(_safe_artifact_source(ctx, "spec_draft_path")) or _render_spec_draft(
            ctx
        )
        novelty_content = _read_text_if_exists(
            _safe_artifact_source(ctx, "novelty_risk_report_path")
        ) or _render_novelty_risk_report(ctx)

        out_dir = ctx.work_dir / "deliverables"
        final_package_dir = ctx.work_dir / "final_package"

        disclosure_out = out_dir / "disclosure.md"
        playbook_out = out_dir / "oa_response_playbook.md"
        validation_out = out_dir / "disclosure_validation_report.md"
        claims_out = out_dir / "claims_draft.md"
        spec_out = out_dir / "spec_draft.md"
        novelty_out = out_dir / "novelty_risk_report.md"

        _atomic_write_text(disclosure_out, disclosure_content)
        _atomic_write_text(playbook_out, playbook_content)
        _atomic_write_text(validation_out, validation_content)
        _atomic_write_text(claims_out, claims_content)
        _atomic_write_text(spec_out, spec_content)
        _atomic_write_text(novelty_out, novelty_content)

        _atomic_write_text(final_package_dir / "disclosure.md", disclosure_content)
        _atomic_write_text(final_package_dir / "oa_response_playbook.md", playbook_content)
        _atomic_write_text(final_package_dir / "disclosure_validation_report.md", validation_content)
        _atomic_write_text(final_package_dir / "claims_draft.md", claims_content)
        _atomic_write_text(final_package_dir / "spec_draft.md", spec_content)
        _atomic_write_text(final_package_dir / "novelty_risk_report.md", novelty_content)

        ctx.metadata["deliverables_disclosure_path"] = str(disclosure_out)
        ctx.metadata["deliverables_oa_response_playbook_path"] = str(playbook_out)
        ctx.metadata["deliverables_disclosure_validation_report_path"] = str(validation_out)
        ctx.metadata["final_package_dir"] = str(final_package_dir)

        return StageResult(
            produces=list(self.produces),
            outputs={
                "deliverables_disclosure_path": str(disclosure_out),
                "deliverables_oa_response_playbook_path": str(playbook_out),
                "deliverables_disclosure_validation_report_path": str(validation_out),
                "final_package_dir": str(final_package_dir),
            },
        )


def stage_05_to_15_stages() -> List[Stage]:
    """Return Stage 05-15 instances for the CN MVP pipeline."""

    return [
        _WriteArtifactStage(
            stage_id="STAGE_05",
            requires=["selected_direction_id"],
            produces=["title_finalization_path"],
            relpath="artifacts/stage_05_title_finalization.md",
            output_key="title_finalization_path",
            render=_render_title_finalization,
        ),
        _WriteJsonArtifactStage(
            stage_id="STAGE_06",
            requires=["selected_direction_id"],
            produces=["disclosure_context_path"],
            relpath="artifacts/disclosure_context.json",
            output_key="disclosure_context_path",
            render_json=_build_disclosure_context,
        ),
        _RenderDisclosureStage(),
        _WriteArtifactStage(
            stage_id="STAGE_08",
            requires=["disclosure_draft_path"],
            produces=["disclosure_validation_report_path"],
            relpath="artifacts/disclosure_validation_report.md",
            output_key="disclosure_validation_report_path",
            render=_render_disclosure_validation_report,
        ),
        _WriteArtifactStage(
            stage_id="STAGE_09",
            requires=["disclosure_validation_report_path"],
            produces=["claim_strategy_path"],
            relpath="artifacts/stage_09_claim_strategy.md",
            output_key="claim_strategy_path",
            render=_render_claim_strategy,
        ),
        _WriteArtifactStage(
            stage_id="STAGE_10",
            requires=["claim_strategy_path"],
            produces=["claims_draft_path"],
            relpath="artifacts/claims_draft.md",
            output_key="claims_draft_path",
            render=_render_claims_draft,
        ),
        _WriteArtifactStage(
            stage_id="STAGE_11",
            requires=["claims_draft_path"],
            produces=["spec_draft_path"],
            relpath="artifacts/spec_draft.md",
            output_key="spec_draft_path",
            render=_render_spec_draft,
        ),
        _WriteArtifactStage(
            stage_id="STAGE_12",
            requires=["spec_draft_path"],
            produces=["patent_legal_validate_path"],
            relpath="artifacts/stage_12_legal_validate.md",
            output_key="patent_legal_validate_path",
            render=_render_patent_legal_validate,
        ),
        _WriteArtifactStage(
            stage_id="STAGE_13",
            requires=["patent_legal_validate_path"],
            produces=["novelty_risk_report_path"],
            relpath="artifacts/novelty_risk_report.md",
            output_key="novelty_risk_report_path",
            render=_render_novelty_risk_report,
        ),
        _WriteArtifactStage(
            stage_id="STAGE_14",
            requires=["novelty_risk_report_path"],
            produces=["oa_response_playbook_draft_path"],
            relpath="artifacts/stage_14_oa_response_playbook_draft.md",
            output_key="oa_response_playbook_draft_path",
            render=_render_oa_response_playbook_draft,
        ),
        DeliverablesExportStage(),
    ]
