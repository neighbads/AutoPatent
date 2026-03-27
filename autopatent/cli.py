import json
import shutil
from pathlib import Path
from typing import Any, Optional, Sequence

import typer

from autopatent.config import load_config
from autopatent.pipeline import PipelineEngine, Stage, StageContext
from autopatent.pipeline.checkpoint import CheckpointStore
from autopatent.pipeline.stages import (
    DirectionDiscoveryStage,
    DirectionScoringStage,
    HumanDirectionGateStage,
    InputIngestStage,
    PriorArtScanStage,
)
from autopatent.pipeline.stages.stage_05_to_15_stubs import stage_05_to_15_stages
from autopatent.templates.renderer import DEFAULT_TEMPLATE_NAME

app = typer.Typer()
_DEFAULT_SELECTED_DIRECTION_ID = "2"
_STAGE_TRACKED_ROOTS = (
    "artifacts",
    "deliverables",
    "final_package",
    "direction_gate_decision.json",
)
_STAGE_DISPLAY_NAMES = {
    "STAGE_00": "INPUT_INGEST(输入阶段)",
    "STAGE_01": "DIRECTION_DISCOVERY(方向候选)",
    "STAGE_02": "PRIOR_ART_SCAN(现有技术检索)",
    "STAGE_03": "DIRECTION_SCORING(方向评分)",
    "STAGE_04": "HUMAN_DIRECTION_GATE(人工选题)",
    "STAGE_05": "TITLE_FINALIZATION(题目确认)",
    "STAGE_06": "DISCLOSURE_OUTLINE(交底书大纲)",
    "STAGE_07": "DISCLOSURE_DRAFT(交底书撰写)",
    "STAGE_08": "DISCLOSURE_VALIDATE(交底书校验)",
    "STAGE_09": "CLAIM_STRATEGY(权利要求策略)",
    "STAGE_10": "CLAIMS_DRAFT(权利要求撰写)",
    "STAGE_11": "SPEC_DRAFT(说明书撰写)",
    "STAGE_12": "LEGAL_VALIDATE(法律与格式校验)",
    "STAGE_13": "NOVELTY_RISK(新颖性/创造性风险)",
    "STAGE_14": "OA_PLAYBOOK(审查意见答复剧本)",
    "STAGE_15": "DELIVERABLES_EXPORT(交付打包)",
}
_STAGE_OPTIONAL_ARTIFACT_HINTS = {
    "STAGE_00": [
        "artifacts/input_doc_digest.md (optional: when --input-doc is provided)",
        "artifacts/code_inventory.json (optional: when --code-dir is provided)",
    ],
}


@app.callback()
def main() -> None:
    """Root CLI stub."""
    pass


@app.command()
def run(
    topic: Optional[str] = None,
    input_doc: Optional[Path] = None,
    output: Optional[Path] = None,
    code_dir: Optional[Path] = None,
    config: Optional[Path] = None,
    resume: bool = False,
    auto_approve: bool = typer.Option(False, "--auto-approve"),
    template: Optional[str] = None,
) -> None:
    """Run the CN MVP pipeline (STAGE_00 -> STAGE_15)."""
    if not topic and not input_doc:
        raise typer.BadParameter("需要至少一个输入", param_hint="--topic/--input-doc")

    if input_doc and not input_doc.exists():
        raise typer.BadParameter(f"输入文档不存在: {input_doc}", param_hint="--input-doc")
    if code_dir and not code_dir.exists():
        raise typer.BadParameter(f"代码目录不存在: {code_dir}", param_hint="--code-dir")
    if config and not config.exists():
        raise typer.BadParameter(f"配置文件不存在: {config}", param_hint="--config")

    app_cfg = load_config(config_path=config)

    selected_template = template or DEFAULT_TEMPLATE_NAME
    output_dir = (output or (Path.cwd() / "artifacts" / "autopatent-run")).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    stages = _build_stages()
    state_dir = output_dir / "state"
    checkpoints = CheckpointStore(state_dir)

    metadata = _initial_metadata(
        topic=topic,
        input_doc=input_doc,
        code_dir=code_dir,
        template_name=selected_template,
        search_provider=app_cfg.search_provider,
        search_runtime=app_cfg.search.to_runtime_mapping(),
        llm_runtime=app_cfg.llm.to_runtime_mapping() if app_cfg.llm else None,
        auto_approve=auto_approve,
    )
    start_idx = 0
    if resume:
        start_idx, resumed_metadata = _resume_state(
            stages=stages,
            state_dir=state_dir,
            checkpoints=checkpoints,
        )
        if resumed_metadata is not None:
            metadata.update(resumed_metadata)
        _restore_human_decisions(metadata=metadata, state_dir=state_dir)
        _apply_run_mode(metadata, auto_approve=auto_approve)
        if start_idx >= len(stages):
            typer.echo("Checkpoint indicates all stages are already complete. Nothing to resume.")
            return
        typer.echo(f"Resuming from {stages[start_idx].stage_id}")

    ctx = StageContext(work_dir=output_dir, metadata=metadata)
    for stage in stages[start_idx:]:
        before_snapshot = _collect_stage_tracked_file_signatures(output_dir)
        typer.echo(f"[{stage.stage_id}] running...")
        try:
            PipelineEngine([stage]).run(ctx)
        except Exception:
            checkpoints.save(stage_id=stage.stage_id, status="failed")
            _write_stage_output_snapshot(
                output_dir=output_dir,
                stage_id=stage.stage_id,
                status="failed",
                before_snapshot=before_snapshot,
                metadata=ctx.metadata,
                produced_keys=getattr(stage, "produces", []),
            )
            _write_metadata_snapshot(state_dir=state_dir, stage_id=stage.stage_id, metadata=ctx.metadata)
            _write_human_decisions(state_dir=state_dir, stage_id=stage.stage_id, metadata=ctx.metadata)
            raise
        checkpoints.save(stage_id=stage.stage_id, status="done")
        _write_stage_output_snapshot(
            output_dir=output_dir,
            stage_id=stage.stage_id,
            status="done",
            before_snapshot=before_snapshot,
            metadata=ctx.metadata,
            produced_keys=getattr(stage, "produces", []),
        )
        _write_metadata_snapshot(state_dir=state_dir, stage_id=stage.stage_id, metadata=ctx.metadata)
        _write_human_decisions(state_dir=state_dir, stage_id=stage.stage_id, metadata=ctx.metadata)
        typer.echo(f"[{stage.stage_id}] done")

    typer.echo("Pipeline complete")
    _print_stage_outputs_summary(output_dir=output_dir, stages=stages)


