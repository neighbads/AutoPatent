from pathlib import Path

from autopatent.pipeline import PipelineEngine, StageContext, StageResult


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
