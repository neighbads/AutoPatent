from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from autopatent.pipeline import StageContext, StageResult


def _stub_resources() -> List[Dict[str, str]]:
    # The endpoints are intentionally "stubs" for deterministic tests.
    return [
        {"source": "CNIPA", "endpoint": "https://pss-system.cnipa.gov.cn"},
        {"source": "WIPO_PATENTSCOPE", "endpoint": "https://patentscope.wipo.int"},
        {"source": "GOOGLE_PATENTS", "endpoint": "https://patents.google.com"},
    ]


@dataclass
class PriorArtScanStage:
    """Stage 02: Produce prior-art resource stubs for follow-up scanning.

    Minimal behavior:
    - Emits a fixed list of sources/endpoints (no network).
    - Stores it in `ctx.metadata['prior_art_resources']`.
    """

    stage_id: str = "STAGE_02"
    requires: list[str] = None  # type: ignore[assignment]
    produces: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.requires is None:
            self.requires = ["direction_candidates"]
        if self.produces is None:
            self.produces = ["prior_art_resources"]

    def run(self, ctx: StageContext) -> StageResult:
        candidates = ctx.metadata.get("direction_candidates", [])
        if candidates is not None and not isinstance(candidates, list):
            raise ValueError("ctx.metadata['direction_candidates'] must be a list if present")

        resources = _stub_resources()
        ctx.metadata["prior_art_resources"] = resources

        result = StageResult(produces=list(self.produces))
        result.outputs = {"prior_art_resources": resources}
        return result

