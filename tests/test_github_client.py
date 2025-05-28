"""Tests for the GitHub client implementation."""
import os
import pytest
from unittest.mock import patch, MagicMock, Mock
from untestables.github.client import GitHubClient, RateLimitExceeded, Repository, retry_on_failure
from sqlalchemy.orm import Session
from github.GithubException import GithubException, RateLimitExceededException
import time
from datetime import datetime, timedelta

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

def test_filter_repositories_with_criteria(mock_github):
    """Test that filter_repositories correctly filters repositories based on criteria."""
    mock_repos = [MagicMock(), MagicMock()]
    mock_github.return_value.search_repositories.side_effect = [mock_repos, []]
    client = GitHubClient(token="test_token")
    results = client.filter_repositories(language="python", min_stars=5, max_stars=1000, keywords=["test"])
    assert len(results) == 2
    assert results == mock_repos

def test_filter_repositories_no_matches(mock_github):
    """Test that filter_repositories handles no matching repositories gracefully."""
    mock_github.return_value.search_repositories.return_value = []
    client = GitHubClient(token="test_token")
    results = client.filter_repositories(language="python", min_stars=1000, max_stars=2000)
    assert len(results) == 0

def test_get_repository_metadata(mock_github):
    """Test that get_repository_metadata correctly extracts and returns repository metadata."""
    mock_repo = MagicMock()
    mock_repo.name = "test-repo"
    mock_repo.description = "A test repository"
    mock_repo.stargazers_count = 100
    mock_repo.html_url = "https://github.com/owner/test-repo"
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    metadata = client.get_repository_metadata("owner/test-repo")
    assert metadata["name"] == "test-repo"
    assert metadata["description"] == "A test repository"
    assert metadata["star_count"] == 100
    assert metadata["url"] == "https://github.com/owner/test-repo"

def test_get_repository_metadata_not_found(mock_github):
    """Test that get_repository_metadata handles repository not found gracefully."""
    mock_github.return_value.get_repo.side_effect = GithubException(404, "Not Found")
    client = GitHubClient(token="test_token")
    with pytest.raises(GithubException):
        client.get_repository_metadata("owner/nonexistent-repo")

def test_store_repository_metadata(mock_github):
    """Test that store_repository_metadata correctly stores data in the database."""
    client = GitHubClient(token="test_token", db_url="sqlite:///:memory:")
    metadata = {
        "name": "test-repo",
        "description": "A test repository",
        "star_count": 100,
        "url": "https://github.com/owner/test-repo"
    }
    missing = {
        "test_directories": False,
        "test_files": False,
        "test_config_files": False,
        "cicd_configs": False,
        "readme_mentions": False
    }
    client.store_repository_metadata(metadata, missing)
    session = Session(bind=client.engine)
    repo = session.query(Repository).filter_by(name="test-repo").first()
    assert repo is not None
    assert repo.description == "A test repository"
    assert repo.star_count == 100
    assert repo.url == "https://github.com/owner/test-repo"
    assert repo.missing_test_directories is False
    assert repo.missing_test_files is False
    assert repo.missing_test_config_files is False
    assert repo.missing_cicd_configs is False
    assert repo.missing_readme_mentions is False
    session.close()

def test_store_repository_metadata_updates_last_scanned_at(mock_github):
    """Test that store_repository_metadata updates the last_scanned_at timestamp."""
    client = GitHubClient(token="test_token", db_url="sqlite:///:memory:")
    metadata = {
        "name": "test-repo",
        "description": "A test repository",
        "star_count": 100,
        "url": "https://github.com/owner/test-repo"
    }
    missing = {
        "test_directories": False,
        "test_files": False,
        "test_config_files": False,
        "cicd_configs": False,
        "readme_mentions": False
    }
    
    # Store initial data
    client.store_repository_metadata(metadata, missing)
    
    # Get the stored record
    session = Session(bind=client.engine)
    repo = session.query(Repository).filter_by(name="test-repo").first()
    initial_timestamp = repo.last_scanned_at
    session.close()
    
    # Wait a moment to ensure timestamp difference
    time.sleep(1)
    
    # Update the record
    client.store_repository_metadata(metadata, missing)
    
    # Check that timestamp was updated
    session = Session(bind=client.engine)
    repo = session.query(Repository).filter_by(name="test-repo").first()
    assert repo.last_scanned_at > initial_timestamp
    session.close()

