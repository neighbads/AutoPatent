from __future__ import annotations

from autopatent.pipeline import StageContext
from autopatent.pipeline.stages import stage_05_to_15_stubs as stage_stubs


def _find_stage(stage_id: str):
    for stage in stage_stubs.stage_05_to_15_stages():
        if stage.stage_id == stage_id:
            return stage
    raise AssertionError(f"stage not found: {stage_id}")


def test_stage10_uses_llm_when_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(
        stage_stubs,
        "_try_llm_text",
        lambda **kwargs: "1. 一种由 LLM 生成的权利要求。",
        raising=False,
    )

    claim_strategy = tmp_path / "artifacts" / "stage_09_claim_strategy.md"
    claim_strategy.parent.mkdir(parents=True, exist_ok=True)
    claim_strategy.write_text("# strategy\n", encoding="utf-8")

    ctx = StageContext(
        work_dir=tmp_path,
        metadata={
            "topic": "抗量子SSL和证书",
            "selected_direction_id": "2",
            "claim_strategy_path": str(claim_strategy),
            "llm": {
                "provider": "openai-compatible",
                "base_url": "http://127.0.0.1:9999/v1",
                "api_key_env": "OPENAI_API_KEY",
                "model": "gpt-5.4",
            },
        },
    )

    stage = _find_stage("STAGE_10")
    stage.run(ctx)

    content = (tmp_path / "artifacts" / "claims_draft.md").read_text(encoding="utf-8")
    assert "LLM 生成的权利要求" in content
