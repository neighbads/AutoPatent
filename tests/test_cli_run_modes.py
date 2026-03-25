import pytest
from typer.testing import CliRunner

from autopatent.cli import app


@pytest.fixture
def runner():
    return CliRunner()


def test_run_requires_topic_or_input_doc(runner):
    result = runner.invoke(app, ["run"])

    assert result.exit_code != 0
    assert "需要至少一个输入" in result.output


def test_run_accepts_topic(runner, tmp_path):
    result = runner.invoke(
        app,
        ["run", "--topic", "专利", "--output", str(tmp_path / "run-output"), "--auto-approve"],
    )

    assert result.exit_code == 0


def test_run_interactive_mode_accepts_choose_input(runner, tmp_path):
    result = runner.invoke(
        app,
        ["run", "--topic", "交互模式专利", "--output", str(tmp_path / "run-output")],
        input="choose 2\n",
    )

    assert result.exit_code == 0
