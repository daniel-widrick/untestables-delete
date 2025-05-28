"""Tests for the GitHub client implementation."""
import os
import pytest
from unittest.mock import patch, MagicMock
from untestables.github.client import GitHubClient

@pytest.fixture
def mock_github():
    """Fixture to mock the GitHub client."""
    with patch("untestables.github.client.Github") as mock:
        yield mock

@pytest.fixture
def mock_env_vars():
    """Fixture to set up mock environment variables."""
    with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}):
        yield

def test_init_with_token():
    """Test initialization with a token."""
    client = GitHubClient(token="test_token")
    assert client.token == "test_token"

def test_init_with_env_var(mock_env_vars):
    """Test initialization with environment variable."""
    client = GitHubClient()
    assert client.token == "test_token"

def test_init_without_token():
    """Test initialization without token raises error."""
    with pytest.raises(ValueError, match="GitHub token is required"):
        GitHubClient()

def test_get_rate_limit(mock_github):
    """Test getting rate limit information."""
    # Setup mock
    mock_rate_limit = MagicMock()
    mock_rate_limit.core.remaining = 100
    mock_rate_limit.core.limit = 5000
    mock_rate_limit.core.reset = "2024-01-01T00:00:00Z"
    mock_github.return_value.get_rate_limit.return_value = mock_rate_limit

    # Test
    client = GitHubClient(token="test_token")
    rate_limit = client.get_rate_limit()

    assert rate_limit["remaining"] == 100
    assert rate_limit["limit"] == 5000
    assert rate_limit["reset_time"] == "2024-01-01T00:00:00Z"

def test_test_connection_success(mock_github):
    """Test successful connection test."""
    mock_github.return_value.get_user.return_value = MagicMock()
    
    client = GitHubClient(token="test_token")
    assert client.test_connection() is True

def test_test_connection_failure(mock_github):
    """Test failed connection test."""
    from github.GithubException import GithubException
    mock_github.return_value.get_user.side_effect = GithubException(401, "Bad credentials")
    
    client = GitHubClient(token="test_token")
    assert client.test_connection() is False 