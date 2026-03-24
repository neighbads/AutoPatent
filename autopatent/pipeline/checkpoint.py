"""Checkpoint persistence helpers for AutoPatent pipelines."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

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

    def latest(self) -> Optional[Checkpoint]:
        """Return the most recent checkpoint or None if none exist."""

        history = self._read_history()
        try:
            last = history[-1]
        except IndexError:
            return None
        return Checkpoint.from_dict(last)

    def _read_history(self) -> List[dict[str, str]]:
        if not self._history_file.exists():
            return []
        content = self._history_file.read_text()
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Malformed checkpoint history at {self._history_file}: {exc}"
            ) from exc
        if not isinstance(data, list):
            raise ValueError(
                f"Checkpoint history at {self._history_file} must be a list, got {type(data).__name__}"
            )
        for index, entry in enumerate(data):
            if not isinstance(entry, dict):
                raise ValueError(
                    f"Checkpoint entry at index {index} in {self._history_file} must be a dict: {type(entry).__name__}"
                )
        return data

    def _write_history(self, history: List[dict[str, str]]) -> None:
        payload = json.dumps(history, ensure_ascii=False, indent=2)
        temp_file = self._history_file.with_name(f"{self._history_file.name}.tmp")
        temp_file.write_text(payload)
        temp_file.replace(self._history_file)
