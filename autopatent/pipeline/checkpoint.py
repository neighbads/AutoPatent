"""Checkpoint persistence helpers for AutoPatent pipelines."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

from autopatent.models import Checkpoint

_HISTORY_FILENAME = "checkpoint_history.json"


class CheckpointStore:
    """Stores and retrieves staged checkpoint metadata."""

    def __init__(self, state_path: Path) -> None:
        self._state_path = Path(state_path)
        self._state_path.mkdir(parents=True, exist_ok=True)
        self._history_file = self._state_path / _HISTORY_FILENAME

    def save(self, stage_id: str, status: str) -> None:
        """Persist a new checkpoint entry."""

        history = list(self._read_history())
        checkpoint = Checkpoint(
            stage_id=stage_id,
            status=status,
            recorded_at=datetime.utcnow().isoformat(),
        )
        history.append(checkpoint.to_dict())
        self._write_history(history)

    def latest(self) -> Checkpoint | None:
        """Return the most recent checkpoint or None if none exist."""

        history = self._read_history()
        try:
            last = history[-1]
        except IndexError:
            return None
        return Checkpoint.from_dict(last)

    def _read_history(self) -> list[dict[str, str]]:
        if not self._history_file.exists():
            return []
        try:
            return json.loads(self._history_file.read_text())
        except json.JSONDecodeError:
            return []

    def _write_history(self, history: Iterable[dict[str, str]]) -> None:
        self._history_file.write_text(
            json.dumps(list(history), ensure_ascii=False, indent=2)
        )
