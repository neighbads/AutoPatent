"""Configuration helpers for AutoPatent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any, Mapping, Optional


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
class AutoPatentConfig:
    """Application configuration surface."""

    checkpoint_root: Path
    search_provider: str = "offline"
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

        llm_cfg = None
        if payload and "llm" in payload and payload["llm"] is not None:
            raw_llm = payload["llm"]
            if not isinstance(raw_llm, Mapping):
                raise ValueError("llm must be an object")
            llm_cfg = LLMConfig.from_mapping(raw_llm)

        return cls(
            checkpoint_root=root.expanduser().resolve(),
            search_provider=search_provider,
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
