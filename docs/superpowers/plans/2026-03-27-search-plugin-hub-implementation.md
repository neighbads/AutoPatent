# Search Plugin Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `STAGE_02` 落地可扩展检索框架（plugin-hub），支持首批 5 个站点插件与 `r.jina.ai -> crawl4ai` 多级回退。

**Architecture:** 保留现有 `offline/seed-only/online` provider，不破坏兼容；新增 `plugin-hub` 作为独立 provider，内部统一处理并发、重试、熔断、回退与观测。站点插件仅负责请求构建与解析，执行策略由内核统一管理。

**Tech Stack:** Python 3.11, urllib, dataclasses, Typer CLI, pytest

---

## File Structure

### Create
- `autopatent/search/plugin_hub.py`
- `autopatent/search/plugins/__init__.py`
- `autopatent/search/plugins/base.py`
- `autopatent/search/plugins/registry.py`
- `autopatent/search/plugins/openalex_plugin.py`
- `autopatent/search/plugins/arxiv_plugin.py`
- `autopatent/search/plugins/semantic_scholar_plugin.py`
- `autopatent/search/plugins/crossref_plugin.py`
- `autopatent/search/plugins/epo_ops_plugin.py`
- `autopatent/search/fallback/__init__.py`
- `autopatent/search/fallback/jina_reader_runner.py`
- `autopatent/search/fallback/crawl4ai_runner.py`
- `tests/test_search_plugin_hub_config.py`
- `tests/test_search_plugin_registry.py`
- `tests/test_search_fallback_runners.py`
- `tests/test_search_plugin_hub_provider.py`
- `tests/test_search_plugins_parsing.py`

### Modify
- `autopatent/config.py`
- `autopatent/search/__init__.py`
- `autopatent/search/providers.py`
- `autopatent/search/evidence_summary.py`
- `autopatent/pipeline/stages/stage_02_prior_art_scan.py`
- `tests/test_checkpoint_resume.py`
- `tests/test_prior_art_pipeline.py`
- `README.md`

### Responsibilities
- `plugin_hub.py`：统一执行语义（并发、重试、熔断、fallback chain、统计）
- `plugins/*`：站点适配层（请求构建 + 解析）
- `fallback/*`：回退抓取执行器（`r.jina.ai` 与 `crawl4ai`）
- `stage_02_prior_art_scan.py`：接入 provider + 扩展 `search_meta.json` 输出
- `config.py`：新增 plugin-hub 配置解析与 fail-fast 校验

---

### Task 1: 配置模型扩展（plugin-hub）

**Files:**
- Modify: `autopatent/config.py`
- Modify: `tests/test_checkpoint_resume.py`
- Create: `tests/test_search_plugin_hub_config.py`

- [ ] **Step 1: 写失败测试（默认值与校验）**

```python
def test_load_config_parses_plugin_hub_defaults(tmp_path):
    cfg = load_config(config_path=...)
    assert cfg.search.plugin_hub.max_workers == 8
    assert cfg.search.plugin_hub.fallback_chain == ["jina_reader", "crawl4ai"]

def test_load_config_rejects_unknown_plugin_id(tmp_path):
    with pytest.raises(ValueError):
        load_config(...)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=. pytest -q tests/test_search_plugin_hub_config.py -k plugin_hub`  
Expected: FAIL（配置模型尚未支持）

- [ ] **Step 3: 实现配置结构与校验**

```python
@dataclass
class PluginHubConfig:
    enabled_plugins: list[str]
    max_workers: int
    request_timeout_sec: int
    retry_max_attempts: int
    retry_backoff_base_sec: float
    cb_failure_threshold: int
    cb_cooldown_sec: int
    enable_fallback: bool
    fallback_chain: list[str]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONPATH=. pytest -q tests/test_search_plugin_hub_config.py tests/test_checkpoint_resume.py`  
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add autopatent/config.py tests/test_search_plugin_hub_config.py tests/test_checkpoint_resume.py
git commit -m "feat(config): 增加 plugin-hub 检索配置与校验"
```

---

### Task 2: 插件协议与注册表

**Files:**
- Create: `autopatent/search/plugins/base.py`
- Create: `autopatent/search/plugins/registry.py`
- Create: `autopatent/search/plugins/__init__.py`
- Modify: `autopatent/search/__init__.py`
- Create: `tests/test_search_plugin_registry.py`

- [ ] **Step 1: 写失败测试（注册发现与未知插件报错）**

```python
def test_registry_loads_builtin_plugins():
    ids = builtin_plugin_ids()
    assert "openalex" in ids

