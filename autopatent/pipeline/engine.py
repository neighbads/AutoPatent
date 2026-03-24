from __future__ import annotations

from typing import Iterable

from autopatent.pipeline.contracts import Stage, StageContext


class PipelineEngine:
    def __init__(self, stages: Iterable[Stage]) -> None:
        self._stages = list(stages)

    def run(self, context: StageContext) -> None:
        for stage in self._stages:
            stage.run(context)
