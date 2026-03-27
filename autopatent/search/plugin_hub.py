from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from autopatent.search.fallback import run_crawl4ai, run_jina_reader
from autopatent.search.plugins import SearchSitePlugin, resolve_plugins
from autopatent.search.plugins.base import RequestSpec


@dataclass(frozen=True)
class PluginHubRuntimeConfig:
    enabled_plugins: list[str]
    max_workers: int
    request_timeout_sec: int
    retry_max_attempts: int
    retry_backoff_base_sec: float
    cb_failure_threshold: int
    cb_cooldown_sec: int
    enable_fallback: bool
    fallback_chain: list[str]

    @classmethod
    def from_mapping(cls, payload: dict[str, Any] | None) -> "PluginHubRuntimeConfig":
        source = payload or {}
        retry = source.get("retry")
        if not isinstance(retry, dict):
            retry = {}
        circuit_breaker = source.get("circuit_breaker")
        if not isinstance(circuit_breaker, dict):
            circuit_breaker = {}
        enabled_plugins = source.get("enabled_plugins")
        if not isinstance(enabled_plugins, list) or not enabled_plugins:
            enabled_plugins = ["openalex", "arxiv", "semantic_scholar", "crossref", "epo_ops"]
        fallback_chain = source.get("fallback_chain")
        if not isinstance(fallback_chain, list) or not fallback_chain:
            fallback_chain = ["jina_reader", "crawl4ai"]
        return cls(
            enabled_plugins=[str(item).strip() for item in enabled_plugins if str(item).strip()],
            max_workers=max(1, int(source.get("max_workers", 8))),
            request_timeout_sec=max(3, int(source.get("request_timeout_sec", 20))),
            retry_max_attempts=max(1, int(retry.get("max_attempts", 3))),
            retry_backoff_base_sec=max(0.1, float(retry.get("backoff_base_sec", 1.0))),
            cb_failure_threshold=max(1, int(circuit_breaker.get("failure_threshold", 3))),
            cb_cooldown_sec=max(10, int(circuit_breaker.get("cooldown_sec", 120))),
            enable_fallback=bool(source.get("enable_fallback", True)),
            fallback_chain=[str(item).strip() for item in fallback_chain if str(item).strip()],
        )


@dataclass
class _CircuitState:
    consecutive_failures: int = 0
    tripped_until: float = 0.0