def test_registry_rejects_unknown_plugin():
    with pytest.raises(ValueError):
        resolve_plugins(["not-exist"])
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=. pytest -q tests/test_search_plugin_registry.py`  
Expected: FAIL

- [ ] **Step 3: 实现插件契约和注册逻辑**

```python
class SearchSitePlugin(Protocol):
    def plugin_id(self) -> str: ...
    def supports(self, query: str, topic: str) -> bool: ...
    def build_requests(self, query: str, topic: str, limit: int) -> list[RequestSpec]: ...
    def parse_response(self, payload: str | bytes, request: RequestSpec) -> list[RawHit]: ...
    def fallback_urls(self, query: str, topic: str, limit: int) -> list[str]: ...
    def parse_fallback(self, payload: str, url: str, query: str, source: str) -> list[RawHit]: ...
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONPATH=. pytest -q tests/test_search_plugin_registry.py`  
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add autopatent/search/plugins/base.py autopatent/search/plugins/registry.py autopatent/search/plugins/__init__.py autopatent/search/__init__.py tests/test_search_plugin_registry.py
git commit -m "feat(search): 新增插件协议与注册中心"
```

---

### Task 3: 回退执行器（jina_reader + crawl4ai）

**Files:**
- Create: `autopatent/search/fallback/__init__.py`
- Create: `autopatent/search/fallback/jina_reader_runner.py`
- Create: `autopatent/search/fallback/crawl4ai_runner.py`
- Create: `tests/test_search_fallback_runners.py`

- [ ] **Step 1: 写失败测试（URL 转换与不可用降级）**

```python
def test_jina_reader_wraps_url():
    assert wrap_jina_reader_url("https://example.com").startswith("https://r.jina.ai/")

def test_crawl4ai_runner_returns_unavailable_when_not_installed():
    result = run_crawl4ai(...)
    assert result.status == "fallback_unavailable"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=. pytest -q tests/test_search_fallback_runners.py`  
Expected: FAIL

- [ ] **Step 3: 实现两个执行器**

```python
def run_jina_reader(url: str, timeout_sec: int) -> FallbackResult: ...
def run_crawl4ai(url: str, timeout_sec: int) -> FallbackResult: ...
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONPATH=. pytest -q tests/test_search_fallback_runners.py`  
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add autopatent/search/fallback/__init__.py autopatent/search/fallback/jina_reader_runner.py autopatent/search/fallback/crawl4ai_runner.py tests/test_search_fallback_runners.py
git commit -m "feat(search): 增加 jina_reader 与 crawl4ai 回退执行器"
```

---

### Task 4: plugin-hub 内核与 provider 接入

**Files:**
- Create: `autopatent/search/plugin_hub.py`
- Modify: `autopatent/search/providers.py`
- Create: `tests/test_search_plugin_hub_provider.py`

- [ ] **Step 1: 写失败测试（provider=plugin-hub + 回退链路）**

```python
def test_plugin_hub_provider_collects_hits_with_stats(...):
    provider = get_search_provider("plugin-hub")
    hits = provider.collect(...)
    assert isinstance(hits, list)
    assert provider.last_meta["provider"] == "plugin-hub"

def test_plugin_hub_fallback_chain_records_source(...):
    assert provider.last_meta["fallback_sources"]["jina_reader"] >= 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=. pytest -q tests/test_search_plugin_hub_provider.py`  
Expected: FAIL

- [ ] **Step 3: 实现统一执行语义**

```python
class PluginHubProvider:
    name = "plugin-hub"
    def collect(...): ...
    # request-level retry, plugin-level breaker, fallback_chain
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONPATH=. pytest -q tests/test_search_plugin_hub_provider.py`  
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add autopatent/search/plugin_hub.py autopatent/search/providers.py tests/test_search_plugin_hub_provider.py
git commit -m "feat(search): 接入 plugin-hub provider 与统一执行内核"
```

---

### Task 5: 首批 5 个站点插件实现

**Files:**
- Create: `autopatent/search/plugins/openalex_plugin.py`
- Create: `autopatent/search/plugins/arxiv_plugin.py`
- Create: `autopatent/search/plugins/semantic_scholar_plugin.py`
- Create: `autopatent/search/plugins/crossref_plugin.py`
- Create: `autopatent/search/plugins/epo_ops_plugin.py`
- Create: `tests/test_search_plugins_parsing.py`

- [ ] **Step 1: 写失败测试（请求构建 + 响应解析）**

```python
def test_openalex_plugin_parses_response_fixture(): ...
def test_arxiv_plugin_parses_atom_fixture(): ...
def test_crossref_plugin_parses_items_fixture(): ...
def test_epo_plugin_skips_without_credentials(monkeypatch): ...
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=. pytest -q tests/test_search_plugins_parsing.py`  
Expected: FAIL

- [ ] **Step 3: 实现插件最小可用逻辑**

