import importlib
import importlib.util
from pathlib import Path

import pytest

from autopatent.pipeline import PipelineEngine, StageContext, StageResult
from autopatent.pipeline.stages import (
    DirectionDiscoveryStage,
    DirectionScoringStage,
    HumanDirectionGateStage,
    InputIngestStage,
    PriorArtScanStage,
)


def stub(stage_id_value: str, order: list[str]):
    class StubStage:
        stage_id = stage_id_value
        requires: list[str] = []
        produces: list[str] = []

        def run(self, ctx: StageContext) -> StageResult:
            order.append(self.stage_id)
            return StageResult(produces=[])

    return StubStage()


def ctx(base_path: Path) -> StageContext:
    return StageContext(work_dir=base_path)


def test_engine_runs_stages_in_order(tmp_path):
    order: list[str] = []
    engine = PipelineEngine(stages=[stub("A", order), stub("B", order)])
    engine.run(context=ctx(tmp_path))
    assert order == ["A", "B"]


def run_pipeline(base_path: Path) -> None:
    """Run the CN MVP pipeline into a temp workdir.

    Stage 05-15 are imported lazily so this smoke test can be written before
    the implementation exists (TDD: we want a failing assertion, not ImportError).
    """

    stages = [
        InputIngestStage(),
        DirectionDiscoveryStage(),
        PriorArtScanStage(),
        DirectionScoringStage(),
        HumanDirectionGateStage(),
    ]

    spec = importlib.util.find_spec("autopatent.pipeline.stages.stage_05_to_15_stubs")
    if spec is not None:
        mod = importlib.import_module("autopatent.pipeline.stages.stage_05_to_15_stubs")
        stages.extend(mod.stage_05_to_15_stages())

    engine = PipelineEngine(stages=stages)
    engine.run(
        context=StageContext(
            work_dir=base_path,
            metadata={
                "topic": "CN MVP 测试主题",
                "non_interactive": True,
                # HumanDirectionGateStage requires a pre-selected id in non-interactive mode.
                "selected_direction_id": "2",
            },
        )
    )


def test_mvp_outputs_key_artifacts(tmp_path):
    run_pipeline(tmp_path)
    assert (tmp_path / "deliverables/disclosure.md").exists()
    assert (tmp_path / "deliverables/oa_response_playbook.md").exists()


def test_engine_treats_empty_required_value_as_missing(tmp_path):
    class NeedsTopicStage:
        stage_id = "NEEDS_TOPIC"
        requires = ["topic"]
        produces: list[str] = []

        def run(self, ctx: StageContext) -> StageResult:
            return StageResult(produces=[])

    engine = PipelineEngine(stages=[NeedsTopicStage()])
    with pytest.raises(ValueError):
        engine.run(context=StageContext(work_dir=tmp_path, metadata={"topic": ""}))


def test_deliverables_export_rejects_outside_artifacts_source(tmp_path):
    from autopatent.pipeline.stages.stage_05_to_15_stubs import DeliverablesExportStage

    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")

    stage = DeliverablesExportStage()
    ctx = StageContext(
        work_dir=tmp_path,
        metadata={
            "disclosure_draft_path": str(outside),
            "oa_response_playbook_draft_path": str(outside),
        },
    )
    with pytest.raises(ValueError):
        stage.run(ctx)
