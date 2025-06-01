"""GitHub API client implementation."""
import os
import time
import fnmatch
from functools import wraps
from typing import Optional, Callable, Any, List
from github import Github, RateLimitExceededException, GithubException, UnknownObjectException
from github.Repository import Repository as GHRepository
from dotenv import load_dotenv
from sqlalchemy import create_engine, desc, func, distinct
from sqlalchemy.orm import sessionmaker, Session
from common.logging import LoggingManager
from datetime import datetime, timedelta, timezone

from .models import Base, Repository as DBRepository

# Configure logger for this module using the application's logging setup
# This will be a child of the main 'app' logger if 'app' is configured first.
logger = LoggingManager.get_logger('app.github_client')


class RateLimitExceeded(Exception):
    """Exception raised when the GitHub API rate limit is exceeded."""
    pass


class APILimitError(Exception):
    """Custom exception for GitHub API rate limit errors."""
    def __init__(self, message: str, reset_time_unix: Optional[int] = None, reset_time_datetime: Optional[datetime] = None):
        super().__init__(message)
        self.reset_time_unix = reset_time_unix
        if reset_time_datetime and reset_time_datetime.tzinfo is None:
            self.reset_time_datetime = reset_time_datetime.replace(tzinfo=timezone.utc)
        else:
            self.reset_time_datetime = reset_time_datetime

        if reset_time_unix and not reset_time_datetime:
            self.reset_time_datetime = datetime.fromtimestamp(reset_time_unix, tz=timezone.utc)
        elif reset_time_datetime and not reset_time_unix:
            self.reset_time_unix = int(reset_time_datetime.timestamp())


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator to retry a function on failure.

    Args:
        max_retries: Maximum number of retry attempts.
        delay: Initial delay between retries in seconds.
        backoff: Multiplier for delay after each retry.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except (GithubException,
                        RateLimitExceededException) as e:  # RateLimitExceededException is from PyGithub
                    last_exception = e
                    logger.warning(f"Attempt {attempt + 1}/{max_retries + 1} failed: {str(e)}")
                    if isinstance(e, RateLimitExceededException):  # PyGithub's exception
                        # For rate limits, wait until reset
                        # PyGithub's RateLimitExceededException has a data attribute which contains headers
                        # The reset time is typically available in e.data.get('X-RateLimit-Reset') or similar
                        # However, the PyGithub object itself provides a get_rate_limit().core.reset
                        # It's better to use the client's get_rate_limit method if possible,
                        # but here we react to an exception that just occurred.
                        # The RateLimitExceededException from PyGithub doesn't directly give a datetime reset object.
                        # We'll rely on the higher-level check_rate_limit or the decorator's delay for now.
                        # A more sophisticated handling might involve trying to parse e.data or calling client.get_rate_limit()
                        # For simplicity, this retry decorator will use its timed backoff for RateLimitExceededException too.
                        # A specific check could be:
                        # gh_client_instance = args[0] # Assuming 'self' is the first arg for methods
                        # if hasattr(gh_client_instance, 'client'):
                        #    reset_time_unix = gh_client_instance.client.get_rate_limit().core.reset.timestamp()
                        #    wait_time = max(reset_time_unix - time.time(), 0)
                        #    logger.info(f"GitHub API Rate limit likely exceeded. Waiting {wait_time:.2f} seconds until reset.")
                        #    time.sleep(wait_time)
                        #    current_delay = 0 # Reset delay as we've waited for the API reset
                        # else:
                        #    logger.warning("Could not determine GitHub client instance to check rate limit reset time.")
                        pass  # Default backoff will apply. For more specific rate limit waiting, it's handled in check_rate_limit

                    if attempt < max_retries:
                        logger.info(f"Retrying in {current_delay:.2f} seconds...")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed. Last error: {str(e)}")
                        raise last_exception  # Re-raise the last caught exception
            return None  # Should not be reached if max_retries >= 0, as func is called or exception raised

        return wrapper

    return decorator


