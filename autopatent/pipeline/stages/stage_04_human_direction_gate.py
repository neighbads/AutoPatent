from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from autopatent.pipeline import StageContext, StageResult


def _coerce_candidate_list(ctx: StageContext) -> List[Dict[str, Any]]:
    raw = ctx.metadata.get("direction_candidates", [])
    if not isinstance(raw, list):
        raise ValueError("ctx.metadata['direction_candidates'] must be a list")
    candidates: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("direction_candidates entries must be dicts")
        # Copy so we can mutate locally while keeping ctx as the source of truth.
        candidates.append(dict(item))
    return candidates


def _is_weak(candidate: Dict[str, Any], threshold: float) -> bool:
    score = candidate.get("score")
    if isinstance(score, (int, float)):
        return float(score) < threshold
    quality = candidate.get("quality")
    if isinstance(quality, str):
        return quality.lower() in ("weak", "low", "poor")
    return True


def _expand_candidate(candidate: Dict[str, Any], attempt: int) -> None:
    # Deterministic "expansion": enrich summary and bump score slightly.
    summary = str(candidate.get("summary", "")).strip()
    title = str(candidate.get("title", "")).strip()
    candidate["summary"] = (
        f"{summary} [expanded:{attempt}] {title}".strip()
        if summary or title
        else f"[expanded:{attempt}]"
    )
    score = candidate.get("score")
    base = float(score) if isinstance(score, (int, float)) else 0.0
    # Bump by 0.15 per attempt, capped at 0.95
    candidate["score"] = min(0.95, base + 0.15)
    candidate["expanded"] = True


def _write_decision(work_dir: Path, payload: Dict[str, Any]) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    path = work_dir / "direction_gate_decision.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


