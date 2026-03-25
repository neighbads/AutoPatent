import json
from pathlib import Path

from typer.testing import CliRunner

from autopatent.cli import app


def _read_checkpoint_history(output_dir: Path) -> list[dict[str, str]]:
    history_file = output_dir / "state" / "checkpoint_history.json"
    return json.loads(history_file.read_text(encoding="utf-8"))


def _read_stage_manifest(output_dir: Path, stage_id: str) -> dict:
    manifest_path = output_dir / "stage_outputs" / stage_id / "manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def test_run_generates_deliverables_and_checkpoints(tmp_path):
    runner = CliRunner()
    output_dir = tmp_path / "run-out"

    result = runner.invoke(
        app,
        [
            "run",
            "--topic",
            "国密 TLCP / IPSec 混合抗量子方案",
            "--output",
            str(output_dir),
            "--auto-approve",
        ],
    )

    assert result.exit_code == 0
    assert "Stage outputs summary:" in result.output
    assert "STAGE_00 INPUT_INGEST(输入阶段):" in result.output
    assert "STAGE_01 DIRECTION_DISCOVERY(方向候选):" in result.output
    assert "STAGE_15 DELIVERABLES_EXPORT(交付打包):" in result.output
    assert (output_dir / "deliverables" / "disclosure.md").exists()
    assert (output_dir / "deliverables" / "disclosure.docx").exists()
    assert (output_dir / "deliverables" / "oa_response_playbook.md").exists()
    assert (output_dir / "deliverables" / "disclosure_validation_report.md").exists()
    assert (output_dir / "deliverables" / "system_architecture.md").exists()
    assert (output_dir / "deliverables" / "process_stages.md").exists()
    assert (output_dir / "deliverables" / "figures_and_tables_plan.md").exists()
    assert (output_dir / "deliverables" / "architecture_ascii.txt").exists()
    assert (output_dir / "deliverables" / "process_flow_ascii.txt").exists()
    assert (output_dir / "deliverables" / "architecture.mmd").exists()
    assert (output_dir / "deliverables" / "process_flow.mmd").exists()
    assert (output_dir / "final_package").exists()
    assert (output_dir / "final_package" / "disclosure.docx").exists()
    assert (output_dir / "final_package" / "system_architecture.md").exists()
    assert (output_dir / "final_package" / "process_stages.md").exists()
    assert (output_dir / "final_package" / "figures_and_tables_plan.md").exists()
    assert (output_dir / "final_package" / "architecture_ascii.txt").exists()
    assert (output_dir / "final_package" / "process_flow_ascii.txt").exists()
    assert (output_dir / "final_package" / "architecture.mmd").exists()
    assert (output_dir / "final_package" / "process_flow.mmd").exists()
    assert (output_dir / "artifacts" / "direction_analysis_report.md").exists()
    assert (output_dir / "artifacts" / "prior_art_evidence.jsonl").exists()
    assert (output_dir / "artifacts" / "direction_scores.json").exists()
    assert (output_dir / "artifacts" / "disclosure_outline.md").exists()
    assert (output_dir / "artifacts" / "disclosure_context.json").exists()
    assert (output_dir / "artifacts" / "disclosure.docx").exists()
    assert (output_dir / "artifacts" / "system_architecture.md").exists()
    assert (output_dir / "artifacts" / "process_stages.md").exists()
    assert (output_dir / "artifacts" / "figures_and_tables_plan.md").exists()
    assert (output_dir / "artifacts" / "architecture_ascii.txt").exists()
    assert (output_dir / "artifacts" / "process_flow_ascii.txt").exists()
    assert (output_dir / "artifacts" / "architecture.mmd").exists()
    assert (output_dir / "artifacts" / "process_flow.mmd").exists()

    history = _read_checkpoint_history(output_dir)
    assert history[0]["stage_id"] == "STAGE_00"
    assert history[0]["status"] == "done"
    assert history[-1]["stage_id"] == "STAGE_15"
    assert history[-1]["status"] == "done"
    assert len(history) == 16

    # New per-stage output snapshot
    for idx in range(16):
        stage_id = f"STAGE_{idx:02d}"
        manifest = _read_stage_manifest(output_dir, stage_id)
        assert manifest["stage_id"] == stage_id
        assert manifest["status"] == "done"
    stage04 = _read_stage_manifest(output_dir, "STAGE_04")
    assert "direction_gate_decision.json" in stage04["changed_files"]

    latest_metadata = output_dir / "state" / "metadata_latest.json"
    assert latest_metadata.exists()

    human_decisions = output_dir / "state" / "human_decisions.json"
    assert human_decisions.exists()
    payload = json.loads(human_decisions.read_text(encoding="utf-8"))
    assert payload["STAGE_04"]["selected_direction_id"] == "2"