def _build_stages() -> list[Stage]:
    return [
        InputIngestStage(),
        DirectionDiscoveryStage(),
        PriorArtScanStage(),
        DirectionScoringStage(),
        HumanDirectionGateStage(),
        *stage_05_to_15_stages(),
    ]


def _initial_metadata(
    *,
    topic: Optional[str],
    input_doc: Optional[Path],
    code_dir: Optional[Path],
    template_name: str,
    search_provider: str,
    search_runtime: dict[str, Any],
    llm_runtime: Optional[dict[str, Any]],
    auto_approve: bool,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "topic": topic,
        "input_doc": str(input_doc.expanduser().resolve()) if input_doc else None,
        "code_dir": str(code_dir.expanduser().resolve()) if code_dir else None,
        "template": template_name,
        "search_provider": search_provider,
        "search": search_runtime,
        "llm": llm_runtime,
    }
    _apply_run_mode(payload, auto_approve=auto_approve)
    return _to_jsonable(payload)


def _apply_run_mode(metadata: dict[str, Any], *, auto_approve: bool) -> None:
    if auto_approve:
        metadata["non_interactive"] = True
        selected = str(metadata.get("selected_direction_id") or "").strip()
        if not selected:
            metadata["selected_direction_id"] = _DEFAULT_SELECTED_DIRECTION_ID
        return
    metadata["non_interactive"] = False


def _resume_state(
    *,
    stages: Sequence[Stage],
    state_dir: Path,
    checkpoints: CheckpointStore,
) -> tuple[int, Optional[dict[str, Any]]]:
    latest = checkpoints.latest()
    if latest is None:
        return 0, None
    idx = _stage_index(stages, latest.stage_id)
    if idx is None:
        raise ValueError(f"Unknown checkpoint stage_id: {latest.stage_id}")
    metadata = _read_metadata_snapshot(state_dir=state_dir, stage_id=latest.stage_id)
    if metadata is None:
        metadata = _read_metadata_latest(state_dir=state_dir)
    if latest.status == "done":
        return idx + 1, metadata
    return idx, metadata


def _stage_index(stages: Sequence[Stage], stage_id: str) -> Optional[int]:
    for idx, stage in enumerate(stages):
        if stage.stage_id == stage_id:
            return idx
    return None


def _snapshot_path(*, state_dir: Path, stage_id: str) -> Path:
    return state_dir / "metadata" / f"{stage_id}.json"


def _read_metadata_snapshot(*, state_dir: Path, stage_id: str) -> Optional[dict[str, Any]]:
    path = _snapshot_path(state_dir=state_dir, stage_id=stage_id)
    if not path.exists():
        return None
    return _read_json_object(path, label="metadata snapshot")


def _read_metadata_latest(*, state_dir: Path) -> Optional[dict[str, Any]]:
    path = state_dir / "metadata_latest.json"
    if not path.exists():
        return None
    return _read_json_object(path, label="metadata latest snapshot")


def _read_json_object(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed {label} at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} at {path} must be a JSON object")
    return payload


