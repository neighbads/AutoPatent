from __future__ import annotations

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


@pytest.mark.parametrize(
    "command",
    [
        "choose",
        "choose x",
        "drop",
        "merge 1",
        "expand",
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

