from typer.testing import CliRunner

from autopatent.cli import app


def test_run_requires_topic_or_input_doc():
    runner = CliRunner()
    result = runner.invoke(app, [])

    assert result.exit_code != 0
    assert "需要至少一个输入" in result.stdout
