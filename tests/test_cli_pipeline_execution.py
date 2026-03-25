import json
from pathlib import Path

from typer.testing import CliRunner

from autopatent.cli import app


def _read_checkpoint_history(output_dir: Path) -> list[dict[str, str]]:
    history_file = output_dir / "state" / "checkpoint_history.json"
    return json.loads(history_file.read_text(encoding="utf-8"))


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
    assert (output_dir / "deliverables" / "disclosure.md").exists()
    assert (output_dir / "deliverables" / "disclosure.docx").exists()
    assert (output_dir / "deliverables" / "oa_response_playbook.md").exists()
    assert (output_dir / "deliverables" / "disclosure_validation_report.md").exists()
    assert (output_dir / "final_package").exists()
    assert (output_dir / "final_package" / "disclosure.docx").exists()
    assert (output_dir / "artifacts" / "direction_analysis_report.md").exists()
    assert (output_dir / "artifacts" / "prior_art_evidence.jsonl").exists()
    assert (output_dir / "artifacts" / "direction_scores.json").exists()
    assert (output_dir / "artifacts" / "disclosure_outline.md").exists()
    assert (output_dir / "artifacts" / "disclosure_context.json").exists()
    assert (output_dir / "artifacts" / "disclosure.docx").exists()

    history = _read_checkpoint_history(output_dir)
    assert history[0]["stage_id"] == "STAGE_00"
    assert history[0]["status"] == "done"
    assert history[-1]["stage_id"] == "STAGE_15"
    assert history[-1]["status"] == "done"
    assert len(history) == 16

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
