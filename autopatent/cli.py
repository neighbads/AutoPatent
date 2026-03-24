from pathlib import Path
from typing import Optional

import typer

app = typer.Typer()


@app.callback()
def main() -> None:
    """Root CLI stub."""
    pass


@app.command()
def run(
    topic: Optional[str] = None,
    input_doc: Optional[Path] = None,
    output: Optional[Path] = None,
    code_dir: Optional[Path] = None,
    resume: bool = False,
    template: Optional[str] = None,
) -> None:
    """Placeholder run command."""
    if not topic and not input_doc:
        raise typer.BadParameter("需要至少一个输入", param_hint="--topic/--input-doc")

    # Keep behavior minimal for MVP skeleton while supporting documented CLI shape.
    _selected_template = template or "cn_invention_default"
    _ = (output, code_dir, resume, _selected_template)


if __name__ == "__main__":
    app()
