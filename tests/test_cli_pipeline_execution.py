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
        ["run", "--topic", "国密 TLCP / IPSec 混合抗量子方案", "--output", str(output_dir)],
    )

    assert result.exit_code == 0
    assert (output_dir / "deliverables" / "disclosure.md").exists()
    assert (output_dir / "deliverables" / "oa_response_playbook.md").exists()

    history = _read_checkpoint_history(output_dir)
    assert history[0]["stage_id"] == "STAGE_00"
    assert history[0]["status"] == "done"
    assert history[-1]["stage_id"] == "STAGE_15"
    assert history[-1]["status"] == "done"
    assert len(history) == 16

    latest_metadata = output_dir / "state" / "metadata_latest.json"
    assert latest_metadata.exists()


def test_resume_continues_from_latest_done_stage(tmp_path):
    runner = CliRunner()
    output_dir = tmp_path / "resume-out"

    first = runner.invoke(
        app,
        ["run", "--topic", "后量子 IPsec", "--output", str(output_dir)],
    )
    assert first.exit_code == 0

    history = _read_checkpoint_history(output_dir)
    partial = history[:4]
    history_file = output_dir / "state" / "checkpoint_history.json"
    history_file.write_text(json.dumps(partial, ensure_ascii=False, indent=2), encoding="utf-8")

    resumed = runner.invoke(
        app,
        ["run", "--topic", "后量子 IPsec", "--output", str(output_dir), "--resume"],
    )
    assert resumed.exit_code == 0

    resumed_history = _read_checkpoint_history(output_dir)
    assert resumed_history[-1]["stage_id"] == "STAGE_15"
    assert resumed_history[-1]["status"] == "done"
    assert len(resumed_history) == 16
