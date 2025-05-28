from click.testing import CliRunner
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import pytest
from untestables.cli import main
from untestables.github.client import Repository
from sqlalchemy.orm import Session

@pytest.fixture
def mock_github_client():
    """Fixture to mock the GitHub client."""
    with patch('untestables.cli.GitHubClient') as mock:
        client_instance = MagicMock()
        # Mock the filter_repositories method to return a list of mock repos
        mock_repo = MagicMock()
        mock_repo.full_name = "test/repo"
        mock_repo.name = "repo"
        client_instance.filter_repositories.return_value = [mock_repo]
        # Mock the get_repository_metadata method
        client_instance.get_repository_metadata.return_value = {
            "name": "repo",
            "description": "Test repo",
            "star_count": 100,
            "url": "https://github.com/test/repo"
        }
        # Mock the flag_missing_tests method
        client_instance.flag_missing_tests.return_value = {
            "test_directories": False,
            "test_files": False,
            "test_config_files": False,
            "cicd_configs": False,
            "readme_mentions": False
        }
        # Mock the get_recently_scanned_repos method
        client_instance.get_recently_scanned_repos.return_value = []
        # Mock the get_rate_limit method
        client_instance.get_rate_limit.return_value = {
            "remaining": 100,
            "limit": 5000,
            "reset_time": "2024-01-01T00:00:00Z"
        }
        mock.return_value = client_instance
        yield mock

@pytest.fixture
def mock_env_vars():
    """Fixture to set up mock environment variables."""
    with patch.dict('os.environ', {
        'GITHUB_TOKEN': 'test_token',
        'DATABASE_URL': 'sqlite:///:memory:'
    }):
        yield

def test_cli_default_values(mock_github_client, mock_env_vars):
    """Test CLI with default values."""
    runner = CliRunner()
    result = runner.invoke(main)
    assert result.exit_code == 0
    assert "Starting repository search with 5 to 1000 stars" in result.output

def test_cli_rescan_days(mock_github_client, mock_env_vars):
    """Test CLI with rescan days option."""
    runner = CliRunner()
    result = runner.invoke(main, ['--rescan-days', '30'])
    assert result.exit_code == 0
    assert "Will re-scan repositories last scanned more than 30 days ago" in result.output

def test_cli_force_rescan(mock_github_client, mock_env_vars):
    """Test CLI with force rescan option."""
    runner = CliRunner()
    result = runner.invoke(main, ['--force-rescan'])
    assert result.exit_code == 0
    assert "Force re-scan enabled" in result.output

def test_cli_combined_options(mock_github_client, mock_env_vars):
    """Test CLI with multiple options."""
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

def test_cli_custom_values(mock_github_client, mock_env_vars):
    """Test CLI with custom star values."""
    runner = CliRunner()
    result = runner.invoke(main, [
        '--min-stars', '10',
        '--max-stars', '500',
    ])
    assert result.exit_code == 0
    assert "Starting repository search with 10 to 500 stars" in result.output 