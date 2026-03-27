"""Configuration helpers for AutoPatent."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import Any, Mapping, Optional

_DEFAULT_PLUGIN_IDS = (
    "openalex",
    "arxiv",
    "semantic_scholar",
    "crossref",
    "epo_ops",
)
_ALLOWED_PLUGIN_IDS = set(_DEFAULT_PLUGIN_IDS)
_DEFAULT_FALLBACK_CHAIN = ("jina_reader", "crawl4ai")
_ALLOWED_FALLBACK_RUNNERS = set(_DEFAULT_FALLBACK_CHAIN)


def _as_mapping(payload: Any, *, key: str) -> Mapping[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError(f"{key} must be an object")
    return payload


def _as_int_in_range(
    value: Any,
    *,
    key: str,
    min_value: int,
    max_value: int,
) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    if value < min_value or value > max_value:
        raise ValueError(f"{key} must be in range [{min_value}, {max_value}]")
    return value


def _as_float_in_range(
    value: Any,
    *,
    key: str,
    min_exclusive: float,
    max_inclusive: float,
) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number")
    numeric = float(value)
    if numeric <= min_exclusive or numeric > max_inclusive:
        raise ValueError(f"{key} must be in range ({min_exclusive}, {max_inclusive}]")
    return numeric


def _as_string_list(value: Any, *, key: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{key} must be a list of strings")
    normalized: list[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            raise ValueError(f"{key}[{idx}] must be a string")
        text = item.strip()
        if not text:
            raise ValueError(f"{key}[{idx}] must be a non-empty string")
        normalized.append(text)
    return normalized


@dataclass
class LLMConfig:
    provider: str
    base_url: str
    api_key_env: str
    model: str
    timeout_sec: int = 60
    max_tokens: int = 4096
    temperature: float = 0.2

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "LLMConfig":
        provider = str(payload.get("provider") or "").strip()
        base_url = str(payload.get("base_url") or "").strip()
        api_key_env = str(payload.get("api_key_env") or "").strip()
        model = str(payload.get("model") or "").strip()

        if not provider:
            raise ValueError("llm.provider is required")
        if not base_url:
            raise ValueError("llm.base_url is required")
        if not api_key_env:
            raise ValueError("llm.api_key_env is required")
        if not model:
            raise ValueError("llm.model is required")

        timeout_raw = payload.get("timeout_sec", 60)
        max_tokens_raw = payload.get("max_tokens", 4096)
        temperature_raw = payload.get("temperature", 0.2)

        if not isinstance(timeout_raw, int) or timeout_raw <= 0:
            raise ValueError("llm.timeout_sec must be a positive integer")
        if not isinstance(max_tokens_raw, int) or max_tokens_raw <= 0:
            raise ValueError("llm.max_tokens must be a positive integer")
        if not isinstance(temperature_raw, (int, float)):
            raise ValueError("llm.temperature must be a number")

        return cls(
            provider=provider,
            base_url=base_url,
            api_key_env=api_key_env,
            model=model,
            timeout_sec=timeout_raw,
            max_tokens=max_tokens_raw,
            temperature=float(temperature_raw),
        )

    def to_runtime_mapping(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "model": self.model,
            "timeout_sec": self.timeout_sec,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }


@dataclass
class PluginHubRetryConfig:
    max_attempts: int = 3
    backoff_base_sec: float = 1.0

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "PluginHubRetryConfig":
        max_attempts = _as_int_in_range(
            payload.get("max_attempts", 3),
            key="search.plugin_hub.retry.max_attempts",
            min_value=1,
            max_value=6,
        )
        backoff_base_sec = _as_float_in_range(
            payload.get("backoff_base_sec", 1.0),
            key="search.plugin_hub.retry.backoff_base_sec",
            min_exclusive=0.0,
            max_inclusive=10.0,
        )
        return cls(max_attempts=max_attempts, backoff_base_sec=backoff_base_sec)

    def to_runtime_mapping(self) -> dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "backoff_base_sec": self.backoff_base_sec,
        }


@dataclass
class PluginHubCircuitBreakerConfig:
    failure_threshold: int = 3
    cooldown_sec: int = 120

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "PluginHubCircuitBreakerConfig":
        failure_threshold = _as_int_in_range(
            payload.get("failure_threshold", 3),
            key="search.plugin_hub.circuit_breaker.failure_threshold",
            min_value=1,
            max_value=20,
        )
        cooldown_sec = _as_int_in_range(
            payload.get("cooldown_sec", 120),
            key="search.plugin_hub.circuit_breaker.cooldown_sec",
            min_value=10,
            max_value=3600,
        )
        return cls(
            failure_threshold=failure_threshold,
            cooldown_sec=cooldown_sec,
        )

    def to_runtime_mapping(self) -> dict[str, Any]:
        return {
            "failure_threshold": self.failure_threshold,
            "cooldown_sec": self.cooldown_sec,
        }


@dataclass
class PluginHubConfig:
    enabled_plugins: list[str] = field(default_factory=lambda: list(_DEFAULT_PLUGIN_IDS))
    max_workers: int = 8
    request_timeout_sec: int = 20
    retry: PluginHubRetryConfig = field(default_factory=PluginHubRetryConfig)
    circuit_breaker: PluginHubCircuitBreakerConfig = field(
        default_factory=PluginHubCircuitBreakerConfig
    )
    enable_fallback: bool = True
    fallback_chain: list[str] = field(default_factory=lambda: list(_DEFAULT_FALLBACK_CHAIN))

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "PluginHubConfig":
        enabled_plugins = _as_string_list(
            payload.get("enabled_plugins", list(_DEFAULT_PLUGIN_IDS)),
            key="search.plugin_hub.enabled_plugins",
        )
        unknown_plugins = sorted({p for p in enabled_plugins if p not in _ALLOWED_PLUGIN_IDS})
        if unknown_plugins:
            raise ValueError(
                "search.plugin_hub.enabled_plugins contains unknown plugin ids: "
                + ", ".join(unknown_plugins)
            )

        max_workers = _as_int_in_range(
            payload.get("max_workers", 8),
            key="search.plugin_hub.max_workers",
            min_value=1,
            max_value=64,
        )
        request_timeout_sec = _as_int_in_range(
            payload.get("request_timeout_sec", 20),
            key="search.plugin_hub.request_timeout_sec",
            min_value=3,
            max_value=120,
        )

        retry = PluginHubRetryConfig.from_mapping(
            _as_mapping(payload.get("retry"), key="search.plugin_hub.retry")
        )
        circuit_breaker = PluginHubCircuitBreakerConfig.from_mapping(
            _as_mapping(
                payload.get("circuit_breaker"),
                key="search.plugin_hub.circuit_breaker",
            )
        )

        enable_fallback_raw = payload.get("enable_fallback", True)
        if not isinstance(enable_fallback_raw, bool):
            raise ValueError("search.plugin_hub.enable_fallback must be a boolean")

        fallback_chain = _as_string_list(
            payload.get("fallback_chain", list(_DEFAULT_FALLBACK_CHAIN)),
            key="search.plugin_hub.fallback_chain",
        )
        unknown_fallback = sorted(
            {runner for runner in fallback_chain if runner not in _ALLOWED_FALLBACK_RUNNERS}
        )
        if unknown_fallback:
            raise ValueError(
                "search.plugin_hub.fallback_chain contains unsupported runners: "
                + ", ".join(unknown_fallback)
            )

        return cls(
            enabled_plugins=enabled_plugins,
            max_workers=max_workers,
            request_timeout_sec=request_timeout_sec,
            retry=retry,
            circuit_breaker=circuit_breaker,
            enable_fallback=enable_fallback_raw,
            fallback_chain=fallback_chain,
        )

    def to_runtime_mapping(self) -> dict[str, Any]:
        return {
            "enabled_plugins": list(self.enabled_plugins),
            "max_workers": self.max_workers,
            "request_timeout_sec": self.request_timeout_sec,
            "retry": self.retry.to_runtime_mapping(),
            "circuit_breaker": self.circuit_breaker.to_runtime_mapping(),
            "enable_fallback": self.enable_fallback,
            "fallback_chain": list(self.fallback_chain),
        }


@dataclass
class SearchConfig:
    plugin_hub: PluginHubConfig = field(default_factory=PluginHubConfig)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SearchConfig":
        plugin_hub = PluginHubConfig.from_mapping(
            _as_mapping(payload.get("plugin_hub"), key="search.plugin_hub")
        )
        return cls(plugin_hub=plugin_hub)

    def to_runtime_mapping(self) -> dict[str, Any]:
        return {"plugin_hub": self.plugin_hub.to_runtime_mapping()}


@dataclass
class AutoPatentConfig:
    """Application configuration surface."""

    checkpoint_root: Path
    search_provider: str = "offline"
    search: SearchConfig = field(default_factory=SearchConfig)
    llm: Optional[LLMConfig] = None

    @classmethod
    def from_mapping(cls, payload: Optional[Mapping[str, Any]] = None) -> "AutoPatentConfig":
        raw_root = payload.get("checkpoint_root") if payload else None
        if raw_root is None:
            root = Path.cwd() / "state"
        elif isinstance(raw_root, (str, PathLike)):
            root = Path(raw_root)
        else:
            raise ValueError(
                "checkpoint_root must be a string or path-like, got "
                f"{type(raw_root).__name__}"
            )
        search_provider_raw = payload.get("search_provider", "offline") if payload else "offline"
        if not isinstance(search_provider_raw, str):
            raise ValueError("search_provider must be a string")
        search_provider = search_provider_raw.strip() or "offline"
        search_cfg = SearchConfig.from_mapping(
            _as_mapping(payload.get("search") if payload else None, key="search")
        )

        llm_cfg = None
        if payload and "llm" in payload and payload["llm"] is not None:
            raw_llm = payload["llm"]
            if not isinstance(raw_llm, Mapping):
                raise ValueError("llm must be an object")
            llm_cfg = LLMConfig.from_mapping(raw_llm)

        return cls(
            checkpoint_root=root.expanduser().resolve(),
            search_provider=search_provider,
            search=search_cfg,
            llm=llm_cfg,
        )


def load_config(config_path: Optional[Path] = None) -> AutoPatentConfig:
    """Load config from a JSON file or use defaults."""

    candidate = Path(config_path) if config_path else Path.cwd() / "config.json"
    payload: Mapping[str, Any] = {}
    if candidate.is_file():
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Unable to parse config file at {candidate}: {exc}"
            ) from exc
    return AutoPatentConfig.from_mapping(payload)