def test_resume_continues_from_latest_done_stage(tmp_path):
    runner = CliRunner()
    output_dir = tmp_path / "resume-out"

    first = runner.invoke(
        app,
        ["run", "--topic", "后量子 IPsec", "--output", str(output_dir), "--auto-approve"],
    )
    assert first.exit_code == 0

    history = _read_checkpoint_history(output_dir)
    partial = history[:4]
    history_file = output_dir / "state" / "checkpoint_history.json"
    history_file.write_text(json.dumps(partial, ensure_ascii=False, indent=2), encoding="utf-8")

    resumed = runner.invoke(
        app,
        [
            "run",
            "--topic",
            "后量子 IPsec",
            "--output",
            str(output_dir),
            "--resume",
            "--auto-approve",
        ],
    )
    assert resumed.exit_code == 0

    resumed_history = _read_checkpoint_history(output_dir)
    assert resumed_history[-1]["stage_id"] == "STAGE_15"
    assert resumed_history[-1]["status"] == "done"
    assert len(resumed_history) == 16


def test_resume_recovers_human_decision_when_stage_metadata_missing(tmp_path):
    runner = CliRunner()
    output_dir = tmp_path / "resume-human-out"

    first = runner.invoke(
        app,
        ["run", "--topic", "后量子 IPsec", "--output", str(output_dir)],
        input="choose 2\n",
    )
    assert first.exit_code == 0

    history = _read_checkpoint_history(output_dir)
    # Keep only up to STAGE_04 done.
    history_file = output_dir / "state" / "checkpoint_history.json"
    history_file.write_text(json.dumps(history[:5], ensure_ascii=False, indent=2), encoding="utf-8")

    # Simulate partial state corruption: stage snapshot and latest snapshot missing.
    stage04_snapshot = output_dir / "state" / "metadata" / "STAGE_04.json"
    if stage04_snapshot.exists():
        stage04_snapshot.unlink()
    latest_snapshot = output_dir / "state" / "metadata_latest.json"
    if latest_snapshot.exists():
        latest_snapshot.unlink()

    resumed = runner.invoke(
        app,
        ["run", "--topic", "后量子 IPsec", "--output", str(output_dir), "--resume"],
    )
    assert resumed.exit_code == 0

    resumed_history = _read_checkpoint_history(output_dir)
    assert resumed_history[-1]["stage_id"] == "STAGE_15"
    assert resumed_history[-1]["status"] == "done"


def test_run_uses_configured_search_provider(tmp_path):
    runner = CliRunner()
    output_dir = tmp_path / "run-with-config"
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "search_provider": "seed-only",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "run",
            "--topic",
            "抗量子SSL和证书",
            "--output",
            str(output_dir),
            "--auto-approve",
            "--config",
            str(config_path),
        ],
    )
    assert result.exit_code == 0

    meta = json.loads((output_dir / "artifacts" / "search_meta.json").read_text(encoding="utf-8"))
    assert meta["provider"] == "seed-only"