def test_check_test_directories_exists(mock_github):
    """Test that check_test_directories correctly identifies the presence of test directories."""
    mock_repo = MagicMock()
    mock_tests_dir = MagicMock()
    mock_tests_dir.name = "tests"
    mock_tests_dir.type = "dir"
    mock_src_dir = MagicMock()
    mock_src_dir.name = "src"
    mock_src_dir.type = "dir"
    mock_contents = [mock_tests_dir, mock_src_dir]
    mock_repo.get_contents.return_value = mock_contents
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    assert client.check_test_directories("owner/repo") is True
    mock_github.return_value.get_repo.assert_called_once_with("owner/repo")
    mock_repo.get_contents.assert_called_once_with("")

def test_check_test_directories_not_exists(mock_github):
    """Test that check_test_directories handles the absence of test directories gracefully."""
    mock_repo = MagicMock()
    mock_contents = [MagicMock(name="src", type="dir")]
    mock_repo.get_contents.return_value = mock_contents
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    assert client.check_test_directories("owner/repo") is False

def test_check_test_directories_root_tests(mock_github):
    """Test detection of 'tests/' at root."""
    mock_repo = MagicMock()
    mock_tests_dir = MagicMock()
    mock_tests_dir.name = "tests"
    mock_tests_dir.type = "dir"
    mock_contents = [mock_tests_dir]
    mock_repo.get_contents.return_value = mock_contents
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    assert client.check_test_directories("owner/repo") is True

def test_check_test_directories_root_test(mock_github):
    """Test detection of 'test/' at root."""
    mock_repo = MagicMock()
    mock_test_dir = MagicMock()
    mock_test_dir.name = "test"
    mock_test_dir.type = "dir"
    mock_contents = [mock_test_dir]
    mock_repo.get_contents.return_value = mock_contents
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    assert client.check_test_directories("owner/repo") is True

def test_check_test_directories_src_tests(mock_github):
    """Test detection of 'src/tests/' directory."""
    mock_repo = MagicMock()
    mock_src_dir = MagicMock()
    mock_src_dir.name = "src"
    mock_src_dir.type = "dir"
    mock_contents = [mock_src_dir]
    mock_tests_dir = MagicMock()
    mock_tests_dir.name = "tests"
    mock_tests_dir.type = "dir"
    mock_repo.get_contents.side_effect = [mock_contents, [mock_tests_dir]]
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    assert client.check_test_directories("owner/repo") is True

def test_check_test_directories_src_test(mock_github):
    """Test detection of 'src/test/' directory."""
    mock_repo = MagicMock()
    mock_src_dir = MagicMock()
    mock_src_dir.name = "src"
    mock_src_dir.type = "dir"
    mock_contents = [mock_src_dir]
    mock_test_dir = MagicMock()
    mock_test_dir.name = "test"
    mock_test_dir.type = "dir"
    mock_repo.get_contents.side_effect = [mock_contents, [mock_test_dir]]
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    assert client.check_test_directories("owner/repo") is True

def test_check_test_files_root(mock_github):
    """Test detection of test files at root."""
    mock_repo = MagicMock()
    mock_test_file = MagicMock()
    mock_test_file.name = "test_example.py"
    mock_test_file.type = "file"
    mock_contents = [mock_test_file]
    mock_repo.get_contents.return_value = mock_contents
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    assert client.check_test_files("owner/repo") is True

