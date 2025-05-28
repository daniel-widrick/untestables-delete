import click
from typing import Optional
from untestables.github.client import GitHubClient

@click.command()
@click.option('--min-stars', type=int, default=5, help='Minimum number of stars')
@click.option('--max-stars', type=int, default=1000, help='Maximum number of stars')
def main(min_stars: int, max_stars: int) -> None:
    """Find Python repositories that need unit tests."""
    click.echo(f"Searching for repositories with {min_stars} to {max_stars} stars")
    
    try:
        client = GitHubClient()
        
        # Search for repositories
        click.echo("Searching GitHub for Python repositories...")
        repos = client.filter_repositories(
            language="python",
            min_stars=min_stars,
            max_stars=max_stars
        )
        
        if not repos:
            click.echo("No repositories found matching the criteria.")
            return
            
        click.echo(f"Found {len(repos)} repositories. Analyzing test coverage...")
        
        # Analyze each repository
        for repo in repos:
            repo_name = repo.full_name
            click.echo(f"\nAnalyzing {repo_name}...")
            
            # Get repository metadata
            metadata = client.get_repository_metadata(repo_name)
            
            # Check for missing test components
            missing = client.flag_missing_tests(repo_name)
            
            # Store results
            client.store_repository_metadata(metadata, missing)
            
            # Display results
            if any(missing.values()):
                click.echo(f"Repository {repo_name} is missing:")
                if missing["test_directories"]:
                    click.echo("  - Test directories")
                if missing["test_files"]:
                    click.echo("  - Test files")
                if missing["test_config_files"]:
                    click.echo("  - Test configuration files")
                if missing["cicd_configs"]:
                    click.echo("  - CI/CD configurations")
                if missing["readme_mentions"]:
                    click.echo("  - Test framework mentions in README")
            else:
                click.echo(f"Repository {repo_name} has good test coverage!")
                
        click.echo("\nAnalysis complete! Results have been stored in the database.")
        
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()

if __name__ == '__main__':
    main() 