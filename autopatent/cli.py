from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

import typer
from typer import _typing
import typer.utils

_original_get_type_hints = _typing.get_type_hints


def _safe_get_type_hints(func: Callable[..., Any]) -> Dict[str, Any]:
    try:
        return _original_get_type_hints(func)
    except TypeError:
        annotations: Dict[str, Any] = {}
        for name, annotation in getattr(func, "__annotations__", {}).items():
            if isinstance(annotation, str) and annotation.endswith(" | None"):
                base = annotation[: -6].strip()
                if base == "str":
                    annotations[name] = Optional[str]
                    continue
                if base == "Path":
                    annotations[name] = Optional[Path]
                    continue
            annotations[name] = annotation
        return annotations


_typing.get_type_hints = _safe_get_type_hints
typer.utils.get_type_hints = _safe_get_type_hints

app = typer.Typer()


@app.command()
def run(topic: str | None = None, input_doc: Path | None = None) -> None:
    """Placeholder run command."""
    if not topic and not input_doc:
        raise typer.BadParameter("需要至少一个输入")
