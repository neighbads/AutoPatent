from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from autopatent.pipeline import StageContext, StageResult


def _score_candidate(candidate: Dict[str, Any], prior_art_resources: List[Dict[str, Any]]) -> float:
    # Deterministic heuristic score in [0, 1].
    title = str(candidate.get("title", "") or "")
    summary = str(candidate.get("summary", "") or "")
    base = 0.2
    base += min(0.4, len(title) / 80.0)
    base += min(0.3, len(summary) / 160.0)
    base += 0.1 if prior_art_resources else 0.0
    return max(0.0, min(1.0, base))


@dataclass
class DirectionScoringStage:
    """Stage 03: Score direction candidates with a simple deterministic heuristic."""

    stage_id: str = "STAGE_03"
    requires: list[str] = field(
        default_factory=lambda: ["direction_candidates", "prior_art_resources"]
    )
    produces: list[str] = field(
        default_factory=lambda: ["direction_candidates", "direction_candidates_scored"]
    )

    weak_score_threshold: float = 0.5

    def run(self, ctx: StageContext) -> StageResult:
        raw = ctx.metadata.get("direction_candidates", [])
        if not isinstance(raw, list):
            raise ValueError("ctx.metadata['direction_candidates'] must be a list")
        prior = ctx.metadata.get("prior_art_resources", [])
        if prior is None:
            prior = []
        if not isinstance(prior, list):
            raise ValueError("ctx.metadata['prior_art_resources'] must be a list if present")

        scored: List[Dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("direction_candidates entries must be dicts")
            c = dict(item)
            c["score"] = _score_candidate(c, prior)
            c["quality"] = "weak" if float(c["score"]) < self.weak_score_threshold else "ok"
            scored.append(c)

        ctx.metadata["direction_candidates"] = scored
        ctx.metadata["direction_candidates_scored"] = scored

        result = StageResult(produces=list(self.produces))
        result.outputs = {"direction_candidates_scored": scored}
        return result
