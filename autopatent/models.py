"""Data models used by AutoPatent."""

from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class Checkpoint:
    """Represents a persisted checkpoint state."""

    stage_id: str
    status: str
    recorded_at: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, str]) -> "Checkpoint":
        return cls(
            stage_id=payload["stage_id"],
            status=payload["status"],
            recorded_at=payload["recorded_at"],
        )
