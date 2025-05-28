"""GitHub API client implementation."""
import os
from typing import Optional
from github import Github
from github.GithubException import GithubException
from dotenv import load_dotenv

class RateLimitExceeded(Exception):
    """Exception raised when the GitHub API rate limit is exceeded."""
    pass

class GitHubClient:
    """Client for interacting with the GitHub API."""
    
    def __init__(self, token: Optional[str] = None):
        """Initialize the GitHub client.
        
        Args:
            token: GitHub personal access token. If not provided, will try to load from GITHUB_TOKEN env var.
        """
        load_dotenv()
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN environment variable or pass token directly.")
        
        self.client = Github(self.token)
    
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