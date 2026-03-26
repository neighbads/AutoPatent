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


def test_stage07_sanitizes_llm_scaffold_text(tmp_path, monkeypatch):
    monkeypatch.setattr(
        stage_stubs,
        "_try_llm_text",
        lambda **kwargs: (
            "以下为关于“抗量子SSL和证书”的扩展内容：\n\n"
            "这是正文内容。\n\n"
            "如需，我还可以继续补充。"
        ),
        raising=False,
    )

    context_path = tmp_path / "artifacts" / "disclosure_context.json"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(
        (
            '{"title":"抗量子SSL和证书","technical_field":"field",'
            '"background":"bg","summary":"sum","embodiments":"emb"}'
        ),
        encoding="utf-8",
    )

    # Stage 07 also reads these artifacts for structured appendix.
    (tmp_path / "artifacts" / "system_architecture.md").write_text("系统架构描述", encoding="utf-8")
    (tmp_path / "artifacts" / "process_stages.md").write_text("流程阶段描述", encoding="utf-8")
    (tmp_path / "artifacts" / "figures_and_tables_plan.md").write_text("图表描述", encoding="utf-8")
    (tmp_path / "artifacts" / "architecture_ascii.txt").write_text("ASCII-ARCH", encoding="utf-8")
    (tmp_path / "artifacts" / "process_flow_ascii.txt").write_text("ASCII-FLOW", encoding="utf-8")
    (tmp_path / "artifacts" / "architecture.mmd").write_text("flowchart TD\nA-->B", encoding="utf-8")
    (tmp_path / "artifacts" / "process_flow.mmd").write_text("flowchart TD\nC-->D", encoding="utf-8")

    ctx = StageContext(
        work_dir=tmp_path,
        metadata={
            "topic": "抗量子SSL和证书",
            "selected_direction_id": "2",
            "disclosure_context_path": str(context_path),
            "system_architecture_path": str(tmp_path / "artifacts" / "system_architecture.md"),
            "process_stages_path": str(tmp_path / "artifacts" / "process_stages.md"),
            "figures_and_tables_plan_path": str(tmp_path / "artifacts" / "figures_and_tables_plan.md"),
            "architecture_ascii_path": str(tmp_path / "artifacts" / "architecture_ascii.txt"),
            "process_ascii_path": str(tmp_path / "artifacts" / "process_flow_ascii.txt"),
            "architecture_mermaid_path": str(tmp_path / "artifacts" / "architecture.mmd"),
            "process_mermaid_path": str(tmp_path / "artifacts" / "process_flow.mmd"),
            "llm": {
                "provider": "openai-compatible",
                "base_url": "http://127.0.0.1:9999/v1",
                "api_key_env": "OPENAI_API_KEY",
                "model": "gpt-5.4",
            },
        },
    )
    _find_stage("STAGE_07").run(ctx)
    content = (tmp_path / "artifacts" / "disclosure.md").read_text(encoding="utf-8")
    assert "## LLM 扩展草案" not in content
    assert "以下为关于" not in content
    assert "如需，我还可以继续补充" not in content
    assert "技术扩展内容" in content


def test_stage07_backfills_legacy_sansec_text_fields_from_lists(tmp_path):
    context_path = tmp_path / "artifacts" / "disclosure_context.json"
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(
        (
            '{'
            '"title":"抗量子SSL和证书",'
            '"technical_field":"field",'
            '"background":"bg",'
            '"summary":"sum",'
            '"embodiments":"emb",'
            '"embodiments_detail":"detail",'
            '"invention_title":"发明标题",'
            '"technical_field_cn":"技术领域",'
            '"background_art":"背景技术",'
            '"core_solution":"技术方案",'
            '"technical_effects":"有益效果",'
            '"evidence_refs":["e1","e2"],'
            '"claim_seed_points":["c1","c2"],'
            '"code_evidence":["src/a.c"]'
            '}'
        ),
        encoding="utf-8",
    )

    ctx = StageContext(
        work_dir=tmp_path,
        metadata={
            "topic": "抗量子SSL和证书",
            "selected_direction_id": "2",
            "template": "sansec_disclosure_v1",
            "disclosure_context_path": str(context_path),
        },
    )

    _find_stage("STAGE_07").run(ctx)
    content = (tmp_path / "artifacts" / "disclosure.md").read_text(encoding="utf-8")
    assert "附录A 检索报告要点" in content
    assert "- e1" in content
    assert "- c1" in content
    assert "- src/a.c" in content


def test_stage11_sanitizes_leading_llm_preamble(tmp_path, monkeypatch):
    monkeypatch.setattr(
        stage_stubs,
        "_try_llm_text",
        lambda **kwargs: "以下为关于说明书草案\n---\n# 说明书草案\n## 背景技术\n正文\n如需，我还可以继续补充。",
        raising=False,
    )

    claims_path = tmp_path / "artifacts" / "claims_draft.md"
    claims_path.parent.mkdir(parents=True, exist_ok=True)
    claims_path.write_text("claims", encoding="utf-8")

    (tmp_path / "artifacts" / "system_architecture.md").write_text("系统架构描述", encoding="utf-8")
    (tmp_path / "artifacts" / "process_stages.md").write_text("流程阶段描述", encoding="utf-8")
    (tmp_path / "artifacts" / "figures_and_tables_plan.md").write_text("图表描述", encoding="utf-8")
    (tmp_path / "artifacts" / "architecture_ascii.txt").write_text("ASCII-ARCH", encoding="utf-8")
    (tmp_path / "artifacts" / "process_flow_ascii.txt").write_text("ASCII-FLOW", encoding="utf-8")
    (tmp_path / "artifacts" / "architecture.mmd").write_text("flowchart TD\nA-->B", encoding="utf-8")
    (tmp_path / "artifacts" / "process_flow.mmd").write_text("flowchart TD\nC-->D", encoding="utf-8")

    ctx = StageContext(
        work_dir=tmp_path,
        metadata={
            "topic": "抗量子SSL和证书",
            "selected_direction_id": "2",
            "claims_draft_path": str(claims_path),
            "system_architecture_path": str(tmp_path / "artifacts" / "system_architecture.md"),
            "process_stages_path": str(tmp_path / "artifacts" / "process_stages.md"),
            "figures_and_tables_plan_path": str(tmp_path / "artifacts" / "figures_and_tables_plan.md"),
            "architecture_ascii_path": str(tmp_path / "artifacts" / "architecture_ascii.txt"),
            "process_ascii_path": str(tmp_path / "artifacts" / "process_flow_ascii.txt"),
            "architecture_mermaid_path": str(tmp_path / "artifacts" / "architecture.mmd"),
            "process_mermaid_path": str(tmp_path / "artifacts" / "process_flow.mmd"),
            "llm": {
                "provider": "openai-compatible",
                "base_url": "http://127.0.0.1:9999/v1",
                "api_key_env": "OPENAI_API_KEY",
                "model": "gpt-5.4",
            },
        },
    )
    _find_stage("STAGE_11").run(ctx)
    content = (tmp_path / "artifacts" / "spec_draft.md").read_text(encoding="utf-8")
    assert "以下为关于" not in content
    assert "如需，我还可以继续补充" not in content
    assert "图示与流程图（生成产物）" in content
