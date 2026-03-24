from __future__ import annotations

from pathlib import Path

from typing import Optional

import typer

app = typer.Typer()
run_app = typer.Typer(invoke_without_command=True)


@run_app.callback()
def run(topic: str | None = None, input_doc: Path | None = None) -> None:
    """Placeholder run command."""
    if not topic and not input_doc:
        raise typer.BadParameter("需要至少一个输入")


app.add_typer(run_app, name="run")


run.__annotations__ = {
    "topic": Optional[str],
    "input_doc": Optional[Path],
    "return": None,
}
