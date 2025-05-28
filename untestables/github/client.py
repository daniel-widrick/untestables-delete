"""GitHub API client implementation."""
import os
from typing import Optional
from github import Github
from github.GithubException import GithubException
from dotenv import load_dotenv

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