def test_check_test_files_src(mock_github):
    """Test detection of test files under src/."""
    mock_repo = MagicMock()
    mock_src_dir = MagicMock()
    mock_src_dir.name = "src"
    mock_src_dir.type = "dir"
    mock_contents = [mock_src_dir]
    mock_test_file = MagicMock()
    mock_test_file.name = "test_example.py"
    mock_test_file.type = "file"
    mock_repo.get_contents.side_effect = [mock_contents, [mock_test_file]]
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    assert client.check_test_files("owner/repo") is True

def test_check_test_files_test_dir(mock_github):
    """Test detection of test files under tests/ directory."""
    mock_repo = MagicMock()
    mock_tests_dir = MagicMock()
    mock_tests_dir.name = "tests"
    mock_tests_dir.type = "dir"
    mock_contents = [mock_tests_dir]
    mock_test_file = MagicMock()
    mock_test_file.name = "test_example.py"
    mock_test_file.type = "file"
    mock_repo.get_contents.side_effect = [mock_contents, [mock_test_file]]
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    assert client.check_test_files("owner/repo") is True

def test_check_test_config_files_exists(mock_github):
    """Test detection of test configuration files at root."""
    mock_repo = MagicMock()
    mock_config_file = MagicMock()
    mock_config_file.name = "pytest.ini"
    mock_config_file.type = "file"
    mock_contents = [mock_config_file]
    mock_repo.get_contents.return_value = mock_contents
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    assert client.check_test_config_files("owner/repo") is True

def test_check_test_config_files_not_exists(mock_github):
    """Test that check_test_config_files returns False when no config files exist."""
    mock_repo = MagicMock()
    mock_contents = [MagicMock(name="README.md", type="file")]
    mock_repo.get_contents.return_value = mock_contents
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    assert client.check_test_config_files("owner/repo") is False

def test_check_readme_for_test_frameworks_exists(mock_github):
    """Test detection of testing framework mentions in README."""
    mock_repo = MagicMock()
    mock_readme = MagicMock()
    mock_readme.decoded_content = b"This project uses pytest for testing."
    mock_repo.get_readme.return_value = mock_readme
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    assert client.check_readme_for_test_frameworks("owner/repo") is True

def test_check_readme_for_test_frameworks_not_exists(mock_github):
    """Test that check_readme_for_test_frameworks returns False when no frameworks are mentioned."""
    mock_repo = MagicMock()
    mock_readme = MagicMock()
    mock_readme.decoded_content = b"This project has no tests."
    mock_repo.get_readme.return_value = mock_readme
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    assert client.check_readme_for_test_frameworks("owner/repo") is False

def test_check_readme_for_test_frameworks_readme_not_found(mock_github):
    """Test that check_readme_for_test_frameworks returns False when README is not found."""
    mock_repo = MagicMock()
    mock_repo.get_readme.side_effect = GithubException(404, "Not Found")
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    assert client.check_readme_for_test_frameworks("owner/repo") is False

def test_check_cicd_configs_exists(mock_github):
    """Test detection of CI/CD configurations."""
    mock_repo = MagicMock()
    mock_github_actions = MagicMock()
    mock_github_actions.name = "test.yml"
    mock_github_actions.type = "file"
    mock_repo.get_contents.return_value = [mock_github_actions]
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    assert client.check_cicd_configs("owner/repo") is True

def test_check_cicd_configs_not_exists(mock_github):
    """Test that check_cicd_configs returns False when no CI/CD configurations exist."""
    mock_repo = MagicMock()
    mock_repo.get_contents.side_effect = GithubException(404, "Not Found")
    mock_github.return_value.get_repo.return_value = mock_repo
    client = GitHubClient(token="test_token")
    assert client.check_cicd_configs("owner/repo") is False

