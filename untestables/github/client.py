"""GitHub API client implementation."""
import os
from typing import Optional
from github import Github
from github.GithubException import GithubException
from dotenv import load_dotenv
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

class RateLimitExceeded(Exception):
    """Exception raised when the GitHub API rate limit is exceeded."""
    pass

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

class GitHubClient:
    """Client for interacting with the GitHub API."""
    
    def __init__(self, token: Optional[str] = None, db_url: Optional[str] = None):
        """Initialize the GitHub client.
        
        Args:
            token: GitHub personal access token. If not provided, will try to load from GITHUB_TOKEN env var.
            db_url: Database URL. If not provided, will try to load from DATABASE_URL env var.
        """
        load_dotenv()
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN environment variable or pass token directly.")
        
        self.client = Github(self.token)
        self.db_url = db_url or os.getenv("DATABASE_URL")
        if not self.db_url:
            raise ValueError("DATABASE_URL environment variable not set and no fallback provided.")
        self.engine = create_engine(self.db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def get_rate_limit(self) -> dict:
        """Get the current rate limit information.
        
        Returns:
            dict: Rate limit information including remaining requests and reset time.
        """
        rate_limit = self.client.get_rate_limit()
        return {
            "remaining": rate_limit.core.remaining,
            "limit": rate_limit.core.limit,
            "reset_time": rate_limit.core.reset
        }
    
    def test_connection(self) -> bool:
        """Test the GitHub API connection.
        
        Returns:
            bool: True if connection is successful, False otherwise.
        """
        try:
            # Make a simple API call to test the connection
            self.client.get_user()
            return True
        except GithubException:
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
            raise RateLimitExceeded(f"GitHub API rate limit exceeded. Resets at {info['reset_time']}.")
        elif info["remaining"] < min_remaining:
            print(f"Warning: GitHub API rate limit is low ({info['remaining']} remaining, resets at {info['reset_time']}).")
        return info 

    def get_paginated_results(self, query: str) -> list:
        """Retrieve paginated results from the GitHub API.
        Args:
            query: The search query to execute.
        Returns:
            list: A list of results from all pages.
        """
        results = []
        page = 1
        while True:
            # Fetch the current page of results
            response = self.client.search_repositories(query=query, page=page)
            if not response:
                break
            results.extend(response)
            page += 1
        return results 

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
        return self.get_paginated_results(query) 

    def get_repository_metadata(self, repo_name: str) -> dict:
        """Retrieve metadata for a given repository.
        Args:
            repo_name: The name of the repository (e.g., 'owner/repo').
        Returns:
            dict: Repository metadata including name, description, star count, and URL.
        Raises:
            GithubException: If the repository is not found.
        """
        repo = self.client.get_repo(repo_name)
        return {
            "name": repo.name,
            "description": repo.description,
            "star_count": repo.stargazers_count,
            "url": repo.html_url
        } 

    def store_repository_metadata(self, metadata: dict, missing: dict) -> None:
        """Store repository metadata in the database.
        Args:
            metadata: Dictionary containing repository metadata.
            missing: Dictionary indicating which test components are missing, as returned by flag_missing_tests.
        """
        session = self.Session()
        repo = Repository(**metadata)
        repo.missing_test_directories = missing.get("test_directories", False)
        repo.missing_test_files = missing.get("test_files", False)
        repo.missing_test_config_files = missing.get("test_config_files", False)
        repo.missing_cicd_configs = missing.get("cicd_configs", False)
        repo.missing_readme_mentions = missing.get("readme_mentions", False)
        session.add(repo)
        session.commit()
        session.close() 

    def check_test_directories(self, repo_name: str) -> bool:
        """Check for the existence of common unit test directories in a given repository.
        Args:
            repo_name: The name of the repository (e.g., 'owner/repo').
        Returns:
            bool: True if test directories exist, False otherwise.
        """
        repo = self.client.get_repo(repo_name)
        test_dirs = ["tests", "test"]
        try:
            # Check root directory
            contents = repo.get_contents("")
            if any(content.name in test_dirs and content.type == "dir" for content in contents):
                return True
            # Check src/ directory if it exists
            src_dir = next((c for c in contents if c.name == "src" and c.type == "dir"), None)
            if src_dir:
                src_contents = repo.get_contents("src")
                if any(content.name in test_dirs and content.type == "dir" for content in src_contents):
                    return True
            return False
        except GithubException:
            return False

    def check_test_files(self, repo_name: str) -> bool:
        """Check for the existence of common unit test files in a given repository.
        Args:
            repo_name: The name of the repository (e.g., 'owner/repo').
        Returns:
            bool: True if test files exist, False otherwise.
        """
        repo = self.client.get_repo(repo_name)
        test_patterns = ["test_*.py", "*_test.py"]
        try:
            # Check root directory
            contents = repo.get_contents("")
            if any(content.name.endswith("_test.py") or content.name.startswith("test_") for content in contents if content.type == "file"):
                return True
            # Check src/ directory if it exists
            src_dir = next((c for c in contents if c.name == "src" and c.type == "dir"), None)
            if src_dir:
                src_contents = repo.get_contents("src")
                if any(content.name.endswith("_test.py") or content.name.startswith("test_") for content in src_contents if content.type == "file"):
                    return True
            # Check test directories if they exist
            test_dirs = ["tests", "test"]
            for test_dir_name in test_dirs:
                test_dir = next((c for c in contents if c.name == test_dir_name and c.type == "dir"), None)
                if test_dir:
                    test_contents = repo.get_contents(test_dir_name)
                    if any(content.name.endswith("_test.py") or content.name.startswith("test_") for content in test_contents if content.type == "file"):
                        return True
            return False
        except GithubException:
            return False

    def check_test_config_files(self, repo_name: str) -> bool:
        """Scan for configuration files related to testing in the root directory.
        Args:
            repo_name: The name of the repository (e.g., 'owner/repo').
        Returns:
            bool: True if test configuration files exist, False otherwise.
        """
        repo = self.client.get_repo(repo_name)
        config_files = ["pytest.ini", "tox.ini", "nose.cfg"]
        try:
            contents = repo.get_contents("")
            return any(content.name in config_files and content.type == "file" for content in contents)
        except GithubException:
            return False

    def check_readme_for_test_frameworks(self, repo_name: str) -> bool:
        """Search the repository README for mentions of testing frameworks.
        Args:
            repo_name: The name of the repository (e.g., 'owner/repo').
        Returns:
            bool: True if testing frameworks are mentioned, False otherwise.
        """
        repo = self.client.get_repo(repo_name)
        try:
            readme = repo.get_readme()
            readme_content = readme.decoded_content.decode("utf-8").lower()
            test_frameworks = ["pytest", "unittest", "nose"]
            return any(framework in readme_content for framework in test_frameworks)
        except GithubException:
            return False 

    def check_cicd_configs(self, repo_name: str) -> bool:
        """Detect CI/CD configurations related to testing in the repository.
        Args:
            repo_name: The name of the repository (e.g., 'owner/repo').
        Returns:
            bool: True if CI/CD configurations exist, False otherwise.
        """
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
                    return True
            except GithubException:
                continue
        return False 

    def flag_missing_tests(self, repo_name: str) -> dict:
        """Flag repositories where unit testing frameworks and configurations are absent.
        Args:
            repo_name: The name of the repository (e.g., 'owner/repo').
        Returns:
            dict: A dictionary indicating which test components are missing.
        """
        missing = {
            "test_directories": not self.check_test_directories(repo_name),
            "test_files": not self.check_test_files(repo_name),
            "test_config_files": not self.check_test_config_files(repo_name),
            "cicd_configs": not self.check_cicd_configs(repo_name),
            "readme_mentions": not self.check_readme_for_test_frameworks(repo_name)
        }
        return missing 

    def store_missing_tests(self, repo_name: str, missing: dict) -> None:
        """Store information about missing test components for a repository in the database.
        Args:
            repo_name: The name of the repository (e.g., 'owner/repo').
            missing: A dictionary indicating which test components are missing, as returned by flag_missing_tests.
        """
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
        print(f"Updating repo {repo_name_only} with missing test info: {missing}")
        session.flush()
        session.commit()
        session.close() 