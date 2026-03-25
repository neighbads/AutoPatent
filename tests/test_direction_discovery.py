from __future__ import annotations

from autopatent.pipeline import StageContext
from autopatent.pipeline.stages.stage_01_direction_discovery import DirectionDiscoveryStage


def test_direction_discovery_generates_about_five_candidates(tmp_path):
    ctx = StageContext(work_dir=tmp_path, metadata={"topic": "混合抗量子协议"})
    stage = DirectionDiscoveryStage()
    result = stage.run(ctx)

    candidates = result.outputs["direction_candidates"]
    assert isinstance(candidates, list)
    assert 4 <= len(candidates) <= 6
    assert any(str(c.get("id")) == "2" for c in candidates)
    assert (tmp_path / "artifacts" / "direction_analysis_report.md").exists()


def test_direction_discovery_candidate_count_is_dynamic(tmp_path):
    short_ctx = StageContext(work_dir=tmp_path / "short", metadata={"topic": "短题"})
    long_ctx = StageContext(
        work_dir=tmp_path / "long",
        metadata={"topic": "国密 TLCP / IPSec 混合抗量子方案 的设计实现与评估"},
    )
    stage = DirectionDiscoveryStage()

    short_out = stage.run(short_ctx).outputs["direction_candidates"]
    long_out = stage.run(long_ctx).outputs["direction_candidates"]

    assert len(short_out) != len(long_out)
