import typer
from typing import Optional

app = typer.Typer()


@app.command(name="run")
def run(
    topic: Optional[str] = typer.Option(None),
    input_doc: Optional[str] = typer.Option(None),
) -> None:
    """Placeholder run command."""
    if not topic and not input_doc:
        raise typer.BadParameter("需要至少一个输入")
