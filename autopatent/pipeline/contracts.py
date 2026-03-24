from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class StageContext:
    work_dir: Path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StageResult:
    produces: list[str] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)


class Stage(Protocol):
    stage_id: str
    requires: list[str]
    produces: list[str]

    def run(self, ctx: StageContext) -> StageResult: ...
