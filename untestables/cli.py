import click
import os
from datetime import datetime
from typing import Optional
from untestables.github.client import GitHubClient
from common.logging import setup_logging, get_logger

@click.command()
@click.option('--min-stars', type=int, default=5, help='Minimum number of stars')
@click.option('--max-stars', type=int, default=1000, help='Maximum number of stars')
def main(min_stars: int, max_stars: int) -> None:
    """Find Python repositories that need unit tests."""
    # Set up logging with a timestamped log file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = f'logs/untestables_{timestamp}.log'
    os.makedirs('logs', exist_ok=True)
    setup_logging(log_file)
    logger = get_logger()
    
    logger.info(f"Starting repository search with {min_stars} to {max_stars} stars")
    
    try:
        client = GitHubClient()
        logger.info("GitHub client initialized")
        
        # Check rate limits before starting
        rate_limit = client.get_rate_limit()
        logger.info(f"Current GitHub API rate limit: {rate_limit['remaining']}/{rate_limit['limit']} remaining")
        
        # Search for repositories
        logger.info("Searching GitHub for Python repositories...")
        click.echo("Searching GitHub for Python repositories...")
        repos = client.filter_repositories(
            language="python",
            min_stars=min_stars,
            max_stars=max_stars
        )
        
        if not repos:
            logger.warning("No repositories found matching the criteria")
            click.echo("No repositories found matching the criteria.")
            return
            
        logger.info(f"Found {len(repos)} repositories to analyze")
        click.echo(f"Found {len(repos)} repositories. Analyzing test coverage...")
        
        # Analyze each repository
        for repo in repos:
            repo_name = repo.full_name
            logger.info(f"Analyzing repository: {repo_name}")
            click.echo(f"\nAnalyzing {repo_name}...")
            
            try:
                # Get repository metadata
                metadata = client.get_repository_metadata(repo_name)
                logger.debug(f"Repository metadata: {metadata}")
                
                # Check for missing test components
                missing = client.flag_missing_tests(repo_name)
                logger.debug(f"Missing test components: {missing}")
                
                # Store results
                client.store_repository_metadata(metadata, missing)
                logger.info(f"Stored results for {repo_name}")
                
                # Display results
                if any(missing.values()):
                    logger.info(f"Repository {repo_name} has missing test components")
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
                    logger.info(f"Repository {repo_name} has good test coverage")
                    click.echo(f"Repository {repo_name} has good test coverage!")
                    
            except Exception as e:
                logger.error(f"Error processing repository {repo_name}: {str(e)}", exc_info=True)
                click.echo(f"Error processing {repo_name}: {str(e)}", err=True)
                continue
                
        logger.info("Analysis complete")
        click.echo("\nAnalysis complete! Results have been stored in the database.")
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        click.echo(f"Error: {str(e)}", err=True)
        raise click.Abort()

if __name__ == '__main__':
    main() 