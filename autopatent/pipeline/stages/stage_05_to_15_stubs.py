from __future__ import annotations

"""Stage 05-15 deterministic synthesis pipeline (CN MVP+).

Goal:
- Provide a stable artifact chain under `<work_dir>/artifacts/`.
- Export a structured deliverable package under `<work_dir>/deliverables/` and
  `<work_dir>/final_package/`.

By default this module is deterministic. If `ctx.metadata["llm"]` is provided,
selected stages will attempt LLM-assisted drafting and fall back to
deterministic structured text
on failure.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from autopatent.llm import OpenAICompatibleClient
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


def _direction_candidates(ctx: StageContext) -> List[Dict[str, Any]]:
    raw = ctx.metadata.get("direction_candidates")
    if not isinstance(raw, list):
        return []
    result: List[Dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            result.append(item)
    return result


def _selected_direction(ctx: StageContext) -> Dict[str, Any]:
    sid = _selected_direction_id(ctx)
    for item in _direction_candidates(ctx):
        if str(item.get("id", "")).strip() == sid:
            return item
    return {}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_jsonl_if_exists(path: Optional[Path]) -> List[Dict[str, Any]]:
    if path is None or not path.exists() or not path.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _load_prior_art_evidence(ctx: StageContext) -> List[Dict[str, Any]]:
    path = _safe_artifact_source(ctx, "prior_art_evidence_path")
    if path is None:
        path = ctx.work_dir / "artifacts" / "prior_art_evidence.jsonl"
    return _read_jsonl_if_exists(path)


def _load_direction_scores(ctx: StageContext) -> Dict[str, Any]:
    path = _safe_artifact_source(ctx, "direction_scores_path")
    if path is None:
        path = ctx.work_dir / "artifacts" / "direction_scores.json"
    payload = _read_json_if_exists(path)
    return payload if isinstance(payload, dict) else {}


def _top_evidence_titles(ctx: StageContext, limit: int = 5) -> List[str]:
    evidence = _load_prior_art_evidence(ctx)
    titles: List[str] = []
    for item in evidence:
        title = str(item.get("title", "")).strip()
        source = str(item.get("source", "")).strip()
        if not title:
            continue
        snippet = f"[{source}] {title}" if source else title
        titles.append(snippet)
        if len(titles) >= limit:
            break
    return titles


def _list_to_nonempty_strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    rows: List[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            rows.append(text)
    return rows


def _try_llm_text(*, ctx: StageContext, task: str, prompt: str, fallback: str) -> str:
    runtime = ctx.metadata.get("llm")
    if not isinstance(runtime, dict):
        return fallback
    try:
        client = OpenAICompatibleClient.from_runtime_mapping(runtime)
        text = client.chat(
            system_prompt="你是中国发明专利写作助手。输出中文专业文本，结构清晰，避免空话。",
            user_prompt=prompt,
            max_tokens=int(runtime.get("max_tokens", 4096)),
        )
    except Exception:
        return fallback
    content = str(text or "").strip()
    cleaned = _sanitize_llm_output(task=task, text=content)
    return cleaned or fallback


def _sanitize_llm_output(*, task: str, text: str) -> str:
    if not text:
        return ""
    lines = str(text).replace("\r\n", "\n").split("\n")
    # Remove leading "AI assistant style" preface lines.
    lead_prefixes = (
        "以下为",
        "以下是",
        "以下可",
        "下面给出",
        "以下内容",
    )
    while lines:
        first = lines[0].strip()
        if not first:
            lines.pop(0)
            continue
        if any(first.startswith(p) for p in lead_prefixes):
            lines.pop(0)
            continue
        if set(first) <= {"-", "*", "—", "=", " "}:
            lines.pop(0)
            continue
        break

    # Cut tail "if you want, I can continue..." assistant chatter.
    tail_prefixes = (
        "如需",
        "如果你愿意",
        "如果需要",
        "若需",
        "我还可以",
        "你还可以",
    )
    cut_at = None
    for idx, line in enumerate(lines):
        s = line.strip()
        if any(s.startswith(p) for p in tail_prefixes):
            cut_at = idx
            break
    if cut_at is not None:
        lines = lines[:cut_at]

    # Remove explicit temporary sections.
    filtered: List[str] = []
    for line in lines:
        s = line.strip()
        if s in ("## LLM 扩展草案", "# LLM 扩展草案"):
            continue
        if re.fullmatch(r"[\-*_=]{3,}", s):
            continue
        filtered.append(line.rstrip())

    # Trim empty borders.
    while filtered and not filtered[0].strip():
        filtered.pop(0)
    while filtered and not filtered[-1].strip():
        filtered.pop()
    return "\n".join(filtered).strip()


def _list_to_text(items: Any, prefix: str = "- ") -> str:
    if not isinstance(items, list):
        return ""
    rows = [f"{prefix}{str(item)}" for item in items if str(item).strip()]
    return "\n".join(rows)


def _normalize_disclosure_context_for_render(context: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(context)
    for text_key, list_key in (
        ("evidence_refs_text", "evidence_refs"),
        ("claim_seed_points_text", "claim_seed_points"),
        ("code_evidence_text", "code_evidence"),
    ):
        existing = normalized.get(text_key)
        if isinstance(existing, str) and existing.strip():
            continue
        normalized[text_key] = _list_to_text(normalized.get(list_key))
    return normalized


def _build_disclosure_context(ctx: StageContext) -> Dict[str, Any]:
    t = _topic(ctx)
    sid = _selected_direction_id(ctx)
    code_dir = str(ctx.metadata.get("code_dir") or "").strip()
    claim_seed_points = [
        "混合协商状态机",
        "分层密钥派生接口",
        "策略驱动的数据面转换机制",
    ]
    evidence_refs = [
        "artifacts/prior_art_evidence.jsonl",
        "artifacts/direction_scores.json",
        "artifacts/direction_analysis_report.md",
    ]
    code_evidence = [code_dir] if code_dir else []
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
        "claim_seed_points": claim_seed_points,
        "evidence_refs": evidence_refs,
        "code_evidence": code_evidence,
        "evidence_refs_text": _list_to_text(evidence_refs),
        "claim_seed_points_text": _list_to_text(claim_seed_points),
        "code_evidence_text": _list_to_text(code_evidence),
    }


def _render_title_finalization(ctx: StageContext) -> str:
    t = _topic(ctx)
    sid = _selected_direction_id(ctx)
    selected = _selected_direction(ctx)
    selected_title = str(selected.get("title", "")).strip() or f"{t} 方向 {sid}"
    selected_summary = str(selected.get("summary", "")).strip() or "未提供方向摘要。"
    selected_score = _safe_float(selected.get("score", 0.0))
    direction_scores = _load_direction_scores(ctx)
    candidate_count = len(direction_scores.get("candidates", [])) if isinstance(direction_scores.get("candidates"), list) else len(_direction_candidates(ctx))
    evidence_titles = _top_evidence_titles(ctx, limit=3)
    evidence_bullets = _list_to_text(evidence_titles) if evidence_titles else "- 暂无检索证据条目，建议先完成 Stage 02 在线检索。"

    return (
        "# 题目与主保护点确认\n\n"
        "## 输入摘要\n"
        f"- 主题: {t}\n"
        f"- 选定方向ID: {sid}\n"
        f"- 方向标题: {selected_title}\n"
        f"- 方向摘要: {selected_summary}\n"
        f"- 方向评分: {selected_score:.3f}\n"
        f"- 候选方向总数: {candidate_count}\n\n"
        "## 推荐题目\n"
        f"1. 一种{t}的系统及方法\n"
        f"2. 一种面向{selected_title}的协议协商与密钥管理方法\n"
        f"3. 一种用于{t}的可验证安全通信平台\n\n"
        "## 主保护点\n"
        "1. 混合协商状态机：对算法协商、回退分支和异常状态进行受控编排。\n"
        "2. 分层密钥管理：将密钥交换、派生、轮换与吊销策略解耦。\n"
        "3. 策略驱动数据面：以策略编排驱动流量保护、审计与运行期治理。\n\n"
        "## 选题依据（证据摘要）\n"
        f"{evidence_bullets}\n"
    )


def _render_disclosure_outline(ctx: StageContext) -> str:
    selected = _selected_direction(ctx)
    direction_title = str(selected.get("title", "")).strip() or f"{_topic(ctx)} 方向 {_selected_direction_id(ctx)}"
    direction_summary = str(selected.get("summary", "")).strip() or "待补充"
    evidence_titles = _top_evidence_titles(ctx, limit=4)
    evidence_bullets = _list_to_text(evidence_titles) if evidence_titles else "- 待补充检索证据条目。"
    return (
        "# 技术交底书大纲\n\n"
        "## 选题定位\n"
        f"- 方向标题: {direction_title}\n"
        f"- 方向摘要: {direction_summary}\n\n"
        "## 章节结构\n"
        "1. 技术领域：明确适用协议栈、密码体系与工程部署边界。\n"
        "2. 背景技术：说明现有方案在兼容性、安全性、可运维性上的缺口。\n"
        "3. 发明内容：给出系统方案、关键模块、接口约束与策略机制。\n"
        "4. 附图说明：列出架构图、时序图、流程图及其解释要点。\n"
        "5. 具体实施方式：覆盖初始化、协商、密钥派生、运行治理全流程。\n\n"
        "## 检索证据锚点\n"
        f"{evidence_bullets}\n"
    )


def _render_system_architecture(ctx: StageContext) -> str:
    t = _topic(ctx)
    sid = _selected_direction_id(ctx)
    return (
        "# 系统架构描述\n\n"
        f"- 主题: {t}\n"
        f"- 选定方向ID: {sid}\n\n"
        "## 架构分层\n"
        "1. 接入与协商层：负责协议协商、能力声明、版本与算法策略匹配。\n"
        "2. 密钥与证书层：负责证书链验证、密钥交换、会话密钥派生与生命周期管理。\n"
        "3. 数据与策略层：负责数据面加解密、策略执行、审计与告警。\n\n"
        "## 核心模块\n"
        "- 协商控制模块：维护握手状态机，控制协商步骤与回退策略。\n"
        "- 密钥管理模块：统一管理经典/抗量子密钥材料、派生与轮换。\n"
        "- 证书与信任模块：实现证书解析、链验证、撤销状态检查。\n"
        "- 策略编排模块：按场景下发策略并驱动数据面执行。\n"
        "- 可观测性模块：输出性能指标、安全事件与变更审计记录。\n"
    )


def _render_process_stages(ctx: StageContext) -> str:
    t = _topic(ctx)
    return (
        "# 流程与详细阶段描述\n\n"
        f"以下流程围绕“{t}”的工程落地定义：\n\n"
        "1. 阶段A 连接初始化：加载策略、证书链与算法能力配置。\n"
        "2. 阶段B 能力协商：客户端/服务端交换能力并确定协商路径。\n"
        "3. 阶段C 身份验证：完成证书链验证、撤销状态检查与失败分支处理。\n"
        "4. 阶段D 密钥协商与派生：执行密钥交换并生成握手密钥、会话密钥。\n"
        "5. 阶段E 加密通信建立：完成握手确认并切换到应用数据保护。\n"
        "6. 阶段F 运行期治理：执行密钥轮换、策略更新、异常告警与审计归档。\n\n"
        "## 失败与回退处理\n"
        "- 协商失败：记录失败原因，触发回退策略或中止连接。\n"
        "- 证书失败：拒绝连接并输出可追踪审计事件。\n"
        "- 性能退化：切换策略档位并上报关键性能指标。\n"
    )


def _render_figures_and_tables_plan(ctx: StageContext) -> str:
    sid = _selected_direction_id(ctx)
    image_hints = []
    arch_img = str(ctx.metadata.get("architecture_image_path") or "").strip()
    flow_img = str(ctx.metadata.get("process_image_path") or "").strip()
    if arch_img:
        image_hints.append(f"- 架构图图片: {arch_img}")
    if flow_img:
        image_hints.append(f"- 流程图图片: {flow_img}")
    image_section = "\n".join(image_hints) if image_hints else "- 图片渲染：当前环境未生成（缺少 mmdc 时属预期）。"
    return (
        "# 附图与图表计划\n\n"
        f"面向方向ID {sid}，建议在交底书与说明书中包含以下图表：\n\n"
        "## 附图清单\n"
        "1. 图1 系统总体架构图（模块关系与边界）。\n"
        "2. 图2 握手协商时序图（请求、响应、校验、完成）。\n"
        "3. 图3 密钥派生流程图（输入、派生、输出与更新）。\n"
        "4. 图4 运行期策略执行流程图（策略下发、执行、反馈、告警）。\n\n"
        "## 图表说明（文字版）\n"
        "| 编号 | 图表名称 | 说明 |\n"
        "| --- | --- | --- |\n"
        "| 图1 | 系统总体架构图 | 展示协商层、密钥层、数据层及其接口关系。 |\n"
        "| 图2 | 握手协商时序图 | 展示从能力协商到握手完成的关键消息序列。 |\n"
        "| 图3 | 密钥派生流程图 | 展示密钥交换输入与派生输出链路。 |\n"
        "| 图4 | 策略执行流程图 | 展示策略驱动与异常处理闭环。 |\n\n"
        "## 产物文件（ASCII -> Mermaid -> Image）\n"
        "- ASCII 架构图: artifacts/architecture_ascii.txt\n"
        "- ASCII 流程图: artifacts/process_flow_ascii.txt\n"
        "- Mermaid 架构图: artifacts/architecture.mmd\n"
        "- Mermaid 流程图: artifacts/process_flow.mmd\n"
        f"{image_section}\n"
    )


def _render_structured_appendix(
    *,
    architecture_text: str,
    process_text: str,
    figures_text: str,
) -> str:
    arch = _strip_first_heading(architecture_text)
    process = _strip_first_heading(process_text)
    figures = _strip_first_heading(figures_text)
    return (
        "## 系统架构描述（补充）\n\n"
        f"{arch}\n\n"
        "## 关键流程与阶段说明（补充）\n\n"
        f"{process}\n\n"
        "## 附图与图表说明（补充）\n\n"
        f"{figures}\n"
    )


def _strip_first_heading(text: str) -> str:
    lines = str(text or "").strip().splitlines()
    if not lines:
        return ""
    if lines[0].lstrip().startswith("#"):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _render_architecture_ascii(ctx: StageContext) -> str:
    sid = _selected_direction_id(ctx)
    return (
        "Anti-Quantum SSL/TLS System Architecture\n"
        "=======================================\n"
        f"Direction: {sid}\n\n"
        "Client\n"
        "  |\n"
        "  | 1) Capability + Hello\n"
        "  v\n"
        "+------------------------+        +----------------------+\n"
        "| Negotiation Controller | <----> | Policy Orchestrator  |\n"
        "+------------------------+        +----------------------+\n"
        "            |\n"
        "            | 2) Certificate & Key Exchange\n"
        "            v\n"
        "+------------------------+        +----------------------+\n"
        "| Cert/Trust Validator   | <----> | Key Management (PQC) |\n"
        "+------------------------+        +----------------------+\n"
        "            |\n"
        "            | 3) Session Keys\n"
        "            v\n"
        "+------------------------+\n"
        "| Data Plane Encryptor   |\n"
        "+------------------------+\n"
        "            |\n"
        "            v\n"
        "       Secure Tunnel\n"
    )


def _render_process_ascii(ctx: StageContext) -> str:
    return (
        "PQC SSL/TLS Runtime Flow\n"
        "========================\n"
        "[A] Init Policy/Cert/Algo\n"
        "   |\n"
        "[B] Capability Negotiation\n"
        "   |\n"
        "[C] Certificate Verification\n"
        "   |--fail--> [Abort + Audit]\n"
        "   |\n"
        "[D] Hybrid Key Exchange + Derive Keys\n"
        "   |\n"
        "[E] Secure Session Established\n"
        "   |\n"
        "[F] Runtime Governance (rotate/update/alert)\n"
    )


def _render_architecture_mermaid(ctx: StageContext) -> str:
    return (
        "flowchart TD\n"
        "    C[Client] --> N[Negotiation Controller]\n"
        "    N <--> P[Policy Orchestrator]\n"
        "    N --> V[Cert/Trust Validator]\n"
        "    V <--> K[Key Management PQC]\n"
        "    V --> D[Data Plane Encryptor]\n"
        "    D --> T[Secure Tunnel]\n"
    )


def _render_process_mermaid(ctx: StageContext) -> str:
    return (
        "flowchart TD\n"
        "    A[Init Policy Cert Algo] --> B[Capability Negotiation]\n"
        "    B --> C[Certificate Verification]\n"
        "    C -->|ok| D[Hybrid Key Exchange and Derivation]\n"
        "    C -->|fail| X[Abort and Audit]\n"
        "    D --> E[Secure Session Established]\n"
        "    E --> F[Runtime Governance]\n"
    )


def _try_render_mermaid_png(mermaid_path: Path) -> Optional[Path]:
    mmdc = shutil.which("mmdc")
    if not mmdc:
        return None
    output = mermaid_path.with_suffix(".png")
    cmd = [mmdc, "-i", str(mermaid_path), "-o", str(output)]
    temp_cfg_path: Optional[str] = None
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        cfg_payload = {"args": ["--no-sandbox", "--disable-setuid-sandbox"]}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as fp:
            fp.write(json.dumps(cfg_payload, ensure_ascii=False))
            temp_cfg_path = fp.name
        cmd = [mmdc, "-p", temp_cfg_path, "-i", str(mermaid_path), "-o", str(output)]
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    finally:
        if temp_cfg_path:
            try:
                Path(temp_cfg_path).unlink(missing_ok=True)
            except OSError:
                pass
    return output if output.exists() else None


def _render_diagram_appendix(ctx: StageContext) -> str:
    arch_ascii = _read_text_if_exists(_safe_artifact_source(ctx, "architecture_ascii_path")) or ""
    flow_ascii = _read_text_if_exists(_safe_artifact_source(ctx, "process_ascii_path")) or ""
    arch_mermaid = _read_text_if_exists(_safe_artifact_source(ctx, "architecture_mermaid_path")) or ""
    flow_mermaid = _read_text_if_exists(_safe_artifact_source(ctx, "process_mermaid_path")) or ""
    arch_img = str(ctx.metadata.get("architecture_image_path") or "").strip()
    flow_img = str(ctx.metadata.get("process_image_path") or "").strip()

    lines = [
        "## 图示与流程图（生成产物）",
        "",
        "### 架构图（ASCII）",
        "```text",
        arch_ascii.strip() or "(not generated)",
        "```",
        "",
        "### 流程图（ASCII）",
        "```text",
        flow_ascii.strip() or "(not generated)",
        "```",
        "",
        "### 架构图（Mermaid）",
        "```mermaid",
        arch_mermaid.strip() or "flowchart TD\n    A[not generated]",
        "```",
        "",
        "### 流程图（Mermaid）",
        "```mermaid",
        flow_mermaid.strip() or "flowchart TD\n    A[not generated]",
        "```",
        "",
        "### 图片文件（可选）",
    ]
    if arch_img:
        lines.append(f"- 架构图图片: {arch_img}")
    if flow_img:
        lines.append(f"- 流程图图片: {flow_img}")
    if not arch_img and not flow_img:
        lines.append("- 当前环境未生成 PNG（通常是未安装 `mmdc`）。")
    return "\n".join(lines).strip()


def _render_disclosure_validation_report(ctx: StageContext) -> str:
    t = _topic(ctx)
    disclosure = _read_text_if_exists(_safe_artifact_source(ctx, "disclosure_draft_path")) or ""
    slot_rules = [
        ("技术领域", ["## 技术领域", "## Technical Field"]),
        ("背景技术", ["## 背景技术", "## Background"]),
        ("发明内容", ["## 发明内容", "## Summary"]),
        ("实施方式", ["## 具体实施方式", "## Embodiments"]),
        ("检索附录", ["附录A 检索报告要点", "Appendix"]),
    ]
    missing: List[str] = []
    for label, options in slot_rules:
        if not any(opt in disclosure for opt in options):
            missing.append(label)
    passed = len(missing) <= 1
    score = int(((len(slot_rules) - len(missing)) / max(1, len(slot_rules))) * 100)
    length_hint = len(disclosure.strip())
    evidence_count = len(_load_prior_art_evidence(ctx))
    risk_label = "低"
    if len(missing) >= 2 or length_hint < 1000:
        risk_label = "中"
    if len(missing) >= 3 or length_hint < 600:
        risk_label = "中高"
    missing_text = _list_to_text(missing) if missing else "- 无"
    return (
        "# 技术交底书校验报告\n\n"
        "## 校验结论\n"
        f"- 主题: {t}\n"
        f"- 结论: {'通过' if passed else '需补强'}\n"
        f"- 完整度评分: {score}/100\n"
        f"- 文档长度(字符): {length_hint}\n"
        f"- 已关联证据条目: {evidence_count}\n"
        f"- 可专利性链路风险: {risk_label}\n\n"
        "## 结构检查\n"
        f"- 缺失章节:\n{missing_text}\n\n"
        "## 补强建议\n"
        "1. 对缺失章节补充明确的技术问题-技术手段-技术效果闭环描述。\n"
        "2. 对关键主张补充可追溯证据锚点（检索条目或实现路径）。\n"
        "3. 对实施例增加参数边界、异常分支与可替代实现路径。\n"
    )


def _render_claim_strategy(ctx: StageContext) -> str:
    context = _read_json_if_exists(_safe_artifact_source(ctx, "disclosure_context_path")) or _build_disclosure_context(
        ctx
    )
    claim_points = _list_to_nonempty_strings(context.get("claim_seed_points"))
    if not claim_points:
        claim_points = ["混合协商状态机", "分层密钥派生", "策略驱动数据面治理"]
    evidence_titles = _top_evidence_titles(ctx, limit=5)
    evidence_bullets = _list_to_text(evidence_titles) if evidence_titles else "- 暂无高质量证据，建议补充在线检索。"
    points_bullets = _list_to_text(claim_points)
    return (
        "# 权利要求布局策略\n\n"
        "## 独立权利要求主轴\n"
        "1. 系统主权利要求：限定模块边界、接口关系、策略执行闭环。\n"
        "2. 方法主权利要求：限定协商-认证-派生-切换的流程约束。\n\n"
        "## 从属权利要求分层\n"
        f"{points_bullets}\n\n"
        "## 抗规避约束\n"
        "1. 约束协商状态机的关键状态与失败回退路径。\n"
        "2. 约束密钥派生输入输出关系与生命周期策略。\n"
        "3. 约束策略下发、执行回执与审计记录的闭环行为。\n\n"
        "## 证据映射\n"
        f"{evidence_bullets}\n"
    )


def _render_claims_draft(ctx: StageContext) -> str:
    context = _read_json_if_exists(_safe_artifact_source(ctx, "disclosure_context_path")) or _build_disclosure_context(
        ctx
    )
    claim_points = _list_to_nonempty_strings(context.get("claim_seed_points"))
    while len(claim_points) < 3:
        claim_points.append(f"可验证约束点{len(claim_points)+1}")
    fallback = (
        "# 权利要求书草案\n\n"
        f"1. 一种面向{_topic(ctx)}的安全通信系统，其特征在于，"
        "包括协商控制模块、证书与信任验证模块、密钥管理模块以及策略驱动的数据处理模块；"
        "所述协商控制模块用于根据能力声明和策略规则驱动握手状态迁移，并在异常场景触发受控回退。\n"
        f"2. 根据权利要求1所述的系统，其特征在于，所述协商控制模块至少包含“{claim_points[0]}”约束，"
        "并将该约束与证书验证结果联合判定握手是否继续。\n"
        f"3. 根据权利要求1所述的系统，其特征在于，所述密钥管理模块至少包含“{claim_points[1]}”约束，"
        "用于定义派生输入、派生输出和轮换策略之间的映射关系。\n"
        f"4. 根据权利要求1所述的系统，其特征在于，所述数据处理模块至少包含“{claim_points[2]}”约束，"
        "用于按策略切换加密参数并输出审计日志。\n"
        "5. 根据权利要求1至4任一项所述的系统，其特征在于，"
        "当协商失败、证书校验失败或性能退化时，系统执行预定义分级处置流程并记录证据链。\n"
    )
    prompt = (
        f"主题：{_topic(ctx)}\n"
        f"方向ID：{_selected_direction_id(ctx)}\n"
        "请输出权利要求书草案，至少3条，包含1条独立权利要求与2条从属权利要求。"
    )
    generated = _try_llm_text(ctx=ctx, task="claims_draft", prompt=prompt, fallback="")
    generated = _sanitize_llm_output(task="claims_draft", text=generated)
    if generated:
        if generated.lstrip().startswith("#"):
            return generated
        return f"# 权利要求书草案\n\n{generated}"
    return fallback


def _render_spec_draft(ctx: StageContext) -> str:
    selected = _selected_direction(ctx)
    direction_summary = str(selected.get("summary", "")).strip() or "围绕核心方向形成系统化实施路径。"
    fallback = (
        "# 说明书草案\n\n"
        "## 背景技术\n"
        f"{direction_summary}\n\n"
        "## 发明内容\n"
        "提出一种分层架构方案，覆盖协商控制、信任验证、密钥治理与数据面执行四类能力，"
        "通过策略编排形成可验证的工程闭环。\n\n"
        "## 附图说明\n"
        "图1为系统总体架构图；图2为握手协商时序图；图3为密钥派生流程图；图4为运行期治理流程图。\n\n"
        "## 具体实施方式\n"
        "在实施例中，系统先完成能力协商与证书验证，再执行密钥交换与会话切换，"
        "运行期持续执行策略更新、密钥轮换与审计告警。\n"
    )
    prompt = (
        f"主题：{_topic(ctx)}\n"
        "请输出说明书草案，包含背景技术、发明内容、附图说明、具体实施方式四节，"
        "并显式写出系统架构、流程阶段与图表说明。"
    )
    generated = _try_llm_text(ctx=ctx, task="spec_draft", prompt=prompt, fallback=fallback)
    generated = _sanitize_llm_output(task="spec_draft", text=generated)
    architecture_text = _read_text_if_exists(_safe_artifact_source(ctx, "system_architecture_path")) or _render_system_architecture(
        ctx
    )
    process_text = _read_text_if_exists(_safe_artifact_source(ctx, "process_stages_path")) or _render_process_stages(
        ctx
    )
    figures_text = _read_text_if_exists(
        _safe_artifact_source(ctx, "figures_and_tables_plan_path")
    ) or _render_figures_and_tables_plan(ctx)
    appendix = _render_structured_appendix(
        architecture_text=architecture_text,
        process_text=process_text,
        figures_text=figures_text,
    )
    diagram_appendix = _render_diagram_appendix(ctx)
    return f"{generated.strip()}\n\n{appendix}\n\n{diagram_appendix}"


def _render_patent_legal_validate(ctx: StageContext) -> str:
    claims = _read_text_if_exists(_safe_artifact_source(ctx, "claims_draft_path")) or ""
    spec = _read_text_if_exists(_safe_artifact_source(ctx, "spec_draft_path")) or ""
    disclosure = _read_text_if_exists(_safe_artifact_source(ctx, "disclosure_draft_path")) or ""

    has_numbered_claims = bool(re.search(r"(?m)^\s*1\.\s*", claims))
    has_dependent_claims = "根据权利要求" in claims
    spec_sections_ok = all(
        key in spec for key in ("## 背景技术", "## 发明内容", "## 具体实施方式")
    )
    disclosure_has_appendix = "附录A 检索报告要点" in disclosure

    issues: List[str] = []
    if not has_numbered_claims:
        issues.append("权利要求缺少编号结构（至少应包含第1条）。")
    if not has_dependent_claims:
        issues.append("权利要求未体现从属层级（建议补充“根据权利要求...”条款）。")
    if not spec_sections_ok:
        issues.append("说明书草案缺少关键章节（背景技术/发明内容/具体实施方式）。")
    if not disclosure_has_appendix:
        issues.append("交底书缺少检索附录锚点，证据链可追溯性不足。")

    passed = not issues
    issues_text = _list_to_text(issues) if issues else "- 无阻塞问题。"
    return (
        "# 法律与格式校验报告\n\n"
        "## 校验结论\n"
        f"- 结论: {'通过' if passed else '需修改后复核'}\n"
        f"- 编号结构检查: {'通过' if has_numbered_claims else '未通过'}\n"
        f"- 从属层级检查: {'通过' if has_dependent_claims else '未通过'}\n"
        f"- 说明书章节检查: {'通过' if spec_sections_ok else '未通过'}\n"
        f"- 证据附录检查: {'通过' if disclosure_has_appendix else '未通过'}\n\n"
        "## 问题清单\n"
        f"{issues_text}\n\n"
        "## 修订建议\n"
        "1. 优先修复编号与从属关系，确保权利要求结构可审查。\n"
        "2. 对说明书章节缺口进行补齐，并补充与权利要求的一一映射。\n"
        "3. 强化附录证据与主张条款的关联关系，提升答复审查意见的准备度。\n"
    )


def _render_novelty_risk_report(ctx: StageContext) -> str:
    selected = _selected_direction(ctx)
    direction_score = _safe_float(selected.get("score", 0.0), 0.0)
    evidence = _load_prior_art_evidence(ctx)
    evidence_count = len(evidence)

    risk_level = "中"
    if evidence_count < 4:
        risk_level = "中高"
    elif direction_score >= 0.7 and evidence_count >= 8:
        risk_level = "中低"

    overlap_risks = [
        "流程型特征容易被现有协议实现覆盖。",
        "接口抽象过宽时，审查中可能被认定为常规工程变体。",
        "缺少参数约束时，创造性论证力度不足。",
    ]
    return (
        "# 新颖性/创造性风险报告\n\n"
        "## 风险分级\n"
        f"- 风险等级: {risk_level}\n"
        f"- 方向评分: {direction_score:.3f}\n"
        f"- 证据条目数: {evidence_count}\n\n"
        "## 主要风险点\n"
        f"{_list_to_text(overlap_risks)}\n\n"
        "## 降险策略\n"
        "1. 在独立权利要求中增加状态机与接口依赖的联合约束。\n"
        "2. 在从属权利要求中补充参数边界、异常处置和运行期治理条件。\n"
        "3. 在说明书实施例中补充可验证指标与证据映射表。\n"
    )


def _render_oa_response_playbook_draft(ctx: StageContext) -> str:
    t = _topic(ctx)
    sid = _selected_direction_id(ctx)
    evidence_titles = _top_evidence_titles(ctx, limit=4)
    evidence_refs = _list_to_text(evidence_titles) if evidence_titles else "- 待补充检索证据条目。"
    fallback = (
        "# OA 答复剧本\n\n"
        f"- 主题: {t}\n"
        f"- 选定方向ID: {sid}\n\n"
        "## 审查意见类型\n"
        "1. 新颖性不足：审查员认为关键特征被单一对比文件公开。\n"
        "2. 创造性不足：审查员认为多个对比文件可直接组合得到方案。\n"
        "3. 说明书支持不足：权利要求范围超出说明书记载或实施例支持。\n\n"
        "## 答复策略\n"
        "1. 构建“技术问题-技术手段-技术效果”三段式论证。\n"
        "2. 在权利要求中补充关键约束，避免被解释为常规拼接。\n"
        "3. 用实施例与性能指标增强可实施性与效果证明。\n\n"
        "## 证据映射\n"
        f"{evidence_refs}\n\n"
        "## 修改动作清单\n"
        "1. 修订独立权利要求：增加系统边界与状态约束。\n"
        "2. 修订从属权利要求：补充参数范围与异常处理路径。\n"
        "3. 修订说明书：同步补充附图说明、实施例和证据引用。\n"
    )
    prompt = (
        f"主题：{t}\n方向ID：{sid}\n"
        "请输出中文审查意见答复剧本，包含意见分类、答复策略、证据映射、修改建议。"
    )
    generated = _try_llm_text(ctx=ctx, task="oa_response_playbook", prompt=prompt, fallback=fallback)
    return _sanitize_llm_output(task="oa_response_playbook", text=generated)


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
class _Stage06DisclosureOutlineStage:
    stage_id: str = "STAGE_06"
    requires: list[str] = field(default_factory=lambda: ["selected_direction_id"])
    produces: list[str] = field(
        default_factory=lambda: [
            "disclosure_outline_path",
            "disclosure_context_path",
            "system_architecture_path",
            "process_stages_path",
            "figures_and_tables_plan_path",
            "architecture_ascii_path",
            "process_ascii_path",
            "architecture_mermaid_path",
            "process_mermaid_path",
            "architecture_image_path",
            "process_image_path",
        ]
    )

    def run(self, ctx: StageContext) -> StageResult:
        outline_path = ctx.work_dir / "artifacts" / "disclosure_outline.md"
        _atomic_write_text(outline_path, _render_disclosure_outline(ctx))

        disclosure_context = _build_disclosure_context(ctx)
        context_path = ctx.work_dir / "artifacts" / "disclosure_context.json"
        _atomic_write_json(context_path, disclosure_context)

        architecture_path = ctx.work_dir / "artifacts" / "system_architecture.md"
        process_path = ctx.work_dir / "artifacts" / "process_stages.md"
        arch_ascii_path = ctx.work_dir / "artifacts" / "architecture_ascii.txt"
        flow_ascii_path = ctx.work_dir / "artifacts" / "process_flow_ascii.txt"
        arch_mermaid_path = ctx.work_dir / "artifacts" / "architecture.mmd"
        flow_mermaid_path = ctx.work_dir / "artifacts" / "process_flow.mmd"
        _atomic_write_text(architecture_path, _render_system_architecture(ctx))
        _atomic_write_text(process_path, _render_process_stages(ctx))
        _atomic_write_text(arch_ascii_path, _render_architecture_ascii(ctx))
        _atomic_write_text(flow_ascii_path, _render_process_ascii(ctx))
        _atomic_write_text(arch_mermaid_path, _render_architecture_mermaid(ctx))
        _atomic_write_text(flow_mermaid_path, _render_process_mermaid(ctx))
        arch_image_path = _try_render_mermaid_png(arch_mermaid_path)
        flow_image_path = _try_render_mermaid_png(flow_mermaid_path)
        if arch_image_path is not None:
            ctx.metadata["architecture_image_path"] = str(arch_image_path)
        else:
            ctx.metadata["architecture_image_path"] = None
        if flow_image_path is not None:
            ctx.metadata["process_image_path"] = str(flow_image_path)
        else:
            ctx.metadata["process_image_path"] = None
        figures_path = ctx.work_dir / "artifacts" / "figures_and_tables_plan.md"
        _atomic_write_text(figures_path, _render_figures_and_tables_plan(ctx))

        ctx.metadata["disclosure_outline_path"] = str(outline_path)
        ctx.metadata["disclosure_context_path"] = str(context_path)
        ctx.metadata["system_architecture_path"] = str(architecture_path)
        ctx.metadata["process_stages_path"] = str(process_path)
        ctx.metadata["figures_and_tables_plan_path"] = str(figures_path)
        ctx.metadata["architecture_ascii_path"] = str(arch_ascii_path)
        ctx.metadata["process_ascii_path"] = str(flow_ascii_path)
        ctx.metadata["architecture_mermaid_path"] = str(arch_mermaid_path)
        ctx.metadata["process_mermaid_path"] = str(flow_mermaid_path)

        return StageResult(
            produces=list(self.produces),
            outputs={
                "disclosure_outline_path": str(outline_path),
                "disclosure_context_path": str(context_path),
                "system_architecture_path": str(architecture_path),
                "process_stages_path": str(process_path),
                "figures_and_tables_plan_path": str(figures_path),
                "architecture_ascii_path": str(arch_ascii_path),
                "process_ascii_path": str(flow_ascii_path),
                "architecture_mermaid_path": str(arch_mermaid_path),
                "process_mermaid_path": str(flow_mermaid_path),
                "architecture_image_path": str(arch_image_path) if arch_image_path else None,
                "process_image_path": str(flow_image_path) if flow_image_path else None,
            },
        )


@dataclass
class _RenderDisclosureStage:
    stage_id: str = "STAGE_07"
    requires: list[str] = field(default_factory=lambda: ["disclosure_context_path"])
    produces: list[str] = field(
        default_factory=lambda: [
            "disclosure_draft_path",
            "disclosure_docx_path",
            "disclosure_docx_markdown_path",
            "template_used",
        ]
    )

    def run(self, ctx: StageContext) -> StageResult:
        context_path = _safe_artifact_source(ctx, "disclosure_context_path")
        disclosure_context = _read_json_if_exists(context_path) or _build_disclosure_context(ctx)
        disclosure_context = _normalize_disclosure_context_for_render(disclosure_context)

        template_name = str(ctx.metadata.get("template") or DEFAULT_TEMPLATE_NAME)
        rendered = render_disclosure(context=disclosure_context, template_name=template_name)
        llm_prompt = (
            f"主题：{_topic(ctx)}\n"
            "请基于给定技术背景补充一段技术交底书扩展内容，突出技术效果与实施要点。"
        )
        llm_extra = _try_llm_text(ctx=ctx, task="disclosure_draft", prompt=llm_prompt, fallback="")
        llm_extra = _sanitize_llm_output(task="disclosure_draft", text=llm_extra)
        markdown_body = rendered.markdown
        docx_markdown_body = rendered.docx_markdown
        if llm_extra.strip():
            markdown_body = f"{markdown_body}\n\n## 技术扩展内容\n{llm_extra.strip()}\n"
            docx_markdown_body = f"{docx_markdown_body}\n\n## 技术扩展内容\n{llm_extra.strip()}\n"

        architecture_text = _read_text_if_exists(_safe_artifact_source(ctx, "system_architecture_path")) or _render_system_architecture(
            ctx
        )
        process_text = _read_text_if_exists(_safe_artifact_source(ctx, "process_stages_path")) or _render_process_stages(
            ctx
        )
        figures_text = _read_text_if_exists(
            _safe_artifact_source(ctx, "figures_and_tables_plan_path")
        ) or _render_figures_and_tables_plan(ctx)
        appendix = _render_structured_appendix(
            architecture_text=architecture_text,
            process_text=process_text,
            figures_text=figures_text,
        )
        diagram_appendix = _render_diagram_appendix(ctx)
        markdown_body = f"{markdown_body}\n\n{appendix}\n\n{diagram_appendix}"
        docx_markdown_body = f"{docx_markdown_body}\n\n{appendix}\n\n{diagram_appendix}"

        markdown_path = ctx.work_dir / "artifacts" / "disclosure.md"
        docx_path = ctx.work_dir / "artifacts" / "disclosure.docx"
        docx_markdown_path = ctx.work_dir / "artifacts" / "disclosure.docx.md"
        _atomic_write_text(markdown_path, markdown_body)
        # Stub docx payload: keep extension for downstream packaging compatibility.
        _atomic_write_text(docx_path, docx_markdown_body)
        _atomic_write_text(docx_markdown_path, docx_markdown_body)

        ctx.metadata["disclosure_draft_path"] = str(markdown_path)
        ctx.metadata["disclosure_docx_path"] = str(docx_path)
        ctx.metadata["disclosure_docx_markdown_path"] = str(docx_markdown_path)
        ctx.metadata["template_used"] = rendered.template_name

        return StageResult(
            produces=list(self.produces),
            outputs={
                "disclosure_draft_path": str(markdown_path),
                "disclosure_docx_path": str(docx_path),
                "disclosure_docx_markdown_path": str(docx_markdown_path),
                "template_used": rendered.template_name,
            },
        )


@dataclass
class DeliverablesExportStage:
    stage_id: str = "STAGE_15"
    requires: list[str] = field(
        default_factory=lambda: [
            "disclosure_draft_path",
            "disclosure_docx_path",
            "oa_response_playbook_draft_path",
        ]
    )
    produces: list[str] = field(
        default_factory=lambda: [
            "deliverables_disclosure_path",
            "deliverables_disclosure_docx_path",
            "deliverables_oa_response_playbook_path",
            "deliverables_disclosure_validation_report_path",
            "deliverables_system_architecture_path",
            "deliverables_process_stages_path",
            "deliverables_figures_and_tables_plan_path",
            "deliverables_architecture_ascii_path",
            "deliverables_process_ascii_path",
            "deliverables_architecture_mermaid_path",
            "deliverables_process_mermaid_path",
            "deliverables_architecture_image_path",
            "deliverables_process_image_path",
            "final_package_dir",
        ]
    )

    def run(self, ctx: StageContext) -> StageResult:
        disclosure_src = _safe_artifact_source(ctx, "disclosure_draft_path")
        disclosure_docx_src = _safe_artifact_source(ctx, "disclosure_docx_path")
        playbook_src = _safe_artifact_source(ctx, "oa_response_playbook_draft_path")

        disclosure_content = _read_text_if_exists(disclosure_src) or ""
        disclosure_docx_content = _read_text_if_exists(disclosure_docx_src) or disclosure_content
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
        architecture_content = _read_text_if_exists(
            _safe_artifact_source(ctx, "system_architecture_path")
        ) or _render_system_architecture(ctx)
        process_content = _read_text_if_exists(
            _safe_artifact_source(ctx, "process_stages_path")
        ) or _render_process_stages(ctx)
        figures_content = _read_text_if_exists(
            _safe_artifact_source(ctx, "figures_and_tables_plan_path")
        ) or _render_figures_and_tables_plan(ctx)
        arch_ascii_content = _read_text_if_exists(
            _safe_artifact_source(ctx, "architecture_ascii_path")
        ) or _render_architecture_ascii(ctx)
        flow_ascii_content = _read_text_if_exists(
            _safe_artifact_source(ctx, "process_ascii_path")
        ) or _render_process_ascii(ctx)
        arch_mermaid_content = _read_text_if_exists(
            _safe_artifact_source(ctx, "architecture_mermaid_path")
        ) or _render_architecture_mermaid(ctx)
        flow_mermaid_content = _read_text_if_exists(
            _safe_artifact_source(ctx, "process_mermaid_path")
        ) or _render_process_mermaid(ctx)

        out_dir = ctx.work_dir / "deliverables"
        final_package_dir = ctx.work_dir / "final_package"

        disclosure_out = out_dir / "disclosure.md"
        disclosure_docx_out = out_dir / "disclosure.docx"
        playbook_out = out_dir / "oa_response_playbook.md"
        validation_out = out_dir / "disclosure_validation_report.md"
        claims_out = out_dir / "claims_draft.md"
        spec_out = out_dir / "spec_draft.md"
        novelty_out = out_dir / "novelty_risk_report.md"
        architecture_out = out_dir / "system_architecture.md"
        process_out = out_dir / "process_stages.md"
        figures_out = out_dir / "figures_and_tables_plan.md"
        arch_ascii_out = out_dir / "architecture_ascii.txt"
        flow_ascii_out = out_dir / "process_flow_ascii.txt"
        arch_mermaid_out = out_dir / "architecture.mmd"
        flow_mermaid_out = out_dir / "process_flow.mmd"
        arch_image_out = out_dir / "architecture.png"
        flow_image_out = out_dir / "process_flow.png"

        _atomic_write_text(disclosure_out, disclosure_content)
        _atomic_write_text(disclosure_docx_out, disclosure_docx_content)
        _atomic_write_text(playbook_out, playbook_content)
        _atomic_write_text(validation_out, validation_content)
        _atomic_write_text(claims_out, claims_content)
        _atomic_write_text(spec_out, spec_content)
        _atomic_write_text(novelty_out, novelty_content)
        _atomic_write_text(architecture_out, architecture_content)
        _atomic_write_text(process_out, process_content)
        _atomic_write_text(figures_out, figures_content)
        _atomic_write_text(arch_ascii_out, arch_ascii_content)
        _atomic_write_text(flow_ascii_out, flow_ascii_content)
        _atomic_write_text(arch_mermaid_out, arch_mermaid_content)
        _atomic_write_text(flow_mermaid_out, flow_mermaid_content)

        src_arch_image = _safe_artifact_source(ctx, "architecture_image_path")
        src_flow_image = _safe_artifact_source(ctx, "process_image_path")
        has_arch_image = bool(src_arch_image and src_arch_image.exists())
        has_flow_image = bool(src_flow_image and src_flow_image.exists())
        if has_arch_image and src_arch_image is not None:
            arch_image_out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_arch_image, arch_image_out)
        if has_flow_image and src_flow_image is not None:
            flow_image_out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_flow_image, flow_image_out)

        _atomic_write_text(final_package_dir / "disclosure.md", disclosure_content)
        _atomic_write_text(final_package_dir / "disclosure.docx", disclosure_docx_content)
        _atomic_write_text(final_package_dir / "oa_response_playbook.md", playbook_content)
        _atomic_write_text(final_package_dir / "disclosure_validation_report.md", validation_content)
        _atomic_write_text(final_package_dir / "claims_draft.md", claims_content)
        _atomic_write_text(final_package_dir / "spec_draft.md", spec_content)
        _atomic_write_text(final_package_dir / "novelty_risk_report.md", novelty_content)
        _atomic_write_text(final_package_dir / "system_architecture.md", architecture_content)
        _atomic_write_text(final_package_dir / "process_stages.md", process_content)
        _atomic_write_text(final_package_dir / "figures_and_tables_plan.md", figures_content)
        _atomic_write_text(final_package_dir / "architecture_ascii.txt", arch_ascii_content)
        _atomic_write_text(final_package_dir / "process_flow_ascii.txt", flow_ascii_content)
        _atomic_write_text(final_package_dir / "architecture.mmd", arch_mermaid_content)
        _atomic_write_text(final_package_dir / "process_flow.mmd", flow_mermaid_content)
        if has_arch_image:
            shutil.copy2(arch_image_out, final_package_dir / "architecture.png")
        if has_flow_image:
            shutil.copy2(flow_image_out, final_package_dir / "process_flow.png")

        ctx.metadata["deliverables_disclosure_path"] = str(disclosure_out)
        ctx.metadata["deliverables_disclosure_docx_path"] = str(disclosure_docx_out)
        ctx.metadata["deliverables_oa_response_playbook_path"] = str(playbook_out)
        ctx.metadata["deliverables_disclosure_validation_report_path"] = str(validation_out)
        ctx.metadata["deliverables_system_architecture_path"] = str(architecture_out)
        ctx.metadata["deliverables_process_stages_path"] = str(process_out)
        ctx.metadata["deliverables_figures_and_tables_plan_path"] = str(figures_out)
        ctx.metadata["deliverables_architecture_ascii_path"] = str(arch_ascii_out)
        ctx.metadata["deliverables_process_ascii_path"] = str(flow_ascii_out)
        ctx.metadata["deliverables_architecture_mermaid_path"] = str(arch_mermaid_out)
        ctx.metadata["deliverables_process_mermaid_path"] = str(flow_mermaid_out)
        ctx.metadata["deliverables_architecture_image_path"] = str(arch_image_out) if has_arch_image else None
        ctx.metadata["deliverables_process_image_path"] = str(flow_image_out) if has_flow_image else None
        ctx.metadata["final_package_dir"] = str(final_package_dir)

        return StageResult(
            produces=list(self.produces),
            outputs={
                "deliverables_disclosure_path": str(disclosure_out),
                "deliverables_disclosure_docx_path": str(disclosure_docx_out),
                "deliverables_oa_response_playbook_path": str(playbook_out),
                "deliverables_disclosure_validation_report_path": str(validation_out),
                "deliverables_system_architecture_path": str(architecture_out),
                "deliverables_process_stages_path": str(process_out),
                "deliverables_figures_and_tables_plan_path": str(figures_out),
                "deliverables_architecture_ascii_path": str(arch_ascii_out),
                "deliverables_process_ascii_path": str(flow_ascii_out),
                "deliverables_architecture_mermaid_path": str(arch_mermaid_out),
                "deliverables_process_mermaid_path": str(flow_mermaid_out),
                "deliverables_architecture_image_path": str(arch_image_out) if has_arch_image else None,
                "deliverables_process_image_path": str(flow_image_out) if has_flow_image else None,
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
        _Stage06DisclosureOutlineStage(),
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
