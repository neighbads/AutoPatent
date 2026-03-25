import json
from pathlib import Path
from typing import Any, Optional, Sequence

import typer

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
    resume: bool = False,
    template: Optional[str] = None,
) -> None:
    """Run the CN MVP pipeline (STAGE_00 -> STAGE_15)."""
    if not topic and not input_doc:
        raise typer.BadParameter("需要至少一个输入", param_hint="--topic/--input-doc")

    if input_doc and not input_doc.exists():
        raise typer.BadParameter(f"输入文档不存在: {input_doc}", param_hint="--input-doc")
    if code_dir and not code_dir.exists():
        raise typer.BadParameter(f"代码目录不存在: {code_dir}", param_hint="--code-dir")

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
    )
    start_idx = 0
    if resume:
        start_idx, resumed_metadata = _resume_state(
            stages=stages,
            state_dir=state_dir,
            checkpoints=checkpoints,
        )
        if resumed_metadata is not None:
            metadata = resumed_metadata
        if start_idx >= len(stages):
            typer.echo("Checkpoint indicates all stages are already complete. Nothing to resume.")
            return
        typer.echo(f"Resuming from {stages[start_idx].stage_id}")

    ctx = StageContext(work_dir=output_dir, metadata=metadata)
    for stage in stages[start_idx:]:
        typer.echo(f"[{stage.stage_id}] running...")
        try:
            PipelineEngine([stage]).run(ctx)
        except Exception:
            checkpoints.save(stage_id=stage.stage_id, status="failed")
            _write_metadata_snapshot(state_dir=state_dir, stage_id=stage.stage_id, metadata=ctx.metadata)
            raise
        checkpoints.save(stage_id=stage.stage_id, status="done")
        _write_metadata_snapshot(state_dir=state_dir, stage_id=stage.stage_id, metadata=ctx.metadata)
        typer.echo(f"[{stage.stage_id}] done")

    typer.echo("Pipeline complete")


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
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "topic": topic,
        "input_doc": str(input_doc.expanduser().resolve()) if input_doc else None,
        "code_dir": str(code_dir.expanduser().resolve()) if code_dir else None,
        "template": template_name,
        # Default to unattended runs in CLI to avoid blocking prompt.
        "non_interactive": True,
        "selected_direction_id": _DEFAULT_SELECTED_DIRECTION_ID,
    }
    return _to_jsonable(payload)


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


def _read_metadata_snapshot(*, state_dir: Path, stage_id: str) -> dict[str, Any]:
    path = _snapshot_path(state_dir=state_dir, stage_id=stage_id)
    if not path.exists():
        raise ValueError(f"Missing metadata snapshot for resume: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed metadata snapshot at {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Metadata snapshot at {path} must be a JSON object")
    return payload


def _write_metadata_snapshot(*, state_dir: Path, stage_id: str, metadata: dict[str, Any]) -> None:
    serializable = _to_jsonable(metadata)
    state_dir.mkdir(parents=True, exist_ok=True)

    path = _snapshot_path(state_dir=state_dir, stage_id=stage_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(serializable, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")
    (state_dir / "metadata_latest.json").write_text(text, encoding="utf-8")


def _to_jsonable(payload: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(payload, ensure_ascii=False, default=str)
    normalized = json.loads(raw)
    if not isinstance(normalized, dict):
        raise ValueError("metadata payload must serialize to a JSON object")
    return normalized


if __name__ == "__main__":
    app()
