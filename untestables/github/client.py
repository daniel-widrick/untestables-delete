"""GitHub API client implementation."""
import os
import time
from functools import wraps
from typing import Optional, Callable, Any
from github import Github
from github.GithubException import GithubException, RateLimitExceededException
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from common.logging import setup_logging, get_logger
from datetime import datetime, timedelta

# Set up logging for this module
setup_logging()
logger = get_logger()

class RateLimitExceeded(Exception):
    """Exception raised when the GitHub API rate limit is exceeded."""
    pass

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
                except (GithubException, RateLimitExceededException) as e:
                    last_exception = e
                    logger.warning(f"Attempt {attempt + 1}/{max_retries + 1} failed: {str(e)}")
                    if isinstance(e, RateLimitExceededException):
                        # For rate limits, wait until reset
                        reset_time = e.reset
                        wait_time = max(reset_time - time.time(), 0)
                        if wait_time > 0:
                            logger.info(f"Rate limit exceeded. Waiting {wait_time:.2f} seconds until reset.")
                            time.sleep(wait_time)
                            continue
                    if attempt < max_retries:
                        logger.info(f"Retrying in {current_delay:.2f} seconds...")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed. Last error: {str(e)}")
                        raise last_exception
            return None
        return wrapper
    return decorator

Base = declarative_base()

