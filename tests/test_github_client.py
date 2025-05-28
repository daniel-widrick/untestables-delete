"""Tests for the GitHub client implementation."""
import os
import pytest
from unittest.mock import patch, MagicMock
from untestables.github.client import GitHubClient, RateLimitExceeded

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

def test_check_rate_limit_exceeded(mock_github):
    """Test that RateLimitExceeded is raised when rate limit is 0."""
    mock_rate_limit = MagicMock()
    mock_rate_limit.core.remaining = 0
    mock_rate_limit.core.limit = 5000
    mock_rate_limit.core.reset = "2024-01-01T00:00:00Z"
    mock_github.return_value.get_rate_limit.return_value = mock_rate_limit
    client = GitHubClient(token="test_token")
    with pytest.raises(RateLimitExceeded):
        client.check_rate_limit()

def test_check_rate_limit_warns_on_low(monkeypatch, mock_github, capsys):
    """Test that a warning is printed when rate limit is low."""
    mock_rate_limit = MagicMock()
    mock_rate_limit.core.remaining = 5
    mock_rate_limit.core.limit = 5000
    mock_rate_limit.core.reset = "2024-01-01T00:00:00Z"
    mock_github.return_value.get_rate_limit.return_value = mock_rate_limit
    client = GitHubClient(token="test_token")
    client.check_rate_limit(min_remaining=10)
    captured = capsys.readouterr()
    assert "Warning: GitHub API rate limit is low" in captured.out

def test_check_rate_limit_ok(mock_github):
    """Test that no warning or error is raised when rate limit is sufficient."""
    mock_rate_limit = MagicMock()
    mock_rate_limit.core.remaining = 100
    mock_rate_limit.core.limit = 5000
    mock_rate_limit.core.reset = "2024-01-01T00:00:00Z"
    mock_github.return_value.get_rate_limit.return_value = mock_rate_limit
    client = GitHubClient(token="test_token")
    info = client.check_rate_limit(min_remaining=10)
    assert info["remaining"] == 100

def test_get_paginated_results_multiple_pages(mock_github):
    """Test that get_paginated_results correctly retrieves and combines results from multiple pages."""
    # Mock responses for two pages
    mock_page1 = [MagicMock(), MagicMock()]
    mock_page2 = [MagicMock()]
    mock_github.return_value.search_repositories.side_effect = [mock_page1, mock_page2, []]
    client = GitHubClient(token="test_token")
    results = client.get_paginated_results("test query")
    assert len(results) == 3
    assert results == mock_page1 + mock_page2

def test_get_paginated_results_empty(mock_github):
    """Test that get_paginated_results handles empty results gracefully."""
    mock_github.return_value.search_repositories.return_value = []
    client = GitHubClient(token="test_token")
    results = client.get_paginated_results("test query")
    assert len(results) == 0

def test_get_paginated_results_single_page(mock_github):
    """Test that get_paginated_results handles a single page of results correctly."""
    mock_page = [MagicMock(), MagicMock()]
    mock_github.return_value.search_repositories.side_effect = [mock_page, []]
    client = GitHubClient(token="test_token")
    results = client.get_paginated_results("test query")
    assert len(results) == 2
    assert results == mock_page 