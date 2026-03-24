"""Data models used by AutoPatent."""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class Checkpoint:
    """Represents a persisted checkpoint state."""

    stage_id: str
    status: str
    updated_at: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, str]) -> "Checkpoint":
        required_keys = ("stage_id", "status", "updated_at")
        for key in required_keys:
            if key not in payload:
                raise ValueError(
                    f"Checkpoint entry missing required key '{key}': {payload}"
                )
            if not isinstance(payload[key], str):
                raise ValueError(
                    f"Checkpoint entry key '{key}' must be a string, got {type(payload[key]).__name__}"
                )
        return cls(
            stage_id=payload["stage_id"],
            status=payload["status"],
            updated_at=payload["updated_at"],
        )
