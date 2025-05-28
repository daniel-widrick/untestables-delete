from click.testing import CliRunner
from untestables.cli import main

def test_cli_default_values():
    runner = CliRunner()
    result = runner.invoke(main)
    assert result.exit_code == 0
    assert "Searching for repositories with 5 to 1000 stars" in result.output

def test_cli_custom_values():
    runner = CliRunner()
    result = runner.invoke(main, [
        '--min-stars', '10',
        '--max-stars', '500',
    ])
    assert result.exit_code == 0
    assert "Searching for repositories with 10 to 500 stars" in result.output 