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
    assert (tmp_path / "deliverables/system_architecture.md").exists()
    assert (tmp_path / "deliverables/process_stages.md").exists()
    assert (tmp_path / "deliverables/figures_and_tables_plan.md").exists()
    assert (tmp_path / "deliverables/architecture_ascii.txt").exists()
    assert (tmp_path / "deliverables/process_flow_ascii.txt").exists()
    assert (tmp_path / "deliverables/architecture.mmd").exists()
    assert (tmp_path / "deliverables/process_flow.mmd").exists()

    disclosure = (tmp_path / "artifacts/disclosure.md").read_text(encoding="utf-8")
    spec = (tmp_path / "artifacts/spec_draft.md").read_text(encoding="utf-8")
    assert "系统架构描述（补充）" in disclosure
    assert "关键流程与阶段说明（补充）" in disclosure
    assert "附图与图表说明（补充）" in disclosure
    assert "图示与流程图（生成产物）" in disclosure
    assert "系统架构描述（补充）" in spec
    assert "关键流程与阶段说明（补充）" in spec
    assert "图示与流程图（生成产物）" in spec


def test_stage_05_to_14_outputs_are_structured_not_stub(tmp_path):
    run_pipeline(tmp_path)

    stage05 = (tmp_path / "artifacts/stage_05_title_finalization.md").read_text(encoding="utf-8")
    stage08 = (tmp_path / "artifacts/disclosure_validation_report.md").read_text(encoding="utf-8")
    stage09 = (tmp_path / "artifacts/stage_09_claim_strategy.md").read_text(encoding="utf-8")
    stage12 = (tmp_path / "artifacts/stage_12_legal_validate.md").read_text(encoding="utf-8")
    stage13 = (tmp_path / "artifacts/novelty_risk_report.md").read_text(encoding="utf-8")
    stage14 = (tmp_path / "artifacts/stage_14_oa_response_playbook_draft.md").read_text(encoding="utf-8")
    deliverable_playbook = (tmp_path / "deliverables/oa_response_playbook.md").read_text(
        encoding="utf-8"
    )

    assert "MVP stub" not in stage05
    assert "MVP stub" not in stage08
    assert "MVP stub" not in stage09
    assert "MVP stub" not in stage12
    assert "MVP stub" not in stage13
    assert "MVP stub" not in stage14
    assert "stub" not in deliverable_playbook.lower()

    assert "推荐题目" in stage05
    assert "校验结论" in stage08
    assert "独立权利要求主轴" in stage09
    assert "法律与格式校验报告" in stage12
    assert "风险分级" in stage13
    assert "审查意见类型" in stage14


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


def test_mvp_outputs_with_relative_work_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    relative_work_dir = Path("relative-run")
    run_pipeline(relative_work_dir)
    assert (relative_work_dir / "deliverables/disclosure.md").exists()
    assert (relative_work_dir / "deliverables/oa_response_playbook.md").exists()
