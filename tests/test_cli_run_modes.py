import pytest
from typer.testing import CliRunner

from autopatent.cli import app


@pytest.fixture
def runner():
    return CliRunner()


def test_run_requires_topic_or_input_doc(runner):
    result = runner.invoke(app, ["run"])

    assert result.exit_code != 0
    assert "需要至少一个输入" in result.stdout
