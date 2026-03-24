from __future__ import annotations

from autopatent.pipeline import StageContext
from autopatent.pipeline.stages.stage_02_prior_art_scan import PriorArtScanStage


def test_prior_art_scan_emits_expected_resource_stubs(tmp_path):
    ctx = StageContext(
        work_dir=tmp_path,
        metadata={
            "direction_candidates": [
                {"id": "1", "title": "方向 1", "summary": "stub"},
            ]
        },
    )
    stage = PriorArtScanStage()
    result = stage.run(ctx)

    assert "prior_art_resources" in result.produces
    resources = ctx.metadata["prior_art_resources"]
    assert isinstance(resources, list)
    assert len(resources) >= 3

    sources = {r["source"] for r in resources}
    assert {"CNIPA", "WIPO_PATENTSCOPE", "GOOGLE_PATENTS"}.issubset(sources)

    for r in resources:
        assert isinstance(r.get("endpoint"), str)
        assert r["endpoint"].startswith("https://")

