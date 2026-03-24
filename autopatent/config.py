"""Configuration helpers for AutoPatent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional


@dataclass
class AutoPatentConfig:
    """Application configuration surface."""

    checkpoint_root: Path

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "AutoPatentConfig":
        raw_root = payload.get("checkpoint_root") if payload else None
        if raw_root:
            root = Path(raw_root)
        else:
            root = Path.cwd() / "state"
        return cls(checkpoint_root=root.expanduser().resolve())


def load_config(config_path: Optional[Path] = None) -> AutoPatentConfig:
    """Load config from a JSON file or use defaults."""

    candidate = Path(config_path) if config_path else Path.cwd() / "config.json"
    payload: Mapping[str, Any] = {}
    if candidate.is_file():
        payload = json.loads(candidate.read_text())
    return AutoPatentConfig.from_mapping(payload)