def _write_metadata_snapshot(*, state_dir: Path, stage_id: str, metadata: dict[str, Any]) -> None:
    serializable = _to_jsonable(metadata)
    state_dir.mkdir(parents=True, exist_ok=True)

    path = _snapshot_path(state_dir=state_dir, stage_id=stage_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(serializable, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")
    (state_dir / "metadata_latest.json").write_text(text, encoding="utf-8")


def _write_human_decisions(*, state_dir: Path, stage_id: str, metadata: dict[str, Any]) -> None:
    if stage_id != "STAGE_04":
        return
    selected = metadata.get("selected_direction_id")
    if selected is None:
        return

    record = {
        "selected_direction_id": str(selected),
        "decision_path": metadata.get("direction_gate_decision_path"),
    }
    path = state_dir / "human_decisions.json"
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Malformed human decisions file at {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"human_decisions.json must contain a JSON object: {path}")
    else:
        payload = {}
    payload["STAGE_04"] = record
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _restore_human_decisions(*, metadata: dict[str, Any], state_dir: Path) -> None:
    path = state_dir / "human_decisions.json"
    if not path.exists():
        return
    payload = _read_json_object(path, label="human decisions")
    stage04 = payload.get("STAGE_04")
    if not isinstance(stage04, dict):
        return
    selected = stage04.get("selected_direction_id")
    if selected is not None and not str(metadata.get("selected_direction_id", "")).strip():
        metadata["selected_direction_id"] = str(selected)
    decision_path = stage04.get("decision_path")
    if decision_path and not metadata.get("direction_gate_decision_path"):
        metadata["direction_gate_decision_path"] = decision_path


def _to_jsonable(payload: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=False, default=str)
    normalized = json.loads(raw)
    if not isinstance(normalized, dict):
        raise ValueError("metadata payload must serialize to a JSON object")
    return normalized


def _collect_stage_tracked_file_signatures(output_dir: Path) -> dict[str, tuple[int, int]]:
    signatures: dict[str, tuple[int, int]] = {}
    for item in _STAGE_TRACKED_ROOTS:
        root = output_dir / item
        if root.is_file():
            rel = str(root.relative_to(output_dir))
            stat = root.stat()
            signatures[rel] = (int(stat.st_mtime_ns), int(stat.st_size))
            continue
        if not root.exists() or not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            rel = str(path.relative_to(output_dir))
            stat = path.stat()
            signatures[rel] = (int(stat.st_mtime_ns), int(stat.st_size))
    return signatures


def _write_stage_output_snapshot(
    *,
    output_dir: Path,
    stage_id: str,
    status: str,
    before_snapshot: dict[str, tuple[int, int]],
    metadata: dict[str, Any],
    produced_keys: Sequence[str],
) -> None:
    after_snapshot = _collect_stage_tracked_file_signatures(output_dir)
    changed_files = sorted(
        rel for rel, signature in after_snapshot.items() if before_snapshot.get(rel) != signature
    )

    stage_root = output_dir / "stage_outputs" / stage_id
    files_root = stage_root / "files"
    files_root.mkdir(parents=True, exist_ok=True)
    for rel in changed_files:
        src = output_dir / rel
        if not src.exists() or not src.is_file():
            continue
        dst = files_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    outputs: dict[str, Any] = {}
    for key in produced_keys:
        outputs[str(key)] = metadata.get(key)

    manifest = {
        "stage_id": stage_id,
        "status": status,
        "changed_files": changed_files,
        "changed_file_count": len(changed_files),
        "outputs": outputs,
    }
    (stage_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _print_stage_outputs_summary(*, output_dir: Path, stages: Sequence[Stage]) -> None:
    typer.echo("")
    typer.echo("Stage outputs summary:")
    for stage in stages:
        stage_id = stage.stage_id
        display = _STAGE_DISPLAY_NAMES.get(stage_id, stage_id)
        typer.echo(f"{stage_id} {display}:")
        items = _stage_output_items(output_dir=output_dir, stage_id=stage_id)
        if not items:
            typer.echo("  (no file artifacts)")
            hints = _STAGE_OPTIONAL_ARTIFACT_HINTS.get(stage_id, [])
            for hint in hints:
                typer.echo(f"  {hint}")
            continue
        for item in items:
            typer.echo(f"  {item}")


def _stage_output_items(*, output_dir: Path, stage_id: str) -> list[str]:
    manifest_path = output_dir / "stage_outputs" / stage_id / "manifest.json"
    if not manifest_path.exists():
        return []
    payload = _read_json_object(manifest_path, label=f"stage manifest {stage_id}")

    changed: list[str] = []
    raw_changed = payload.get("changed_files")
    if isinstance(raw_changed, list):
        for item in raw_changed:
            text = str(item).strip()
            if text:
                changed.append(text)

    produced: list[str] = []
    raw_outputs = payload.get("outputs")
    if isinstance(raw_outputs, dict):
        for value in raw_outputs.values():
            if not isinstance(value, str):
                continue
            path_text = value.strip()
            if not path_text:
                continue
            rel = _to_output_relative_path(output_dir=output_dir, raw_path=path_text)
            if rel is None:
                continue
            produced.append(rel)

    merged: list[str] = []
    seen = set()
    for item in changed + produced:
        if item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def _to_output_relative_path(*, output_dir: Path, raw_path: str) -> Optional[str]:
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        candidate = (output_dir / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if not candidate.exists() or not candidate.is_file():
        return None
    try:
        return str(candidate.relative_to(output_dir))
    except ValueError:
        return str(candidate)


if __name__ == "__main__":
    app()
