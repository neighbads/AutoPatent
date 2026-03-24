from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import typer
import typing
from typer import _typing
import typer.utils

_original_get_type_hints = typing.get_type_hints


def _safe_get_type_hints(func, globalns=None, localns=None):
    try:
        return _original_get_type_hints(func, globalns=globalns, localns=localns)
    except TypeError:
        annotations: Dict[str, object] = {}
        for name, annotation in getattr(func, "__annotations__", {}).items():
            if isinstance(annotation, str) and annotation.endswith(" | None"):
                base = annotation[: -6].strip()
                if base == "str":
                    annotations[name] = Optional[str]
                elif base == "Path":
                    annotations[name] = Optional[Path]
                else:
                    annotations[name] = annotation
            else:
                annotations[name] = annotation
        return annotations


typing.get_type_hints = _safe_get_type_hints
_typing.get_type_hints = _safe_get_type_hints
typer.utils.get_type_hints = _safe_get_type_hints

app = typer.Typer()

app = typer.Typer()


@app.callback(invoke_without_command=True)
def main() -> None:
    """Root CLI stub."""
    pass


@app.command()
def run(
    topic: str | None = None,
    input_doc: Path | None = None,
) -> None:
    """Placeholder run command."""
    if not topic and not input_doc:
        raise typer.BadParameter("需要至少一个输入")