@dataclass
class HumanDirectionGateStage:
    stage_id: str = "STAGE_04"
    requires: list[str] = field(default_factory=lambda: ["direction_candidates"])
    produces: list[str] = field(
        default_factory=lambda: ["selected_direction_id", "direction_gate_decision_path"]
    )

    # Behavior knobs kept as attributes so tests can override if needed.
    weak_score_threshold: float = 0.5
    auto_expand_max_retries: int = 3

    def run(self, ctx: StageContext) -> StageResult:
        candidates = _coerce_candidate_list(ctx)

        # Auto-expand weak candidates before human prompt, with a global retry cap.
        auto_retries = 0
        while auto_retries < self.auto_expand_max_retries and any(
            _is_weak(c, self.weak_score_threshold) for c in candidates
        ):
            auto_retries += 1
            for c in candidates:
                if _is_weak(c, self.weak_score_threshold):
                    _expand_candidate(c, attempt=auto_retries)

        # Persist the expanded candidate set back into ctx as the "current view".
        ctx.metadata["direction_candidates"] = candidates
        ctx.metadata["direction_gate_auto_expand_retries"] = auto_retries

        if ctx.metadata.get("non_interactive") is True:
            selected = ctx.metadata.get("selected_direction_id")
            if selected is None:
                raise ValueError("non_interactive mode requires selected_direction_id")
            selected_id = str(selected)
            if not self._has_candidate(candidates, selected_id):
                raise ValueError(f"selected_direction_id not found: {selected_id}")
            decision = {"selected_direction_id": selected_id}
            decision_path = _write_decision(ctx.work_dir, decision)
            ctx.metadata["selected_direction_id"] = selected_id
            ctx.metadata["direction_gate_decision_path"] = str(decision_path)
            return StageResult(
                produces=list(self.produces),
                outputs={
                    "selected_direction_id": selected_id,
                    "direction_gate_decision_path": str(decision_path),
                },
            )

        manual_retries = 0
        self._print_candidates(candidates)

        while True:
            raw = input(
                "Direction gate (choose <id> | expand [id|all] | merge <a> <b> | drop <id> | quit): "
            )
            cmd, args = self._parse(raw)
            if cmd is None:
                continue

            if cmd == "choose":
                selected = args[0]
                if not self._has_candidate(candidates, selected):
                    continue
                decision = {"selected_direction_id": selected}
                decision_path = _write_decision(ctx.work_dir, decision)
                ctx.metadata["selected_direction_id"] = selected
                ctx.metadata["direction_gate_decision_path"] = str(decision_path)

                return StageResult(
                    produces=list(self.produces),
                    outputs={
                        "selected_direction_id": selected,
                        "direction_gate_decision_path": str(decision_path),
                    },
                )

            if cmd == "quit":
                ctx.metadata["selected_direction_id"] = None
                ctx.metadata["direction_gate_decision_path"] = None
                return StageResult(
                    produces=list(self.produces),
                    outputs={
                        "selected_direction_id": None,
                        "direction_gate_decision_path": None,
                    },
                )

            if cmd == "drop":
                target = args[0]
                candidates = [c for c in candidates if str(c.get("id")) != target]
                ctx.metadata["direction_candidates"] = candidates
                self._print_candidates(candidates)
                continue

            if cmd == "expand":
                target = args[0] if args else "all"
                if target == "all":
                    for c in candidates:
                        if _is_weak(c, self.weak_score_threshold):
                            _expand_candidate(c, attempt=auto_retries + manual_retries + 1)
                    manual_retries += 1
                else:
                    c = self._find_candidate(candidates, target)
                    if c is None:
                        continue
                    _expand_candidate(c, attempt=auto_retries + manual_retries + 1)
                    manual_retries += 1
                ctx.metadata["direction_candidates"] = candidates
                ctx.metadata["direction_gate_manual_expand_retries"] = manual_retries
                self._print_candidates(candidates)
                continue

            if cmd == "merge":
                a, b = args
                ca = self._find_candidate(candidates, a)
                cb = self._find_candidate(candidates, b)
                if ca is None or cb is None:
                    continue
                merged = self._merge_candidates(ca, cb, candidates)
                candidates.append(merged)
                ctx.metadata["direction_candidates"] = candidates
                self._print_candidates(candidates)
                continue

    def _print_candidates(self, candidates: List[Dict[str, Any]]) -> None:
        print("Candidate directions:")
        for item in candidates:
            cid = str(item.get("id", "")).strip() or "-"
            title = str(item.get("title", "")).strip() or "(untitled)"
            summary = str(item.get("summary", "")).strip()
            score = item.get("score")
            score_text = f"{float(score):.3f}" if isinstance(score, (int, float)) else "n/a"
            quality = str(item.get("quality", "")).strip() or "n/a"
            if summary:
                print(f"  [{cid}] {title} | score={score_text} | quality={quality}")
                print(f"       {summary}")
            else:
                print(f"  [{cid}] {title} | score={score_text} | quality={quality}")

    def _parse(self, raw: str) -> Tuple[Optional[str], List[str]]:
        parts = raw.strip().split()
        if not parts:
            return None, []
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd == "choose" and len(args) == 1:
            return cmd, args
        if cmd == "drop" and len(args) == 1:
            return cmd, args
        if cmd == "merge" and len(args) == 2:
            return cmd, args
        if cmd == "expand" and len(args) in (0, 1):
            if args and args[0].lower() == "all":
                return cmd, []
            return cmd, args
        if cmd == "quit" and not args:
            return cmd, []
        return None, []

    def _has_candidate(self, candidates: List[Dict[str, Any]], cid: str) -> bool:
        return self._find_candidate(candidates, cid) is not None

    def _find_candidate(
        self, candidates: List[Dict[str, Any]], cid: str
    ) -> Optional[Dict[str, Any]]:
        for c in candidates:
            if str(c.get("id")) == cid:
                return c
        return None

    def _merge_candidates(
        self,
        a: Dict[str, Any],
        b: Dict[str, Any],
        existing: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        # Deterministic merged id: "m<N>" where N is count of existing merged items + 1.
        merged_count = sum(
            1 for c in existing if isinstance(c.get("id"), str) and str(c["id"]).startswith("m")
        )
        mid = f"m{merged_count + 1}"
        title = f"{a.get('title', '')} + {b.get('title', '')}".strip(" +")
        summary = f"Merged: {a.get('summary', '')} | {b.get('summary', '')}".strip()
        score_a = float(a.get("score", 0.0)) if isinstance(a.get("score"), (int, float)) else 0.0
        score_b = float(b.get("score", 0.0)) if isinstance(b.get("score"), (int, float)) else 0.0
        return {"id": mid, "title": title, "summary": summary, "score": max(score_a, score_b)}
