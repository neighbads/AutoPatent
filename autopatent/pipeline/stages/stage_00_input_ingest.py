from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from autopatent.pipeline import StageContext, StageResult


@dataclass
class InputIngestStage:
    """Stage 00: Normalize user inputs into ctx.metadata.

    Minimal behavior:
    - If `topic` exists, keep it.
    - If `input_doc` exists and is a Path/str, persist its string form.
    """

    stage_id: str = "STAGE_00"
    requires: list[str] = None  # type: ignore[assignment]
    produces: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.requires is None:
            self.requires = []
        if self.produces is None:
            self.produces = ["topic", "input_doc"]

    def run(self, ctx: StageContext) -> StageResult:
        topic = ctx.metadata.get("topic")
        if topic is not None and not isinstance(topic, str):
            ctx.metadata["topic"] = str(topic)

        input_doc: Optional[Any] = ctx.metadata.get("input_doc")
        if isinstance(input_doc, Path):
            ctx.metadata["input_doc"] = str(input_doc)
        elif input_doc is not None and not isinstance(input_doc, str):
            ctx.metadata["input_doc"] = str(input_doc)

        result = StageResult(produces=list(self.produces))
        result.outputs = {k: ctx.metadata.get(k) for k in self.produces}
        return result