```python
class OpenAlexPlugin(SearchSitePlugin): ...
class ArxivPlugin(SearchSitePlugin): ...
class SemanticScholarPlugin(SearchSitePlugin): ...
class CrossrefPlugin(SearchSitePlugin): ...
class EpoOpsPlugin(SearchSitePlugin): ...
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONPATH=. pytest -q tests/test_search_plugins_parsing.py`  
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add autopatent/search/plugins/openalex_plugin.py autopatent/search/plugins/arxiv_plugin.py autopatent/search/plugins/semantic_scholar_plugin.py autopatent/search/plugins/crossref_plugin.py autopatent/search/plugins/epo_ops_plugin.py tests/test_search_plugins_parsing.py
git commit -m "feat(search): 增加首批五个站点插件"
```

---

### Task 6: Stage02 集成与输出契约扩展

**Files:**
- Modify: `autopatent/pipeline/stages/stage_02_prior_art_scan.py`
- Modify: `autopatent/search/evidence_summary.py`
- Modify: `tests/test_prior_art_pipeline.py`

- [ ] **Step 1: 写失败测试（meta 扩展字段与 evidence 增量字段）**

```python
def test_prior_art_scan_with_plugin_hub_writes_plugin_stats(...):
    meta = read_json(...)
    assert "plugins" in meta
    assert "fallback_sources" in meta

def test_evidence_contains_plugin_and_fallback_fields(...):
    row = read_jsonl(...)[0]
    assert "plugin_id" in row
    assert "via_fallback" in row
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=. pytest -q tests/test_prior_art_pipeline.py -k plugin_hub`  
Expected: FAIL

- [ ] **Step 3: 实现 Stage02 与 evidence mapping 扩展**

```python
meta.update(provider_meta)
record["plugin_id"] = hit.get("plugin_id")
record["via_fallback"] = bool(hit.get("via_fallback"))
record["fallback_source"] = hit.get("fallback_source")
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONPATH=. pytest -q tests/test_prior_art_pipeline.py`  
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add autopatent/pipeline/stages/stage_02_prior_art_scan.py autopatent/search/evidence_summary.py tests/test_prior_art_pipeline.py
git commit -m "feat(stage02): 集成 plugin-hub 统计与证据扩展字段"
```

---

### Task 7: 文档与配置示例更新

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 补充 plugin-hub 配置示例与 fallback_chain 说明**

Add:
- `search_provider: "plugin-hub"`
- `enabled_plugins` 示例
- `fallback_chain: ["jina_reader", "crawl4ai"]`
- `EPO_OPS_CONSUMER_KEY/SECRET` 说明

- [ ] **Step 2: 运行文档相关回归测试（如有）**

Run: `PYTHONPATH=. pytest -q tests/test_cli_pipeline_execution.py`  
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add README.md
git commit -m "docs(search): 增加 plugin-hub 与多级回退配置说明"
```

---

### Task 8: 全量验收与真实 smoke

**Files:**
- Test only (no required code change)

- [ ] **Step 1: 全量测试**

Run: `PYTHONPATH=. pytest -q`  
Expected: PASS

- [ ] **Step 2: plugin-hub smoke（无外部凭据）**

Run:

```bash
cat > /tmp/autopatent-plugin-hub.json <<'EOF'
{
  "search_provider": "plugin-hub",
  "search": {
    "plugin_hub": {
      "enabled_plugins": ["openalex", "arxiv", "semantic_scholar", "crossref", "epo_ops"],
      "enable_fallback": true,
      "fallback_chain": ["jina_reader", "crawl4ai"]
    }
  }
}
EOF

PYTHONPATH=. python -m autopatent.cli run \
  --topic "国密 TLCP / IPSec 混合抗量子方案的设计、实现与评估" \
  --output /tmp/autopatent-plugin-hub-smoke \
  --config /tmp/autopatent-plugin-hub.json \
  --auto-approve
```

Expected:
- pipeline 完成
- `artifacts/search_meta.json` 包含 `provider=plugin-hub`
- `plugins` 与 `fallback_sources` 字段存在

- [ ] **Step 3: 最终收口提交（如需）**

```bash
git add .
git commit -m "chore(search): 完成 plugin-hub 子项目2 全链路验收"
```

---

## Final Verification Checklist

- [ ] `search_provider=plugin-hub` 可跑通 Stage02
- [ ] 首批 5 插件可被注册并按配置启停
- [ ] `r.jina.ai -> crawl4ai` 回退链路可观测
- [ ] `search_meta.json` 包含插件统计与回退来源统计
- [ ] `prior_art_evidence.jsonl` 包含 `plugin_id/via_fallback/fallback_source`
- [ ] 现有 `offline/seed-only/online` 不回归
- [ ] 全量 `pytest -q` 通过