def test_flag_missing_tests_all_present(mock_github):
    """Test flagging when all test components are present."""
    mock_repo = MagicMock()
    # Directory and file mocks
    mock_tests_dir = MagicMock()
    mock_tests_dir.name = "tests"
    mock_tests_dir.type = "dir"
    mock_test_file = MagicMock()
    mock_test_file.name = "test_example.py"
    mock_test_file.type = "file"
    mock_config_file = MagicMock()
    mock_config_file.name = "pytest.ini"
    mock_config_file.type = "file"
    mock_cicd_file = MagicMock()
    mock_cicd_file.name = "test.yml"
    mock_cicd_file.type = "file"
    # README mock
    mock_readme = MagicMock()
    mock_readme.decoded_content = b"This project uses pytest for testing."

    def get_contents_side_effect(path=""):
        if path == "":
            return [mock_tests_dir, mock_test_file, mock_config_file, mock_cicd_file]
        elif path == "tests":
            return [mock_test_file]
        elif path == "src":
            return []
        elif path == "pytest.ini":
            return [mock_config_file]
        elif path == ".github/workflows/*.yml":
            return [mock_cicd_file]
        elif path == ".travis.yml":
            return []
        elif path == "Jenkinsfile":
            return []
        elif path == "teamcity.yml":
            return []
        else:
            raise GithubException(404, "Not Found")

    mock_repo.get_contents.side_effect = get_contents_side_effect
    mock_repo.get_readme.return_value = mock_readme
    mock_github.return_value.get_repo.return_value = mock_repo

    client = GitHubClient(token="test_token")
    missing = client.flag_missing_tests("owner/repo")
    assert not any(missing.values())

def test_flag_missing_tests_all_absent(mock_github):
    """Test flagging when all test components are absent."""
    mock_repo = MagicMock()
    mock_repo.get_contents.side_effect = GithubException(404, "Not Found")
    mock_repo.get_readme.side_effect = GithubException(404, "Not Found")
    mock_github.return_value.get_repo.return_value = mock_repo

    client = GitHubClient(token="test_token")
    missing = client.flag_missing_tests("owner/repo")
    assert all(missing.values())

def test_store_missing_tests_new_repo(mock_github):
    """Test storing missing test information for a new repository record."""
    mock_repo = MagicMock()
    mock_repo.name = "test-repo"
    mock_repo.description = "A test repository"
    mock_repo.stargazers_count = 100
    mock_repo.html_url = "https://github.com/owner/test-repo"
    mock_github.return_value.get_repo.return_value = mock_repo

    client = GitHubClient(token="test_token", db_url="sqlite:///:memory:")
    missing = {
        "test_directories": True,
        "test_files": False,
        "test_config_files": True,
        "cicd_configs": False,
        "readme_mentions": True
    }
    client.store_missing_tests("owner/test-repo", missing)

    session = Session(bind=client.engine)
    repo = session.query(Repository).filter_by(name="test-repo").first()
    assert repo is not None
    assert repo.missing_test_directories is True
    assert repo.missing_test_files is False
    assert repo.missing_test_config_files is True
    assert repo.missing_cicd_configs is False
    assert repo.missing_readme_mentions is True
    session.close()

def test_store_missing_tests_existing_repo(mock_github):
    """Test updating missing test information for an existing repository record."""
    mock_repo = MagicMock()
    mock_repo.name = "test-repo"
    mock_repo.description = "A test repository"
    mock_repo.stargazers_count = 100
    mock_repo.html_url = "https://github.com/owner/test-repo"
    mock_github.return_value.get_repo.return_value = mock_repo

    client = GitHubClient(token="test_token", db_url="sqlite:///:memory:")
    # First, create a record
    metadata = {
        "name": "test-repo",
        "description": "A test repository",
        "star_count": 100,
        "url": "https://github.com/owner/test-repo"
    }
    missing = {
        "test_directories": False,
        "test_files": False,
        "test_config_files": False,
        "cicd_configs": False,
        "readme_mentions": False
    }
    client.store_repository_metadata(metadata, missing)

    # Now update the missing test information
    missing = {
        "test_directories": False,
        "test_files": True,
        "test_config_files": False,
        "cicd_configs": True,
        "readme_mentions": False
    }
    client.store_missing_tests("owner/test-repo", missing)

    session = Session(bind=client.engine)
    repo = session.query(Repository).filter_by(name="test-repo").first()
    assert repo is not None
    assert repo.missing_test_directories is False
    assert repo.missing_test_files is True
    assert repo.missing_test_config_files is False
    assert repo.missing_cicd_configs is True
    assert repo.missing_readme_mentions is False
    session.close()

