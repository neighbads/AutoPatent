from __future__ import annotations

import json
from pathlib import Path

import pytest

from autopatent.pipeline import StageContext


def ctx_with_candidates(base_path: Path) -> StageContext:
    # Minimal candidate payload expected by Stage 04.
    return StageContext(
        work_dir=base_path,
        metadata={
            "direction_candidates": [
                {"id": "1", "title": "方向 1", "summary": "stub", "score": 0.2},
                {"id": "2", "title": "方向 2", "summary": "stub", "score": 0.8},
                {"id": "3", "title": "方向 3", "summary": "stub", "score": 0.4},
            ]
        },
    )


def test_human_gate_choose_persists_decision(tmp_path, monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "choose 2")
    from autopatent.pipeline.stages.stage_04_human_direction_gate import (
        HumanDirectionGateStage,
    )

    stage = HumanDirectionGateStage()
    result = stage.run(ctx_with_candidates(tmp_path))
    assert result.outputs["selected_direction_id"] == "2"
    decision_path = tmp_path / "direction_gate_decision.json"
    assert decision_path.exists()
    payload = json.loads(decision_path.read_text(encoding="utf-8"))
    assert payload["selected_direction_id"] == "2"


def test_human_gate_drop_then_choose_updates_candidates(tmp_path, monkeypatch):
    commands = iter(["drop 1", "choose 2"])
    monkeypatch.setattr("builtins.input", lambda _: next(commands))
    from autopatent.pipeline.stages.stage_04_human_direction_gate import (
        HumanDirectionGateStage,
    )

    ctx = ctx_with_candidates(tmp_path)
    stage = HumanDirectionGateStage()
    result = stage.run(ctx)
    assert result.outputs["selected_direction_id"] == "2"
    ids = {str(c["id"]) for c in ctx.metadata["direction_candidates"]}
    assert "1" not in ids


def test_human_gate_non_interactive_uses_preselected(tmp_path):
    from autopatent.pipeline.stages.stage_04_human_direction_gate import (
        HumanDirectionGateStage,
    )

    ctx = ctx_with_candidates(tmp_path)
    ctx.metadata["non_interactive"] = True
    ctx.metadata["selected_direction_id"] = "2"
    stage = HumanDirectionGateStage()
    result = stage.run(ctx)
    assert result.outputs["selected_direction_id"] == "2"
    assert (tmp_path / "direction_gate_decision.json").exists()


def test_human_gate_interactive_prints_candidates(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "choose 2")
    from autopatent.pipeline.stages.stage_04_human_direction_gate import (
        HumanDirectionGateStage,
    )

    stage = HumanDirectionGateStage()
    stage.run(ctx_with_candidates(tmp_path))
    out = capsys.readouterr().out
    assert "Candidate directions" in out
    assert "[1]" in out
    assert "[2]" in out


@pytest.mark.parametrize(
    "command",
    [
        "choose",
        "choose x",
        "drop",
        "merge 1",
        "expand 1 2",
        "unknown 1",
    ],
)
def test_human_gate_invalid_command_prompts_again(tmp_path, monkeypatch, command):
    # Stage should keep prompting until it gets a valid command.
    commands = iter([command, "choose 1"])
    monkeypatch.setattr("builtins.input", lambda _: next(commands))
    from autopatent.pipeline.stages.stage_04_human_direction_gate import (
        HumanDirectionGateStage,
    )

    stage = HumanDirectionGateStage()
    result = stage.run(ctx_with_candidates(tmp_path))
    assert result.outputs["selected_direction_id"] == "1"
