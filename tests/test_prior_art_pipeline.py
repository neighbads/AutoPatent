from __future__ import annotations

import json

from autopatent.pipeline import StageContext
from autopatent.pipeline.stages.stage_02_prior_art_scan import PriorArtScanStage


def _read_jsonl(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_prior_art_scan_generates_queries_evidence_and_meta(tmp_path):
    ctx = StageContext(
        work_dir=tmp_path,
        metadata={
            "topic": "国密 TLCP / IPSec 混合抗量子方案",
            "direction_candidates": [
                {"id": "1", "title": "握手协商流程优化", "summary": "s1"},
                {"id": "2", "title": "密钥管理接口设计", "summary": "s2"},
                {"id": "3", "title": "策略驱动数据面实现", "summary": "s3"},
            ],
        },
    )
    stage = PriorArtScanStage()
    stage.run(ctx)

    evidence_path = tmp_path / "artifacts" / "prior_art_evidence.jsonl"
    queries_path = tmp_path / "artifacts" / "prior_art_queries.json"
    meta_path = tmp_path / "artifacts" / "search_meta.json"

    assert evidence_path.exists()
    assert queries_path.exists()
    assert meta_path.exists()

    evidence = _read_jsonl(evidence_path)
    assert len(evidence) > 0
    # Deduped evidence should have unique normalized title keys.
    assert len({item["dedup_key"] for item in evidence}) == len(evidence)

    queries = json.loads(queries_path.read_text(encoding="utf-8"))
    assert isinstance(queries, list)
    assert len(queries) >= 5
    assert any("TLCP" in q or "IPSec" in q for q in queries)

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["raw_hits"] >= meta["deduped_hits"] >= 1
    assert meta["query_count"] == len(queries)
    assert meta["resource_count"] >= 10
    assert meta["provider"] == "offline"


def test_prior_art_scan_expands_queries_with_seed_artifacts(tmp_path):
    digest = tmp_path / "artifacts" / "input_doc_digest.md"
    digest.parent.mkdir(parents=True, exist_ok=True)
    digest.write_text("关键词: IKEv2 TLCP 组网迁移\n", encoding="utf-8")

    inventory = tmp_path / "artifacts" / "code_inventory.json"
    inventory.write_text(
        json.dumps(
            {
                "files": [
                    {"path": "swssl/tlcp_adapter.c", "ext": ".c"},
                    {"path": "swssl/ipsec_kdf.c", "ext": ".c"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    ctx = StageContext(
        work_dir=tmp_path,
        metadata={
            "topic": "国密 TLCP / IPSec 混合抗量子方案",
            "direction_candidates": [
                {"id": "1", "title": "握手协商流程优化", "summary": "s1"},
                {"id": "2", "title": "密钥管理接口设计", "summary": "s2"},
            ],
            "input_doc_digest_path": str(digest),
            "code_inventory_path": str(inventory),
        },
    )
    stage = PriorArtScanStage()
    stage.run(ctx)

    queries = json.loads((tmp_path / "artifacts" / "prior_art_queries.json").read_text(encoding="utf-8"))
    joined = " ".join(queries).lower()
    assert "ikev2" in joined
    assert "tlcp_adapter" in joined


def test_prior_art_scan_supports_seed_only_provider(tmp_path):
    ctx = StageContext(
        work_dir=tmp_path,
        metadata={
            "topic": "国密 TLCP / IPSec 混合抗量子方案",
            "search_provider": "seed-only",
            "direction_candidates": [
                {"id": "1", "title": "握手协商流程优化", "summary": "s1"},
                {"id": "2", "title": "密钥管理接口设计", "summary": "s2"},
            ],
        },
    )
    stage = PriorArtScanStage()
    stage.run(ctx)

    meta = json.loads((tmp_path / "artifacts" / "search_meta.json").read_text(encoding="utf-8"))
    assert meta["provider"] == "seed-only"
    assert meta["raw_hits"] == meta["query_count"]


def test_prior_art_scan_rejects_unknown_provider(tmp_path):
    ctx = StageContext(
        work_dir=tmp_path,
        metadata={
            "topic": "国密 TLCP / IPSec 混合抗量子方案",
            "search_provider": "unknown-provider",
            "direction_candidates": [
                {"id": "1", "title": "握手协商流程优化", "summary": "s1"},
            ],
        },
    )
    stage = PriorArtScanStage()
    try:
        stage.run(ctx)
    except ValueError as exc:
        assert "search provider" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError for unknown provider")
