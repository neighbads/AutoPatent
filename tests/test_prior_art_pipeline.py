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


def test_prior_art_scan_supports_online_provider_with_mocked_fetchers(tmp_path, monkeypatch):
    from autopatent.search.providers import OnlineSearchProvider

    def _mock_openalex(self, *, query, endpoint, direction_ids):
        return [
            {
                "source": "OPENALEX",
                "endpoint": endpoint,
                "query": query,
                "title": f"{query} openalex result",
                "related_direction_ids": direction_ids,
                "rank": 1,
            }
        ]

    def _mock_arxiv(self, *, query, endpoint, direction_ids):
        return [
            {
                "source": "ARXIV",
                "endpoint": endpoint,
                "query": query,
                "title": f"{query} arxiv result",
                "related_direction_ids": direction_ids,
                "rank": 1,
            }
        ]

    monkeypatch.setattr(OnlineSearchProvider, "_fetch_openalex", _mock_openalex)
    monkeypatch.setattr(OnlineSearchProvider, "_fetch_arxiv", _mock_arxiv)

    ctx = StageContext(
        work_dir=tmp_path,
        metadata={
            "topic": "抗量子SSL和证书",
            "search_provider": "online",
            "direction_candidates": [
                {"id": "1", "title": "混合证书链", "summary": "s1"},
                {"id": "2", "title": "握手协商扩展", "summary": "s2"},
            ],
        },
    )
    stage = PriorArtScanStage()
    stage.run(ctx)

    evidence = _read_jsonl(tmp_path / "artifacts" / "prior_art_evidence.jsonl")
    meta = json.loads((tmp_path / "artifacts" / "search_meta.json").read_text(encoding="utf-8"))
    assert meta["provider"] == "online"
    assert meta["raw_hits"] >= 2
    assert len(evidence) >= 2


def test_prior_art_scan_online_generates_english_query_variants(tmp_path, monkeypatch):
    from autopatent.search.providers import OnlineSearchProvider

    captured_queries = []

    def _capture_openalex(self, *, query, endpoint, direction_ids):
        captured_queries.append(query)
        return []

    def _capture_arxiv(self, *, query, endpoint, direction_ids):
        captured_queries.append(query)
        return []

    monkeypatch.setattr(OnlineSearchProvider, "_fetch_openalex", _capture_openalex)
    monkeypatch.setattr(OnlineSearchProvider, "_fetch_arxiv", _capture_arxiv)

    ctx = StageContext(
        work_dir=tmp_path,
        metadata={
            "topic": "抗量子SSL和证书",
            "search_provider": "online",
            "direction_candidates": [
                {"id": "1", "title": "混合证书链", "summary": "s1"},
            ],
        },
    )
    stage = PriorArtScanStage()
    stage.run(ctx)

    assert any("post-quantum" in item.lower() for item in captured_queries)


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


def test_prior_art_scan_with_plugin_hub_writes_plugin_stats(tmp_path, monkeypatch):
    class _Provider:
        name = "plugin-hub"
        last_meta = {
            "provider": "plugin-hub",
            "plugins": {"openalex": {"success": 1, "failed": 0, "skipped": 0, "fallback_used": 0}},
            "fallback_sources": {"jina_reader": 0, "crawl4ai": 0, "fallback_unavailable": 0},
            "circuit_breaker": {"trip_count": 0, "plugins": []},
            "errors_sample": [],
        }

        def collect(self, *, topic, resources, queries, candidates):
            _ = topic, resources, queries, candidates
            return [
                {
                    "source": "OPENALEX",
                    "endpoint": "https://api.openalex.org/works",
                    "query": "q1",
                    "title": "Plugin hub test hit",
                    "rank": 1,
                    "plugin_id": "openalex",
                    "via_fallback": False,
                    "related_direction_ids": ["1"],
                }
            ]

    monkeypatch.setattr(
        "autopatent.pipeline.stages.stage_02_prior_art_scan.get_search_provider",
        lambda name, plugin_hub_config=None: _Provider(),
    )

    ctx = StageContext(
        work_dir=tmp_path,
        metadata={
            "topic": "抗量子SSL和证书",
            "search_provider": "plugin-hub",
            "search": {
                "plugin_hub": {
                    "enabled_plugins": ["openalex"],
                }
            },
            "direction_candidates": [
                {"id": "1", "title": "方向A", "summary": "s1"},
            ],
        },
    )
    PriorArtScanStage().run(ctx)

    meta = json.loads((tmp_path / "artifacts" / "search_meta.json").read_text(encoding="utf-8"))
    assert meta["provider"] == "plugin-hub"
    assert "plugins" in meta
    assert "fallback_sources" in meta
    assert meta["plugins"]["openalex"]["success"] == 1


def test_evidence_contains_plugin_and_fallback_fields(tmp_path):
    ctx = StageContext(
        work_dir=tmp_path,
        metadata={
            "topic": "国密 TLCP / IPSec 混合抗量子方案",
            "search_provider": "seed-only",
            "direction_candidates": [
                {"id": "1", "title": "方向A", "summary": "s1"},
            ],
        },
    )
    PriorArtScanStage().run(ctx)
    row = _read_jsonl(tmp_path / "artifacts" / "prior_art_evidence.jsonl")[0]
    assert "plugin_id" in row
    assert "via_fallback" in row
    assert "fallback_source" in row
