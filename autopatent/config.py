"""Configuration helpers for AutoPatent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import Any, Mapping, Optional


@dataclass
class AutoPatentConfig:
    """Application configuration surface."""

    checkpoint_root: Path

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
        return cls(checkpoint_root=root.expanduser().resolve())


def load_config(config_path: Optional[Path] = None) -> AutoPatentConfig:
    """Load config from a JSON file or use defaults."""

    candidate = Path(config_path) if config_path else Path.cwd() / "config.json"
    payload: Mapping[str, Any] = {}
    if candidate.is_file():
        try:
            payload = json.loads(candidate.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Unable to parse config file at {candidate}: {exc}"
            ) from exc
    return AutoPatentConfig.from_mapping(payload)