def test_retry_on_failure_success():
    """Test that retry decorator returns result on success."""
    mock_func = Mock(return_value="success")
    decorated = retry_on_failure()(mock_func)
    assert decorated() == "success"
    assert mock_func.call_count == 1

def test_retry_on_failure_retries():
    """Test that retry decorator retries on failure."""
    mock_func = Mock(side_effect=[GithubException(404, "Not found"), "success"])
    decorated = retry_on_failure(max_retries=1, delay=0.1)(mock_func)
    assert decorated() == "success"
    assert mock_func.call_count == 2

@pytest.mark.skip(reason="Difficult to mock RateLimitExceededException with reset attribute in PyGithub.")
def test_retry_on_failure_rate_limit():
    pass

def test_retry_on_failure_max_retries():
    """Test that retry decorator raises after max retries."""
    mock_func = Mock(side_effect=GithubException(404, "Not found"))
    decorated = retry_on_failure(max_retries=2, delay=0.1)(mock_func)
    with pytest.raises(GithubException):
        decorated()
    assert mock_func.call_count == 3

def test_client_retry_on_api_calls(mock_github):
    """Test that client methods use retry decorator."""
    client = GitHubClient(token="test_token", db_url="sqlite:///:memory:")
    
    # Test get_rate_limit
    mock_github.return_value.get_rate_limit.side_effect = [
        GithubException(404, "Not found"),
        Mock(core=Mock(remaining=100, limit=100, reset=0))
    ]
    result = client.get_rate_limit()
    assert result["remaining"] == 100
    assert mock_github.return_value.get_rate_limit.call_count == 2

    # Test get_repository_metadata with only exceptions to test retry logic
    def always_raise_github_exception(*args, **kwargs):
        raise GithubException(404, "Not found")
    mock_github.return_value.get_repo.side_effect = always_raise_github_exception
    with pytest.raises(GithubException):
        client.get_repository_metadata("test/repo")
    assert mock_github.return_value.get_repo.call_count == 4  # 1 initial + 3 retries 

def test_get_recently_scanned_repos(mock_github):
    """Test that get_recently_scanned_repos returns correct repositories."""
    client = GitHubClient(token="test_token", db_url="sqlite:///:memory:")
    
    # Create some test repositories with different scan times
    session = Session(bind=client.engine)
    now = datetime.utcnow()
    
    # Recent scan (1 day ago)
    repo1 = Repository(
        name="repo1",
        description="Test repo 1",
        star_count=100,
        url="https://github.com/owner/repo1",
        missing_test_directories=False,
        missing_test_files=False,
        missing_test_config_files=False,
        missing_cicd_configs=False,
        missing_readme_mentions=False,
        last_scanned_at=now - timedelta(days=1)
    )
    
    # Old scan (31 days ago)
    repo2 = Repository(
        name="repo2",
        description="Test repo 2",
        star_count=200,
        url="https://github.com/owner/repo2",
        missing_test_directories=True,
        missing_test_files=True,
        missing_test_config_files=False,
        missing_cicd_configs=False,
        missing_readme_mentions=False,
        last_scanned_at=now - timedelta(days=31)
    )
    
    session.add_all([repo1, repo2])
    session.commit()
    session.close()
    
    # Test getting all scanned repos
    all_repos = client.get_recently_scanned_repos()
    assert len(all_repos) == 2
    assert "repo1" in all_repos
    assert "repo2" in all_repos
    
    # Test getting repos scanned in last 30 days
    recent_repos = client.get_recently_scanned_repos(days=30)
    assert len(recent_repos) == 1
    assert "repo1" in recent_repos
    assert "repo2" not in recent_repos
    
    # Test getting repos scanned in last 40 days
    older_repos = client.get_recently_scanned_repos(days=40)
    assert len(older_repos) == 2
    assert "repo1" in older_repos
    assert "repo2" in older_repos 