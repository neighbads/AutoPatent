import pytest
from typer.testing import CliRunner

from autopatent.cli import app


class RunAwareCliRunner(CliRunner):
    def invoke(self, command, args=None, **kwargs):
        args = list(args or [])
        if args and args[0] == "run":
            args.pop(0)
        return super().invoke(command, args, **kwargs)


@pytest.fixture
def runner():
    return RunAwareCliRunner()


def test_run_requires_topic_or_input_doc(runner):
    result = runner.invoke(app, ["run"])

    assert result.exit_code != 0
    assert "需要至少一个输入" in result.stdout


def test_run_accepts_topic(runner):
    result = runner.invoke(app, ["run", "--topic", "专利"])

    assert result.exit_code == 0
