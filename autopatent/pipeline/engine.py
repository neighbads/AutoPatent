from __future__ import annotations

from typing import Iterable

from autopatent.pipeline.contracts import Stage, StageContext


class PipelineEngine:
    def __init__(self, stages: Iterable[Stage]) -> None:
        self._stages = list(stages)

    def run(self, context: StageContext) -> None:
        for stage in self._stages:
            missing = [k for k in getattr(stage, "requires", []) if k not in context.metadata]
            if missing:
                sid = getattr(stage, "stage_id", stage.__class__.__name__)
                raise ValueError(f"Stage {sid} missing required inputs: {missing}")

            result = stage.run(context)
            # Merge declared outputs into ctx.metadata so later stages can rely on them
            # even if a stage does not mutate ctx.metadata directly.
            if result is not None:
                outputs = getattr(result, "outputs", None)
                if isinstance(outputs, dict) and outputs:
                    context.metadata.update(outputs)