class PluginHubProvider:
    name = "plugin-hub"

    def __init__(
        self,
        *,
        config: PluginHubRuntimeConfig | None = None,
        user_agent: str = "AutoPatent/0.1 (+https://local.autopatent)",
    ) -> None:
        self.config = config or PluginHubRuntimeConfig.from_mapping(None)
        self.user_agent = user_agent
        self.last_meta: dict[str, Any] = {}

    def collect(
        self,
        *,
        topic: str,
        resources: list[dict[str, str]],
        queries: list[str],
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        _ = resources
        plugins = resolve_plugins(self.config.enabled_plugins)
        direction_ids = [str(c.get("id")) for c in candidates if "id" in c]

        hits: list[dict[str, Any]] = []
        plugin_stats: dict[str, dict[str, int]] = {}
        circuit_breaker = {"trip_count": 0, "plugins": []}
        fallback_sources: dict[str, int] = {
            "jina_reader": 0,
            "crawl4ai": 0,
            "fallback_unavailable": 0,
        }
        errors_sample: list[str] = []

        for plugin in plugins:
            plugin_id = plugin.plugin_id()
            stats = {"success": 0, "failed": 0, "skipped": 0, "fallback_used": 0}
            plugin_stats[plugin_id] = stats
            breaker = _CircuitState()

            for query in queries:
                if not plugin.supports(query, topic):
                    stats["skipped"] += 1
                    continue

                if time.time() < breaker.tripped_until:
                    stats["skipped"] += 1
                    continue

                requests = plugin.build_requests(query, topic, limit=3)
                if not requests:
                    stats["skipped"] += 1
                    continue

                for request in requests:
                    request = RequestSpec(
                        method=request.method,
                        url=request.url,
                        headers=request.headers,
                        timeout_sec=request.timeout_sec or self.config.request_timeout_sec,
                        meta={**request.meta, "query": query},
                    )
                    result = self._execute_request(plugin=plugin, request=request, topic=topic, query=query)
                    for fallback_source in result["fallback_observed"]:
                        fallback_sources[fallback_source] = fallback_sources.get(fallback_source, 0) + 1
                    if result["hits"]:
                        stats["success"] += 1
                        if result["fallback_source"]:
                            stats["fallback_used"] += 1
                            fallback_sources[result["fallback_source"]] = (
                                fallback_sources.get(result["fallback_source"], 0) + 1
                            )
                        breaker.consecutive_failures = 0
                        for idx, hit in enumerate(result["hits"], start=1):
                            record = dict(hit)
                            record.setdefault("source", plugin_id.upper())
                            record.setdefault("endpoint", request.url)
                            record.setdefault("query", query)
                            record.setdefault("rank", idx)
                            record.setdefault("plugin_id", plugin_id)
                            record.setdefault("related_direction_ids", direction_ids)
                            if result["fallback_source"]:
                                record["via_fallback"] = True
                                record["fallback_source"] = result["fallback_source"]
                            hits.append(record)
                        continue

                    stats["failed"] += 1
                    breaker.consecutive_failures += 1
                    if result["error"] and len(errors_sample) < 20:
                        errors_sample.append(
                            f"{plugin_id}:{query[:80]} -> {result['error'][:180]}"
                        )
                    if breaker.consecutive_failures >= self.config.cb_failure_threshold:
                        breaker.tripped_until = time.time() + self.config.cb_cooldown_sec
                        breaker.consecutive_failures = 0
                        circuit_breaker["trip_count"] += 1
                        if plugin_id not in circuit_breaker["plugins"]:
                            circuit_breaker["plugins"].append(plugin_id)

        self.last_meta = {
            "provider": self.name,
            "plugins": plugin_stats,
            "circuit_breaker": circuit_breaker,
            "errors_sample": errors_sample,
            "fallback_sources": fallback_sources,
        }
        return hits

    def _execute_request(
        self,
        *,
        plugin: SearchSitePlugin,
        request: RequestSpec,
        topic: str,
        query: str,
    ) -> dict[str, Any]:
        last_error = ""
        for attempt in range(1, self.config.retry_max_attempts + 1):
            try:
                payload = self._http_get(
                    url=request.url,
                    headers=request.headers,
                    timeout_sec=request.timeout_sec or self.config.request_timeout_sec,
                )
                parsed = plugin.parse_response(payload, request)
                if parsed:
                    return {
                        "hits": parsed,
                        "error": "",
                        "fallback_source": "",
                        "fallback_observed": [],
                    }
                last_error = "empty parsed result"
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
            if attempt < self.config.retry_max_attempts:
                time.sleep(self.config.retry_backoff_base_sec * (2 ** (attempt - 1)))

        if not self.config.enable_fallback:
            return {"hits": [], "error": last_error, "fallback_source": "", "fallback_observed": []}

        fallback_observed: list[str] = []
        fallback_urls = plugin.fallback_urls(query, topic, limit=3)
        for runner in self.config.fallback_chain:
            for url in fallback_urls[:3]:
                if runner == "jina_reader":
                    fallback = run_jina_reader(
                        target_url=url,
                        timeout_sec=self.config.request_timeout_sec,
                        user_agent=self.user_agent,
                    )
                elif runner == "crawl4ai":
                    fallback = run_crawl4ai(
                        target_url=url,
                        timeout_sec=self.config.request_timeout_sec,
                    )
                else:
                    continue

                if fallback.status == "fallback_unavailable":
                    fallback_observed.append("fallback_unavailable")
                    continue
                if fallback.status != "ok":
                    last_error = fallback.error or last_error
                    continue

                parsed = plugin.parse_fallback(fallback.content, url, query, fallback.source)
                if parsed:
                    return {
                        "hits": parsed,
                        "error": "",
                        "fallback_source": fallback.source,
                        "fallback_observed": fallback_observed,
                    }
                last_error = "fallback parsed empty"

        return {
            "hits": [],
            "error": last_error or "request failed",
            "fallback_source": "",
            "fallback_observed": fallback_observed,
        }

    def _http_get(self, *, url: str, headers: dict[str, str], timeout_sec: int) -> str:
        request_headers = {"User-Agent": self.user_agent}
        request_headers.update(headers or {})
        req = urllib.request.Request(
            url,
            headers=request_headers,
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=max(1, int(timeout_sec))) as resp:
                body = resp.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {exc.code}: {raw[:180]}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(str(exc.reason)) from exc
        return body.decode("utf-8", errors="ignore")

    def format_meta_json(self) -> str:
        return json.dumps(self.last_meta, ensure_ascii=False, indent=2)
