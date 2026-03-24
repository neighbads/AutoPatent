from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

app = typer.Typer()


@app.callback(invoke_without_command=True)
def main() -> None:
    """Root CLI stub."""
    pass


@app.command()
def run(
    topic: Optional[str] = None,
    input_doc: Optional[Path] = None,
) -> None:
    """Placeholder run command."""
    if not topic and not input_doc:
        raise typer.BadParameter("需要至少一个输入")
