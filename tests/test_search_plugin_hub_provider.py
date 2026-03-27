from __future__ import annotations

from autopatent.search.plugin_hub import PluginHubProvider, PluginHubRuntimeConfig
from autopatent.search.plugins.base import RequestSpec


class _HappyPlugin:
    def plugin_id(self) -> str:
        return "happy_plugin"

    def supports(self, query: str, topic: str) -> bool:
        _ = topic
        return bool(query)

    def build_requests(self, query: str, topic: str, limit: int) -> list[RequestSpec]:
        _ = topic, limit
        return [RequestSpec(method="GET", url=f"https://example.com?q={query}", meta={"query": query})]

    def parse_response(self, payload: str | bytes, request: RequestSpec) -> list[dict]:
        _ = payload
        return [
            {
                "source": "TEST",
                "title": f"hit for {request.meta.get('query')}",
                "query": str(request.meta.get("query")),
                "rank": 1,
            }
        ]

    def fallback_urls(self, query: str, topic: str, limit: int) -> list[str]:
        _ = query, topic, limit
        return []

    def parse_fallback(self, payload: str, url: str, query: str, source: str) -> list[dict]:
        _ = payload, url, query, source
        return []


class _FallbackPlugin:
    def plugin_id(self) -> str:
        return "fallback_plugin"

    def supports(self, query: str, topic: str) -> bool:
        _ = topic
        return bool(query)

    def build_requests(self, query: str, topic: str, limit: int) -> list[RequestSpec]:
        _ = topic, limit
        return [RequestSpec(method="GET", url=f"https://broken.example?q={query}", meta={"query": query})]

    def parse_response(self, payload: str | bytes, request: RequestSpec) -> list[dict]:
        _ = payload, request
        return []

    def fallback_urls(self, query: str, topic: str, limit: int) -> list[str]:
        _ = topic, limit
        return [f"https://fallback.example/{query}"]

    def parse_fallback(self, payload: str, url: str, query: str, source: str) -> list[dict]:
        _ = payload, url
        return [{"source": "TEST", "title": f"fallback {query}", "query": query, "rank": 1, "fallback_source": source}]


def test_plugin_hub_provider_collects_hits_with_stats(monkeypatch):
    monkeypatch.setattr("autopatent.search.plugin_hub.resolve_plugins", lambda ids: [_HappyPlugin()])  # type: ignore[arg-type]
    monkeypatch.setattr(PluginHubProvider, "_http_get", lambda *args, **kwargs: "{}")

    provider = PluginHubProvider(
        config=PluginHubRuntimeConfig.from_mapping(
            {
                "enabled_plugins": ["openalex"],
                "retry": {"max_attempts": 1},
            }
        )
    )
    hits = provider.collect(
        topic="topic",
        resources=[],
        queries=["q1"],
        candidates=[{"id": "1"}],
    )

    assert len(hits) == 1
    assert provider.last_meta["provider"] == "plugin-hub"
    assert provider.last_meta["plugins"]["happy_plugin"]["success"] == 1


def test_plugin_hub_fallback_chain_records_source(monkeypatch):
    monkeypatch.setattr("autopatent.search.plugin_hub.resolve_plugins", lambda ids: [_FallbackPlugin()])  # type: ignore[arg-type]
    monkeypatch.setattr(
        PluginHubProvider,
        "_http_get",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    class _Result:
        status = "ok"
        source = "jina_reader"
        content = "fallback content"
        error = ""
        url = "https://r.jina.ai/http://fallback.example"

    monkeypatch.setattr("autopatent.search.plugin_hub.run_jina_reader", lambda **kwargs: _Result())

    provider = PluginHubProvider(
        config=PluginHubRuntimeConfig.from_mapping(
            {
                "enabled_plugins": ["openalex"],
                "retry": {"max_attempts": 1},
                "enable_fallback": True,
                "fallback_chain": ["jina_reader"],
            }
        )
    )
    hits = provider.collect(topic="topic", resources=[], queries=["q1"], candidates=[])
    assert len(hits) == 1
    assert provider.last_meta["plugins"]["fallback_plugin"]["fallback_used"] == 1
    assert provider.last_meta["fallback_sources"]["jina_reader"] >= 1