class Repository(Base):
    __tablename__ = 'repositories'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    star_count = Column(Integer, nullable=False)
    url = Column(String(255), nullable=False)
    missing_test_directories = Column(Boolean, nullable=False)
    missing_test_files = Column(Boolean, nullable=False)
    missing_test_config_files = Column(Boolean, nullable=False)
    missing_cicd_configs = Column(Boolean, nullable=False)
    missing_readme_mentions = Column(Boolean, nullable=False)
    last_scanned_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    language = Column(String(50), nullable=True)

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
        self.client = Github(self.token)
        self.db_url = db_url or os.getenv("DATABASE_URL")
        if not self.db_url:
            logger.error("Database URL not found in environment variables")
            raise ValueError("DATABASE_URL environment variable not set and no fallback provided.")
        
        logger.info("Initializing database connection")
        self.engine = create_engine(self.db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        logger.info("GitHub client initialization complete")
    
    @retry_on_failure()
    def get_rate_limit(self) -> dict:
        """Get the current rate limit information.
        
        Returns:
            dict: Rate limit information including remaining requests and reset time.
        """
        logger.debug("Fetching GitHub API rate limit")
        rate_limit = self.client.get_rate_limit()
        info = {
            "remaining": rate_limit.core.remaining,
            "limit": rate_limit.core.limit,
            "reset_time": rate_limit.core.reset
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
            # Make a simple API call to test the connection
            self.client.get_user()
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
            RateLimitExceeded: If the rate limit is exceeded.
        Returns:
            dict: The current rate limit info.
        """
        info = self.get_rate_limit()
        if info["remaining"] <= 0:
            logger.error(f"Rate limit exceeded. Resets at {info['reset_time']}")
            raise RateLimitExceeded(f"GitHub API rate limit exceeded. Resets at {info['reset_time']}. Please try again later.")
        elif info["remaining"] < min_remaining:
            logger.warning(f"Rate limit is low: {info['remaining']} remaining, resets at {info['reset_time']}")
        return info 

    @retry_on_failure()
    def get_paginated_results(self, query: str) -> list:
        """Retrieve paginated results from the GitHub API.
        Args:
            query: The search query to execute.
        Returns:
            list: A list of results from all pages.
        """
        logger.info(f"Executing search query: {query}")
        results = []
        page = 1
        while True:
            # Fetch the current page of results
            logger.debug(f"Fetching page {page}")
            response = self.client.search_repositories(query=query, page=page)
            if not response or response.totalCount == 0:
                break
            # Convert PaginatedList to list and extend results
            page_results = list(response)
            results.extend(page_results)
            logger.debug(f"Found {len(page_results)} results on page {page}")
            # Check if we've reached the end
            if len(page_results) < 29:  # GitHub's default page size
                break
            page += 1
        logger.info(f"Total results found: {len(results)}")
        return results 

    @retry_on_failure()
    def filter_repositories(self, language: str = "python", min_stars: int = 0, max_stars: int = 1000, keywords: list = None) -> list:
        """Filter repositories based on specified criteria.
        Args:
            language: Primary language of the repositories (default: 'python').
            min_stars: Minimum number of stars (default: 0).
            max_stars: Maximum number of stars (default: 1000).
            keywords: List of keywords to search in repository descriptions (default: None).
        Returns:
            list: A list of filtered repositories.
        """
        query_parts = [f"language:{language}", f"stars:{min_stars}..{max_stars}"]
        if keywords:
            query_parts.extend([f'"{keyword}"' for keyword in keywords])
        query = " ".join(query_parts)
        logger.info(f"Filtering repositories with criteria: {query}")
        return self.get_paginated_results(query) 

    @retry_on_failure()
    def get_repository_metadata(self, repo_name: str, language: str = "python") -> dict:
        """Retrieve metadata for a given repository, including language."""
        logger.info(f"Fetching metadata for repository: {repo_name}")
        repo = self.client.get_repo(repo_name)
        metadata = {
            "name": repo.name,
            "description": repo.description,
            "star_count": repo.stargazers_count,
            "url": repo.html_url,
            "language": getattr(repo, "language", language) or language
        }
        logger.debug(f"Repository metadata: {metadata}")
        return metadata 

    def store_repository_metadata(self, metadata: dict, missing: dict) -> None:
        """Store repository metadata in the database, including language."""
        logger.info(f"Storing metadata for repository: {metadata['name']}")
        session = self.Session()
        repo = Repository(**metadata)
        repo.missing_test_directories = missing.get("test_directories", False)
        repo.missing_test_files = missing.get("test_files", False)
        repo.missing_test_config_files = missing.get("test_config_files", False)
        repo.missing_cicd_configs = missing.get("cicd_configs", False)
        repo.missing_readme_mentions = missing.get("readme_mentions", False)
        repo.last_scanned_at = datetime.utcnow()
        session.add(repo)
        session.commit()
        logger.debug(f"Stored repository data: {metadata['name']} with missing components: {missing}")
        session.close()

    @retry_on_failure()
    def check_test_directories(self, repo_name: str) -> bool:
        """Check for the existence of common unit test directories in a given repository.
        Args:
            repo_name: The name of the repository (e.g., 'owner/repo').
        Returns:
            bool: True if test directories exist, False otherwise.
        """
        logger.info(f"Checking test directories for repository: {repo_name}")
        repo = self.client.get_repo(repo_name)
        test_dirs = ["tests", "test"]
        try:
            # Check root directory
            contents = repo.get_contents("")
            if any(content.name in test_dirs and content.type == "dir" for content in contents):
                logger.debug(f"Found test directory in root for {repo_name}")
                return True
            # Check src/ directory if it exists
            src_dir = next((c for c in contents if c.name == "src" and c.type == "dir"), None)
            if src_dir:
                src_contents = repo.get_contents("src")
                if any(content.name in test_dirs and content.type == "dir" for content in src_contents):
                    logger.debug(f"Found test directory in src/ for {repo_name}")
                    return True
            logger.debug(f"No test directories found for {repo_name}")
            return False
        except GithubException as e:
            logger.error(f"Error checking test directories for {repo_name}: {str(e)}")
            return False

    @retry_on_failure()
    def check_test_files(self, repo_name: str) -> bool:
        """Check for the existence of common unit test files in a given repository.
        Args:
            repo_name: The name of the repository (e.g., 'owner/repo').
        Returns:
            bool: True if test files exist, False otherwise.
        """
        logger.info(f"Checking test files for repository: {repo_name}")
        repo = self.client.get_repo(repo_name)
        test_patterns = ["test_*.py", "*_test.py"]
        try:
            # Check root directory
            contents = repo.get_contents("")
            if any(content.name.endswith("_test.py") or content.name.startswith("test_") for content in contents if content.type == "file"):
                logger.debug(f"Found test files in root for {repo_name}")
                return True
            # Check src/ directory if it exists
            src_dir = next((c for c in contents if c.name == "src" and c.type == "dir"), None)
            if src_dir:
                src_contents = repo.get_contents("src")
                if any(content.name.endswith("_test.py") or content.name.startswith("test_") for content in src_contents if content.type == "file"):
                    logger.debug(f"Found test files in src/ for {repo_name}")
                    return True
            # Check test directories if they exist
            test_dirs = ["tests", "test"]
            for test_dir_name in test_dirs:
                test_dir = next((c for c in contents if c.name == test_dir_name and c.type == "dir"), None)
                if test_dir:
                    test_contents = repo.get_contents(test_dir_name)
                    if any(content.name.endswith("_test.py") or content.name.startswith("test_") for content in test_contents if content.type == "file"):
                        logger.debug(f"Found test files in {test_dir_name}/ for {repo_name}")
                        return True
            logger.debug(f"No test files found for {repo_name}")
            return False
        except GithubException as e:
            logger.error(f"Error checking test files for {repo_name}: {str(e)}")
            return False

    def check_test_config_files(self, repo_name: str) -> bool:
        """Scan for configuration files related to testing in the root directory.
        Args:
            repo_name: The name of the repository (e.g., 'owner/repo').
        Returns:
            bool: True if test configuration files exist, False otherwise.
        """
        logger.info(f"Checking test config files for repository: {repo_name}")
        repo = self.client.get_repo(repo_name)
        config_files = ["pytest.ini", "tox.ini", "nose.cfg"]
        try:
            contents = repo.get_contents("")
            has_config = any(content.name in config_files and content.type == "file" for content in contents)
            logger.debug(f"Test config files {'found' if has_config else 'not found'} for {repo_name}")
            return has_config
        except GithubException as e:
            logger.error(f"Error checking test config files for {repo_name}: {str(e)}")
            return False

    def check_readme_for_test_frameworks(self, repo_name: str) -> bool:
        """Search the repository README for mentions of testing frameworks.
        Args:
            repo_name: The name of the repository (e.g., 'owner/repo').
        Returns:
            bool: True if testing frameworks are mentioned, False otherwise.
        """
        logger.info(f"Checking README for test frameworks in repository: {repo_name}")
        repo = self.client.get_repo(repo_name)
        try:
            readme = repo.get_readme()
            readme_content = readme.decoded_content.decode("utf-8").lower()
            test_frameworks = ["pytest", "unittest", "nose"]
            has_frameworks = any(framework in readme_content for framework in test_frameworks)
            logger.debug(f"Test framework mentions {'found' if has_frameworks else 'not found'} in README for {repo_name}")
            return has_frameworks
        except GithubException as e:
            logger.error(f"Error checking README for {repo_name}: {str(e)}")
            return False 

    def check_cicd_configs(self, repo_name: str) -> bool:
        """Detect CI/CD configurations related to testing in the repository.
        Args:
            repo_name: The name of the repository (e.g., 'owner/repo').
        Returns:
            bool: True if CI/CD configurations exist, False otherwise.
        """
        logger.info(f"Checking CI/CD configs for repository: {repo_name}")
        repo = self.client.get_repo(repo_name)
        cicd_files = [
            ".github/workflows/*.yml",  # GitHub Actions
            ".travis.yml",              # Travis CI
            "Jenkinsfile",              # Jenkins
            "teamcity.yml"              # TeamCity
        ]
        for file_pattern in cicd_files:
            try:
                contents = repo.get_contents(file_pattern)
                if contents:
                    logger.debug(f"Found CI/CD config {file_pattern} for {repo_name}")
                    return True
            except GithubException:
                continue
        logger.debug(f"No CI/CD configs found for {repo_name}")
        return False 

    def flag_missing_tests(self, repo_name: str) -> dict:
        """Flag repositories where unit testing frameworks and configurations are absent.
        Args:
            repo_name: The name of the repository (e.g., 'owner/repo').
        Returns:
            dict: A dictionary indicating which test components are missing.
        """
        logger.info(f"Checking for missing test components in repository: {repo_name}")
        missing = {
            "test_directories": not self.check_test_directories(repo_name),
            "test_files": not self.check_test_files(repo_name),
            "test_config_files": not self.check_test_config_files(repo_name),
            "cicd_configs": not self.check_cicd_configs(repo_name),
            "readme_mentions": not self.check_readme_for_test_frameworks(repo_name)
        }
        logger.debug(f"Missing test components for {repo_name}: {missing}")
        return missing 

    def store_missing_tests(self, repo_name: str, missing: dict) -> None:
        """Store information about missing test components for a repository in the database.
        Args:
            repo_name: The name of the repository (e.g., 'owner/repo').
            missing: A dictionary indicating which test components are missing, as returned by flag_missing_tests.
        """
        logger.info(f"Storing missing test information for repository: {repo_name}")
        session = self.Session()
        # Extract just the repository name from owner/repo format
        repo_name_only = repo_name.split('/')[-1]
        repo = session.query(Repository).filter_by(name=repo_name_only).first()
        if not repo:
            # If the repository doesn't exist in the database, create a new record
            metadata = self.get_repository_metadata(repo_name)
            repo = Repository(**metadata)
            session.add(repo)
        # Update the record with missing test information
        repo.missing_test_directories = missing.get("test_directories", False)
        repo.missing_test_files = missing.get("test_files", False)
        repo.missing_test_config_files = missing.get("test_config_files", False)
        repo.missing_cicd_configs = missing.get("cicd_configs", False)
        repo.missing_readme_mentions = missing.get("readme_mentions", False)
        logger.debug(f"Updating repo {repo_name_only} with missing test info: {missing}")
        session.flush()
        session.commit()
        session.close() 

    def get_recently_scanned_repos(self, days: int = None) -> list:
        """Get a list of repositories that have been scanned within the specified time period.
        Args:
            days: Number of days to look back. If None, returns all scanned repositories.
        Returns:
            list: List of repository names that have been scanned.
        """
        logger.info(f"Getting recently scanned repositories (days={days})")
        session = self.Session()
        query = session.query(Repository.name)
        
        if days is not None:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            query = query.filter(Repository.last_scanned_at >= cutoff_date)
            
        repos = [repo[0] for repo in query.all()]
        session.close()
        logger.debug(f"Found {len(repos)} recently scanned repositories")
        return repos 