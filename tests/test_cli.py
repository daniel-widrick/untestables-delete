from click.testing import CliRunner
from datetime import datetime, timedelta
from untestables.cli import main
from untestables.github.client import Repository
from sqlalchemy.orm import Session

def test_cli_default_values():
    runner = CliRunner()
    result = runner.invoke(main)
    assert result.exit_code == 0
    assert "Searching for repositories with 5 to 1000 stars" in result.output

def test_cli_rescan_days():
    runner = CliRunner()
    result = runner.invoke(main, ['--rescan-days', '30'])
    assert result.exit_code == 0
    assert "Will re-scan repositories last scanned more than 30 days ago" in result.output

def test_cli_force_rescan():
    runner = CliRunner()
    result = runner.invoke(main, ['--force-rescan'])
    assert result.exit_code == 0
    assert "Force re-scan enabled" in result.output

def test_cli_combined_options():
    runner = CliRunner()
    result = runner.invoke(main, [
        '--min-stars', '10',
        '--max-stars', '50',
        '--rescan-days', '7',
        '--force-rescan'
    ])
    assert result.exit_code == 0
    assert "Starting repository search with 10 to 50 stars" in result.output
    assert "Will re-scan repositories last scanned more than 7 days ago" in result.output
    assert "Force re-scan enabled" in result.output

def test_cli_custom_values():
    runner = CliRunner()
    result = runner.invoke(main, [
        '--min-stars', '10',
        '--max-stars', '500',
    ])
    assert result.exit_code == 0
    assert "Searching for repositories with 10 to 500 stars" in result.output 