class GitHubClient:
    """Client for interacting with the GitHub API."""

    def __init__(self, token: Optional[str] = None, db_url: Optional[str] = None, load_env: bool = True):
        """Initialize the GitHub client.

        Args:
            token: GitHub personal access token. If not provided, will try to load from GITHUB_TOKEN env var.
            db_url: Database URL. If not provided, will try to load from DATABASE_URL env var.
            load_env: Whether to load environment variables from .env file (default: True).
        """
        if load_env:
            load_dotenv()
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            logger.error("GitHub token not found in environment variables")
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN environment variable or pass token directly.")

        logger.info("Initializing GitHub client")
        self.gh = Github(self.token, per_page=100)  # PyGithub client, explicitly set per_page
        self.db_url = db_url or os.getenv("DATABASE_URL")
        if not self.db_url:
            logger.error("Database URL not found in environment variables")
            raise ValueError("DATABASE_URL environment variable not set and no fallback provided.")

        logger.info("Initializing database connection")
        self.engine = create_engine(self.db_url)
        Base.metadata.create_all(self.engine)  # Creates tables if they don't exist
        self.Session = sessionmaker(bind=self.engine)
        logger.info("GitHub client initialization complete")

    @retry_on_failure()
    def get_rate_limit(self) -> dict:
        """Get the current rate limit information.

        Returns:
            dict: Rate limit information including remaining requests and reset time.
        """
        logger.debug("Fetching GitHub API rate limit")
        rate_limit = self.gh.get_rate_limit()  # PyGithub's rate limit object
        info = {
            "remaining": rate_limit.core.remaining,
            "limit": rate_limit.core.limit,
            "reset_time": rate_limit.core.reset  # This is a datetime object
        }
        logger.debug(f"Rate limit info: {info}")
        return info

    @retry_on_failure()
    def test_connection(self) -> bool:
        """Test the GitHub API connection.

        Returns:
            bool: True if connection is successful, False otherwise.
        """
        logger.info("Testing GitHub API connection")
        try:
            self.gh.get_user()  # A simple call to verify authentication and connection
            logger.info("GitHub API connection test successful")
            return True
        except GithubException as e:
            logger.error(f"GitHub API connection test failed: {str(e)}")
            return False

    def check_rate_limit(self, min_remaining: int = 10):
        """Check the current rate limit and raise or warn if low/exceeded.
        Args:
            min_remaining: Minimum number of requests that should remain before warning/raising.
        Raises:
            RateLimitExceeded: If the rate limit is exceeded (custom exception).
        Returns:
            dict: The current rate limit info.
        """
        info = self.get_rate_limit()
        if info["remaining"] <= 0:
            reset_time_str = info['reset_time'].strftime('%Y-%m-%d %H:%M:%S UTC')
            logger.error(f"Rate limit exceeded. Resets at {reset_time_str}")
            # Raise your custom exception. The retry decorator might catch PyGithub's RateLimitExceededException.
            raise RateLimitExceeded(
                f"GitHub API rate limit exceeded. Resets at {reset_time_str}. Please try again later.")
        elif info["remaining"] < min_remaining:
            reset_time_str = info['reset_time'].strftime('%Y-%m-%d %H:%M:%S UTC')
            logger.warning(f"Rate limit is low: {info['remaining']} remaining, resets at {reset_time_str}")
        return info

    @retry_on_failure()
    def get_paginated_results(self, query: str, per_page: int = 30) -> list:
        logger.info(f"Executing search query: {query}. PyGithub client default per_page is used.")
        results = []
        MAX_RESULTS = 1000 # GitHub API limit for search results

        self.check_rate_limit() # Initial check
        try:
            # The per_page argument to search_repositories can sometimes be finicky or ignored
            # if the client itself has a per_page default. We set it on client init.
            paginated_list_object = self.gh.search_repositories(query=query)
            logger.debug(f"Obtained PaginatedList for query: {query}")

            # Iterate directly over the PaginatedList. PyGithub handles pagination.
            # We only need to cap the total number of results collected.
            for i, repo in enumerate(paginated_list_object):
                if len(results) >= MAX_RESULTS:
                    logger.info(f"Reached GitHub API search result limit of {MAX_RESULTS}. Halting collection.")
                    break
                results.append(repo)
                if (i + 1) % 100 == 0: # Log progress every 100 repos fetched by the iterator
                    logger.debug(f"Collected {len(results)} repositories so far for query '{query}'...")

        except GithubException as e:
            logger.error(f"Error during search for query '{query}': {e}")
            # Depending on the error, you might want to raise it or handle it gracefully.
            # For instance, RateLimitExceededException is already handled by the decorator.
            if not isinstance(e, RateLimitExceededException): # Avoid re-raising if decorator handles it
                raise

        logger.info(f"Total results collected for query '{query}': {len(results)} (capped at {MAX_RESULTS} if applicable)")
        return results


    @retry_on_failure()
    def filter_repositories(self, language: str = "Python", min_stars: int = 0, max_stars: int = None, # max_stars can be None
                            keywords: list = None, max_results: int = 1000) -> List[GHRepository]: # Type hint is github.Repository.Repository
        """Filter repositories based on specified criteria using paginated search."""
        query_parts = []
        if language:
            query_parts.append(f"language:{language}")

        if max_stars is None:
            if min_stars == 0: # No star filter effectively
                pass # Or some very large upper bound if API requires, but usually not specifying is fine
            else:
                query_parts.append(f"stars:>={min_stars}")
        elif min_stars == 0 and max_stars == 0: # Special case: 0 stars only
             query_parts.append(f"stars:0")
        else: # min_stars, max_stars, or both are set (and max_stars is not None)
            query_parts.append(f"stars:{min_stars}..{max_stars}")

        if keywords:
            query_parts.extend([f'"{keyword}"' for keyword in keywords])

        query = " ".join(query_parts)
        logger.info(f"Constructed repository search query: {query}")

        # Use the paginated search method, removing end_time_iso
        return self.search_repositories_paginated(query=query, max_results=max_results)

    @retry_on_failure()
    def get_repository_metadata(self, repo_name: str, language: str = "python") -> dict:
        """Retrieve metadata for a given repository, including language."""
        logger.info(f"Fetching metadata for repository: {repo_name}")
        repo = self.gh.get_repo(repo_name)  # repo_name should be "owner/repo"
        metadata = {
            "name": repo.name,  # Just the repo name
            "description": repo.description,
            "star_count": repo.stargazers_count,
            "url": repo.html_url,  # Full HTML URL
            "language": getattr(repo, "language", language) or language,  # Primary language
            "last_push_time": repo.pushed_at,
            "last_metadata_update_time": repo.updated_at,
            "creation_time": repo.created_at
            # "full_name": repo.full_name # "owner/repo" - good to store if not using URL as unique ID
        }
        logger.debug(f"Repository metadata: {metadata}")
        return metadata

    def store_repository_metadata(self, metadata: dict, missing: dict) -> None:
        """Store repository metadata in the database, including language."""
        # This function assumes 'metadata' contains a 'name' key which is the simple repo name.
        # If your DB needs to be unique on 'owner/repo', ensure 'name' reflects that or use a different field.
        logger.info(
            f"Storing metadata for repository: {metadata.get('full_name', metadata.get('name'))}")  # Log full_name if available
        session = self.Session()
        try:
            # Consider how to handle existing repositories. Update or skip?
            # If 'name' in the DB is just repo.name, then ownerA/repoX and ownerB/repoX could clash
            # if not handled. If url is unique, that's better.
            # repo_to_store = Repository(**metadata) # This will fail if metadata has extra keys like 'full_name' not in model init

            repo_data_for_model = {
                "name": metadata["name"],
                "description": metadata["description"],
                "star_count": metadata["star_count"],
                "url": metadata["url"],
                "language": metadata["language"],
                "missing_test_directories": missing.get("test_directories", False),
                "missing_test_files": missing.get("test_files", False),
                "missing_test_config_files": missing.get("test_config_files", False),
                "missing_cicd_configs": missing.get("cicd_configs", False),
                "missing_readme_mentions": missing.get("readme_mentions", False),
                "last_scanned_at": datetime.utcnow(),
                "last_push_time": metadata.get("last_push_time"),
                "last_metadata_update_time": metadata.get("last_metadata_update_time"),
                "creation_time": metadata.get("creation_time")
            }

            # Check if repo already exists by URL (which should be unique)
            existing_repo = session.query(DBRepository).filter_by(url=metadata["url"]).first()
            if existing_repo:
                logger.debug(f"Repository {metadata['url']} already exists. Updating.")
                for key, value in repo_data_for_model.items():
                    setattr(existing_repo, key, value)
                repo_to_store = existing_repo
            else:
                logger.debug(f"New repository: {metadata['url']}. Creating.")
                repo_to_store = DBRepository(**repo_data_for_model)
                session.add(repo_to_store)

            session.commit()
            logger.debug(f"Stored/Updated repository data: {metadata.get('full_name', metadata['name'])}")
        except Exception as e:
            logger.error(f"Error storing repository metadata for {metadata.get('url')}: {e}")
            session.rollback()
            raise
        finally:
            session.close()

    @retry_on_failure()
    def check_test_directories(self, repo_name: str) -> bool:  # repo_name is "owner/repo"
        """Check for the existence of common unit test directories in a given repository."""
        logger.info(f"Checking test directories for repository: {repo_name}")
        repo = self.gh.get_repo(repo_name)
        test_dirs = ["tests", "test", "testfiles", "unittests"]  # Added more common names
        # Common top-level or src-level test directories
        paths_to_check = [""]  # Root
        try:
            # Check if 'src' directory exists at root, if so, add "src/" to paths to check for tests
            root_contents = repo.get_contents("")
            if any(content.name == "src" and content.type == "dir" for content in root_contents):
                paths_to_check.append("src")
        except GithubException as e:
            logger.warning(f"Could not list root contents for {repo_name} to check for 'src' dir: {e}")
            # Continue without checking src, or handle as an error if src is crucial

        for path_prefix in paths_to_check:
            try:
                contents = repo.get_contents(path_prefix)
                for content_item in contents:
                    if content_item.type == "dir" and content_item.name.lower() in test_dirs:
                        logger.debug(
                            f"Found test directory '{content_item.name}' in '{path_prefix if path_prefix else 'root'}' for {repo_name}")
                        return True
            except GithubException as e:  # e.g., 404 if path_prefix (like 'src') doesn't exist
                logger.debug(
                    f"Error or path not found checking '{path_prefix}' for test directories in {repo_name}: {str(e)}")
                continue  # Try next path_prefix or return False if all fail

        logger.debug(f"No common test directories found for {repo_name} in checked paths.")
        return False

    @retry_on_failure()
    def check_test_files(self, repo_name: str) -> bool:  # repo_name is "owner/repo"
        """Check for common unit test files in a repository."""
        logger.info(f"Checking test files for repository: {repo_name}")
        repo = self.gh.get_repo(repo_name)
        # Patterns for fnmatch
        test_file_patterns = ["test_*.py", "*_test.py", "tests.py", "test.py"]
        common_test_paths = ["", "tests", "test", "src", "src/tests", "src/test"]

        for path_prefix in common_test_paths:
            try:
                contents = repo.get_contents(path_prefix)
                for content_item in contents:
                    if content_item.type == "file":
                        file_name_lower = content_item.name.lower()
                        for pattern in test_file_patterns:
                            if fnmatch.fnmatchcase(file_name_lower, pattern): # Use fnmatchcase for case-sensitive matching on case-insensitive filesystems if needed, or fnmatch
                                logger.debug(f"Found test file '{content_item.name}' in '{path_prefix or 'root'}' matching pattern '{pattern}' for {repo_name}")
                                return True
            except GithubException as e:
                logger.debug(f"Error or path not found '{path_prefix}' while checking for test files in {repo_name}: {str(e)}")
                continue

        logger.debug(f"No common test files found for {repo_name} in checked paths.")
        return False

    @retry_on_failure()
    def check_test_config_files(self, repo_name: str) -> bool:  # repo_name is "owner/repo"
        """Scan for configuration files related to testing in the root directory."""
        logger.info(f"Checking test config files for repository: {repo_name}")
        repo = self.gh.get_repo(repo_name)
        config_files = ["pytest.ini", "tox.ini", "nose.cfg", ".coveragerc", "setup.cfg",
                        "pyproject.toml"]  # setup.cfg/pyproject.toml can contain pytest/coverage config
        try:
            contents = repo.get_contents("")  # Check only root for these usually
            for content_item in contents:
                if content_item.type == "file" and content_item.name.lower() in config_files:
                    # For pyproject.toml or setup.cfg, could add a check for specific sections like [tool.pytest.ini_options]
                    logger.debug(f"Test config file '{content_item.name}' found for {repo_name}")
                    return True
            logger.debug(f"No common test config files found in root for {repo_name}")
            return False
        except GithubException as e:
            logger.error(f"Error checking test config files for {repo_name}: {str(e)}")
            return False  # False if error, as we couldn't confirm existence

    @retry_on_failure()
    def check_readme_for_test_frameworks(self, repo_name: str) -> bool:  # repo_name is "owner/repo"
        """Search the repository README for mentions of testing frameworks."""
        logger.info(f"Checking README for test frameworks in repository: {repo_name}")
        repo = self.gh.get_repo(repo_name)
        try:
            readme = repo.get_readme()
            readme_content = readme.decoded_content.decode("utf-8", errors="ignore").lower()  # Added errors='ignore'
            test_frameworks = ["pytest", "unittest", "nose", "tox", "doctest", "behave", "lettuce",
                               "robot framework"]  # Expanded list
            if any(framework in readme_content for framework in test_frameworks):
                logger.debug(f"Test framework mentions found in README for {repo_name}")
                return True
            logger.debug(f"No common test framework mentions found in README for {repo_name}")
            return False
        except GithubException as e:  # README might not exist (404) or other errors
            if hasattr(e, 'status') and e.status == 404:
                logger.debug(f"No README file found for {repo_name}.")
            else:
                logger.error(f"Error checking README for {repo_name}: {str(e)}")
            return False

    @retry_on_failure()
    def check_cicd_configs(self, repo_name: str) -> bool:  # repo_name is "owner/repo"
        """Detect CI/CD configurations related to testing in the repository."""
        logger.info(f"Checking CI/CD configs for repository: {repo_name}")
        repo = self.gh.get_repo(repo_name)
        # Patterns for CI/CD config files/directories
        # GitHub Actions workflows are in .github/workflows/ and can be any .yml or .yaml file
        # For others, it's usually a specific file name at the root.

        # Check for GitHub Actions workflow directory
        try:
            contents = repo.get_contents(".github/workflows")
            if any(content.name.lower().endswith((".yml", ".yaml")) for content in contents if content.type == 'file'):
                logger.debug(f"Found GitHub Actions workflow files in .github/workflows/ for {repo_name}")
                return True
        except GithubException as e:  # Path .github/workflows not found
            logger.debug(f"No .github/workflows directory or error accessing it for {repo_name}: {str(e)}")
            pass  # Continue to check other CI/CD files

        # Check for other common CI/CD files at root
        cicd_root_files = [".travis.yml", "Jenkinsfile", ".gitlab-ci.yml", "circle.yml", ".circleci/config.yml",
                           "appveyor.yml", "azure-pipelines.yml", "bitbucket-pipelines.yml"]
        try:
            root_contents = repo.get_contents("")
            for content_item in root_contents:
                if content_item.type == "file" and content_item.name in cicd_root_files:
                    logger.debug(f"Found CI/CD config file '{content_item.name}' in root for {repo_name}")
                    return True
                # Special case for .circleci/config.yml
                if content_item.type == "dir" and content_item.name == ".circleci":
                    try:
                        circleci_contents = repo.get_contents(".circleci")
                        if any(c.name == "config.yml" and c.type == "file" for c in circleci_contents):
                            logger.debug(f"Found .circleci/config.yml for {repo_name}")
                            return True
                    except GithubException:
                        pass  # couldn't read .circleci contents
        except GithubException as e:
            logger.error(f"Error checking root CI/CD config files for {repo_name}: {str(e)}")
            # Fall through to return False if no CI/CD found or error on root listing

        logger.debug(f"No common CI/CD configs found for {repo_name}")
        return False

    def flag_missing_tests(self, repo_name: str) -> dict:  # repo_name is "owner/repo"
        """Flag repositories where unit testing frameworks and configurations are absent."""
        logger.info(f"Checking for missing test components in repository: {repo_name}")
        # Note: These checks are independent. "Not having a test_directory" doesn't mean "no test files",
        # as test files could be at root. The current logic reflects this.
        missing = {
            "test_directories": not self.check_test_directories(repo_name),
            "test_files": not self.check_test_files(repo_name),
            "test_config_files": not self.check_test_config_files(repo_name),
            "cicd_configs": not self.check_cicd_configs(repo_name),
            "readme_mentions": not self.check_readme_for_test_frameworks(repo_name)
        }
        logger.debug(f"Missing test components for {repo_name}: {missing}")
        return missing

    def store_missing_tests(self, repo_name: str, missing: dict) -> None:  # repo_name is "owner/repo"
        """Store information about missing test components for a repository in the database.
        This method assumes the repository metadata ALREADY EXISTS from a prior call to store_repository_metadata.
        It updates the 'missing' flags for an existing repository entry.
        """
        logger.info(f"Attempting to store missing test information for repository: {repo_name}")
        session = self.Session()
        try:
            # Assuming repo_name is "owner/repo". We need to find it by URL or a unique full_name.
            # The 'Repository' table's 'name' field is just the repo name, not unique across owners.
            # Best to query by URL if that's unique.

            # First, try to get the repo object to construct the URL, or require URL to be passed
            # This is a bit redundant if store_repository_metadata was just called.
            # This function might be better merged or called directly by the main script after metadata is stored.

            # Let's assume the repo's URL is the unique identifier here.
            # We'd need the URL. If we only have "owner/repo", we can construct a potential URL.
            # github_repo_obj = self.gh.get_repo(repo_name) # API call
            # repo_url = github_repo_obj.html_url

            # Alternative: The calling script should manage this, passing the DB ID or unique URL.
            # For now, if this method is called, we assume the repo *should* be in the DB.
            # Let's assume the main script fetched metadata, got its URL, then calls this.
            # However, the original code tries to get metadata IF NOT FOUND.

            # Simplified: Assume the calling script ensures `repo_name` can be used to find an existing DB record.
            # This part is tricky if `repo_name` is "owner/repo" and your DB `Repository.name` is just "repo".
            # Let's refine to update based on URL, which should be unique.
            # The `get_repository_metadata` would be the source of the URL.

            # This method's original logic:
            # repo_name_only = repo_name.split('/')[-1]
            # repo_db_entry = session.query(Repository).filter_by(name=repo_name_only).first()
            # This is problematic if multiple owners have repos with the same name.

            # Safer approach: Use a more unique identifier if possible (like URL).
            # If you must use repo_name ("owner/repo") and your DB stores only the simple name,
            # you need to be careful.

            # For the purpose of this function as "update flags for a repo known by its full name":
            # It should ideally receive the database ID or a unique key like URL.
            # If `repo_name` is "owner/repo", and you stored `url` (which includes owner/repo):

            # Let's assume the calling function passes the URL that was stored.
            # For now, I'll keep the original logic but log a warning about its potential ambiguity.

            repo_name_only = repo_name.split('/')[-1]
            logger.warning(
                f"Querying repository in DB by simple name '{repo_name_only}' for update. This might be ambiguous if multiple owners have repos with this name. Consider using URL or DB ID for updates.")

            repo_db_entry = session.query(DBRepository).filter(DBRepository.name == repo_name_only,
                                                             DBRepository.url.like(f"%/{repo_name}")).first()

            if not repo_db_entry:
                logger.warning(
                    f"Repository '{repo_name}' (name: {repo_name_only}) not found in database to update missing flags. Attempting to fetch and create.")
                # This implies store_repository_metadata should have been called first.
                # If we allow creation here, it duplicates store_repository_metadata's role.
                # For now, let's assume it MUST exist.
                # metadata = self.get_repository_metadata(repo_name) # API call
                # repo_db_entry = Repository(**metadata) # This would create a new one
                # session.add(repo_db_entry)
                logger.error(
                    f"Repository {repo_name} not found in DB. Flags cannot be updated. Ensure metadata is stored first.")
                return  # Or raise an error

            # Update the record with missing test information
            repo_db_entry.missing_test_directories = missing.get("test_directories",
                                                                 repo_db_entry.missing_test_directories)
            repo_db_entry.missing_test_files = missing.get("test_files", repo_db_entry.missing_test_files)
            repo_db_entry.missing_test_config_files = missing.get("test_config_files",
                                                                  repo_db_entry.missing_test_config_files)
            repo_db_entry.missing_cicd_configs = missing.get("cicd_configs", repo_db_entry.missing_cicd_configs)
            repo_db_entry.missing_readme_mentions = missing.get("readme_mentions",
                                                                repo_db_entry.missing_readme_mentions)
            repo_db_entry.last_scanned_at = datetime.utcnow()  # Update scan time

            logger.debug(f"Updating repo {repo_name} (DB name: {repo_db_entry.name}) with missing test info: {missing}")
            session.commit()
        except Exception as e:
            logger.error(f"Error storing missing test information for {repo_name}: {e}")
            session.rollback()
            raise
        finally:
            session.close()

    def get_recently_scanned_repos(self, days: Optional[int] = None) -> list:
        """Get a list of repository URLs that have been scanned within the specified time period.
        Args:
            days: Number of days to look back. If None, returns all scanned repository URLs.
        Returns:
            list: List of repository URLs (e.g., 'https://github.com/owner/repo') that have been scanned.
                  The calling script will need to match based on this.
        """
        logger.info(f"Getting recently scanned repository URLs (days={days})")
        session = self.Session()
        try:
            # Returns a list of URLs for the calling script to use for exclusion.
            # Using URL as it's more unique than just 'name'.
            query = session.query(DBRepository.url)

            if days is not None:
                # This is the behavior if `days` is specified by the calling script (e.g., untestables)
                # It makes "recently scanned" mean scanned in the last X days.
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                query = query.filter(DBRepository.last_scanned_at >= cutoff_date)
            # If 'days' is None (as in the original log), all repo URLs from the DB are returned.
            # The calling script then uses this list to skip processing.

            repo_urls = [repo_url_tuple[0] for repo_url_tuple in query.all()]
            logger.debug(f"Found {len(repo_urls)} repository URLs matching criteria (days={days}).")
            return repo_urls
        except Exception as e:
            logger.error(f"Error getting recently scanned repos: {e}")
            return []  # Return empty list on error
        finally:
            session.close()

    def get_processed_star_counts(self) -> list[int]:
        """Get a sorted list of distinct star counts from successfully scanned repositories."""
        logger.info("Fetching processed star counts from the database.")
        session = self.Session()
        try:
            query = session.query(DBRepository.star_count).distinct().order_by(DBRepository.star_count)
            logger.info(f"Constructed query: {query}") # Using f-string for consistency

            logger.debug("Attempting to execute query.all() for processed star counts...")
            results = query.all() # This is the suspected hanging point
            logger.debug(f"query.all() executed. Number of results (tuples): {len(results)}")

            star_counts = [result[0] for result in results]
            logger.debug(f"Found {len(star_counts)} distinct processed star counts after extracting from tuples.")
            return star_counts
        except Exception as e:
            logger.error(f"Error fetching processed star counts: {e}", exc_info=True)
            return [] 
        finally:
            logger.debug("Closing session in get_processed_star_counts.")
            session.close()

    def get_rate_limit_info(self) -> dict:
        """Gets current rate limit status for core and search."""
        try:
            rate_limits = self.gh.get_rate_limit()
            core_limits = rate_limits.core
            search_limits = rate_limits.search

            # Ensure datetimes are timezone-aware (UTC)
            core_reset_dt = core_limits.reset.replace(tzinfo=timezone.utc) if core_limits.reset.tzinfo is None else core_limits.reset
            search_reset_dt = search_limits.reset.replace(tzinfo=timezone.utc) if search_limits.reset.tzinfo is None else search_limits.reset

            return {
                "core": {
                    "limit": core_limits.limit,
                    "remaining": core_limits.remaining,
                    "reset_time_unix": int(core_reset_dt.timestamp()),
                    "reset_time_datetime": core_reset_dt
                },
                "search": {
                    "limit": search_limits.limit,
                    "remaining": search_limits.remaining,
                    "reset_time_unix": int(search_reset_dt.timestamp()),
                    "reset_time_datetime": search_reset_dt
                }
            }
        except Exception as e:
            logger.error(f"Could not retrieve rate limit: {e}", exc_info=True)
            return {
                "core": {"limit": 0, "remaining": 0, "reset_time_unix": None, "reset_time_datetime": None},
                "search": {"limit": 0, "remaining": 0, "reset_time_unix": None, "reset_time_datetime": None}
            }

    def search_repositories_paginated(self, query: str, max_results: int = 1000) -> List[GHRepository]: # Type hint is github.Repository.Repository
        """
        Searches repositories using paginated results from PyGithub, respecting GitHub's result cap (1000).
        Args:
            query (str): The GitHub search query string.
            max_results (int): The maximum number of repositories to return.
                               Capped at 1000 due to GitHub API limitations for search.
        Returns:
            List[GHRepository]: A list of repository objects.
        """
        logger.info(f"Executing paginated repository search: '{query}'. Max results: {max_results}.") # Removed End time from log

        effective_max_results = min(max_results, 1000)
        if max_results > 1000:
            logger.warning(f"Requested max_results {max_results} exceeds GitHub API limit of 1000. Will fetch at most 1000.")

        results: List[GHRepository] = []
        # Removed end_time_dt parsing and related logic

        try:
            paginated_list = self.gh.search_repositories(query=query)
            logger.debug(f"PyGithub PaginatedList obtained for query: {query}")

            for i, repo in enumerate(paginated_list):
                # Removed time check: if end_time_dt and datetime.now(timezone.utc) >= end_time_dt:

                results.append(repo)
                if len(results) >= effective_max_results:
                    logger.info(f"Reached effective_max_results ({effective_max_results}). Stopping repository collection.")
                    break

                if (i + 1) % 50 == 0:
                    logger.debug(f"Collected {len(results)} repositories so far for query '{query}'...")

            logger.info(f"Finished collecting repositories for query '{query}'. Total collected: {len(results)}.")

        except RateLimitExceededException as e: # PyGithub's exception
            # This exception should ideally be caught by the @retry_on_failure decorator.
            # If it reaches here, it means retries failed or decorator isn't applied to a calling method.
            rl = self.gh.get_rate_limit().search # Check search-specific limit
            reset_time = rl.reset.replace(tzinfo=timezone.utc)
            logger.error(f"GitHub Search API rate limit exceeded during search: '{query}'. Limit will reset at {reset_time}. Error: {e}")
            # Raise the custom APILimitError so AnalyzerService can see it
            raise APILimitError(message=f"Search API rate limit hit: {e}", reset_time_datetime=reset_time) from e
        except GithubException as e:
            logger.error(f"An unexpected GitHub API error occurred during search '{query}': {e}", exc_info=True)
            # Depending on policy, either raise a custom error or the original GithubException
            raise # Re-raise the original error to be handled by caller or retry decorator
        except Exception as e:
            logger.error(f"A non-GitHub error occurred during repository search '{query}': {e}", exc_info=True)
            raise # Re-raise

        return results
