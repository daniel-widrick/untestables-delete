import click
import os
from datetime import datetime, timedelta, timezone
import time # For sleep
from typing import Optional
from common.logging import LoggingManager
import sys # For stderr
import re # For parsing duration

# --- Setup logging early ---
# Ensure the logs directory exists
LOGS_DIR = 'logs'
os.makedirs(LOGS_DIR, exist_ok=True)
# Generate a timestamped log file name
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file_path = os.path.join(LOGS_DIR, f'untestables_{timestamp}.log')

# Configure the main 'app' logger which will have the file and console handlers.
# This LoggingManager instance configures the 'app' logger.
app_logger_manager = LoggingManager(
    logger_name='app',  # Main logger for the application
    log_file=log_file_path,
    console_output=True,
    propagate=False  # The 'app' logger itself should not propagate to root
)

# Get a specific logger for this cli.py module, via LoggingManager
logger = LoggingManager.get_logger('app.cli')
# --- Logging is now set up ---

# Now import GitHubClient. Its logger will be 'app.github_client' (see client.py changes)
from untestables.github.client import GitHubClient, APILimitError # Import APILimitError
from untestables.analyzer import AnalyzerService # Simplified import

# Exit code for scanner when APILimitError is encountered
SCANNER_CLI_APILIMIT_EXIT_CODE = 2 # Distinct from AnalyzerService's internal one

# --- Duration Parsing Helper ---
def parse_duration(duration_str: str) -> Optional[timedelta]:
    """Parses a duration string like '7d', '3h', '30m' into a timedelta."""
    match = re.fullmatch(r'(\d+)([dhms])', duration_str.lower())
    if not match:
        logger.error(f"Invalid duration format: '{duration_str}'. Use <number><d|h|m|s>.")
        return None
    
    value, unit = int(match.group(1)), match.group(2)
    if unit == 'd':
        return timedelta(days=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'm':
        return timedelta(minutes=value)
    elif unit == 's':
        return timedelta(seconds=value)
    return None # Should not happen due to regex

# --- Click Command Group ---
@click.group()
def cli():
    """Github Repository Test Finder CLI"""
    pass

@cli.command('find-repos') # Renamed from main
@click.option('--min-stars', type=int, default=5, help='Minimum number of stars')
@click.option('--max-stars', type=int, default=1000, help='Maximum number of stars')
@click.option('--rescan-days', type=int, help='Re-scan repositories that were last scanned more than this many days ago')
@click.option('--force-rescan', is_flag=True, help='Force re-scan of all repositories, ignoring last scan time')
@click.option('--end-time', type=str, default=None, help='Optional ISO timestamp for when the find-repos process should stop itself.')
def find_repos(min_stars: int, max_stars: int, rescan_days: Optional[int] = None, force_rescan: bool = False, end_time_iso: Optional[str] = None) -> None:
    """(Formerly main) Finds Python repositories based on stars and stores their test status."""
    # Logging is already set up. The logger instance is available globally in this module.
    # No need to call setup_logging() or get_logger() here again.
    
    logger.info(f"Starting repository 'find-repos' with {min_stars} to {max_stars} stars")
    click.echo(f"Starting repository search with {min_stars} to {max_stars} stars")
    if rescan_days:
        logger.info(f"Will re-scan repositories last scanned more than {rescan_days} days ago")
        click.echo(f"Will re-scan repositories last scanned more than {rescan_days} days ago")
    if force_rescan:
        logger.info("Force re-scan enabled - will scan all repositories")
        click.echo("Force re-scan enabled - will scan all repositories")
    
    end_time_dt: Optional[datetime] = None
    if end_time_iso:
        try:
            end_time_dt = datetime.fromisoformat(end_time_iso.replace('Z', '+00:00'))
            if end_time_dt.tzinfo is None:
                end_time_dt = end_time_dt.replace(tzinfo=timezone.utc) # Assume UTC if not specified
            logger.info(f"Scan process will stop if current time exceeds: {end_time_dt.isoformat()}")
        except ValueError:
            logger.error(f"Invalid --end-time format: '{end_time_iso}'. Please use ISO format. Continuing without time limit.")
            # Continue without an end_time if parsing fails, or handle as a fatal error
            # For now, just log and proceed without it.

    try:
        client = GitHubClient()
        logger.info("GitHub client initialized")
        
        rate_limit = client.get_rate_limit_info() # Use the new method
        search_remaining = rate_limit.get('search',{}).get('remaining',0)
        search_limit = rate_limit.get('search',{}).get('limit',0)
        logger.info(f"Current GitHub Search API rate limit: {search_remaining}/{search_limit} remaining.")
        if search_remaining == 0:
            reset_dt = rate_limit.get('search',{}).get('reset_time_datetime')
            reset_unix = rate_limit.get('search',{}).get('reset_time_unix')
            msg = f"GitHub Search API rate limit is 0. Reset at {reset_dt}."
            logger.error(msg)
            if reset_unix:
                print(f"ANALYZER_ERROR:APILimitError:{reset_unix}", file=sys.stderr)
            click.echo(msg, err=True)
            sys.exit(SCANNER_CLI_APILIMIT_EXIT_CODE)
            
        recently_scanned = set()
        if not force_rescan:
            recently_scanned = set(client.get_recently_scanned_repos(rescan_days))
            logger.info(f"Found {len(recently_scanned)} recently scanned repositories to potentially skip")

        logger.info(f"Searching GitHub for Python repositories (stars: {min_stars}-{max_stars})...")
        click.echo(f"Searching GitHub for Python repositories (stars: {min_stars}-{max_stars})...")
        repos = client.filter_repositories(
            language="Python",
            min_stars=min_stars,
            max_stars=max_stars,
            keywords=None, # Explicitly pass None as per original filter_repositories signature
            end_time_iso=end_time_iso # Pass the end_time_iso string
        )
        
        if not repos:
            logger.warning("No repositories found matching the criteria")
            click.echo("No repositories found matching the criteria.")
            sys.exit(0) # Successful exit, no work to do
            
        logger.info(f"Found {len(repos)} repositories to analyze")
        click.echo(f"Found {len(repos)} repositories. Analyzing test coverage...")
        
        start_time = datetime.now(timezone.utc)
        end_time_overall = start_time + total_duration_td
        logger.info(f"Scan command initiated. Total duration: {total_duration_td}. Scan will run until {end_time_overall.isoformat()}.")
        
        for repo in repos:
            repo_name = repo.full_name
            repo_url = repo.html_url
            
            if not force_rescan and repo_url in recently_scanned:
                logger.info(f"Skipping {repo_name} ({repo_url}) - recently scanned")
                continue
                
            logger.info(f"Analyzing repository: {repo_name}")
            click.echo(f"\nAnalyzing {repo_name}...")
            
            try:
                metadata = client.get_repository_metadata(repo_name)
                missing = client.flag_missing_tests(repo_name)
                client.store_repository_metadata(metadata, missing)
                logger.info(f"Stored results for {repo_name}")
                
                if any(missing.values()):
                    logger.info(f"Repository {repo_name} has missing test components")
                    click.echo(f"Repository {repo_name} is missing:")
                    if missing.get("test_directories"):
                        click.echo("  - Test directories")
                    if missing.get("test_files"):
                        click.echo("  - Test files")
                    if missing.get("test_config_files"):
                        click.echo("  - Test configuration files")
                    if missing.get("cicd_configs"):
                        click.echo("  - CI/CD configurations")
                    if missing.get("readme_mentions"):
                        click.echo("  - Test framework mentions in README")
                else:
                    logger.info(f"Repository {repo_name} has good test coverage")
                    click.echo(f"Repository {repo_name} has good test coverage!")
                    
            except APILimitError as e:
                logger.error(f"GitHub API rate limit hit while processing repository {repo_name}: {e.message}")
                if e.reset_time_unix:
                    print(f"ANALYZER_ERROR:APILimitError:{e.reset_time_unix}", file=sys.stderr)
                click.echo(f"Error: GitHub API rate limit hit. {e.message}. Try again later.", err=True)
                sys.exit(SCANNER_CLI_APILIMIT_EXIT_CODE) 
            except Exception as e:
                logger.error(f"Error processing repository {repo_name}: {str(e)}", exc_info=True)
                click.echo(f"Error processing {repo_name}: {str(e)}", err=True)
                continue 
                
        logger.info(f"'{find_repos.name}' command complete.")
        click.echo(f"\n'{find_repos.name}' analysis complete! Results have been stored in the database.")
        sys.exit(0) # Successful completion
        
    except APILimitError as e:
        logger.error(f"GitHub API rate limit hit during script execution: {e.message}")
        if e.reset_time_unix:
            print(f"ANALYZER_ERROR:APILimitError:{e.reset_time_unix}", file=sys.stderr)
        click.echo(f"Error: GitHub API rate limit hit. {e.message}. Check logs. Try again later.", err=True)
        sys.exit(SCANNER_CLI_APILIMIT_EXIT_CODE) 
    except Exception as e:
        # Ensure the error is logged with full traceback
        logger.critical(f"Fatal error in '{find_repos.name}': {str(e)}", exc_info=True)
    finally:
        # This block executes whether an exception occurred or not
        # It's a good place for cleanup or final logging
        logger.info(f"'{find_repos.name}' command complete.")

@cli.command('scan')
@click.option('--duration', default='7d', help='Total duration to run the scanner for (e.g., 7d, 12h, 30m). Default 7 days.')
@click.option('--no-gaps-sleep', default='1h', help='Sleep interval when no gaps are found (e.g., 1h, 30m). Default 1 hour.')
@click.option('--cycle-sleep', default='1m', help='Sleep interval between scan attempts/cycles. Default 1 minute.')
def scan(duration: str, no_gaps_sleep: str, cycle_sleep: str):
    """Continuously finds and scans unprocessed repository star ranges."""
    logger.info(f"Starting continuous scan process. Duration: {duration}, No Gaps Sleep: {no_gaps_sleep}, Cycle Sleep: {cycle_sleep}")

    total_duration_td = parse_duration(duration)
    if not total_duration_td:
        click.echo("Invalid --duration format.", err=True)
        sys.exit(1)
    
    no_gaps_sleep_td = parse_duration(no_gaps_sleep)
    if not no_gaps_sleep_td:
        click.echo("Invalid --no-gaps-sleep format.", err=True)
        sys.exit(1)
    no_gaps_sleep_seconds = no_gaps_sleep_td.total_seconds()
        
    cycle_sleep_td = parse_duration(cycle_sleep)
    if not cycle_sleep_td:
        click.echo("Invalid --cycle-sleep format.", err=True)
        sys.exit(1)
    cycle_sleep_seconds = cycle_sleep_td.total_seconds()

    start_time = datetime.now(timezone.utc)
    end_time_overall = start_time + total_duration_td
    
    # DATABASE_URL will be read from .env by AnalyzerService's components (Config/GitHubClient)
    # No need for explicit db_url handling here anymore.

    try:
        # AnalyzerService will now rely on environment variable for DATABASE_URL.
        # Its internal GitHubClient/Config will load .env and read os.getenv("DATABASE_URL").
        analyzer = AnalyzerService()
        logger.info("AnalyzerService initialized for scan command.")
    except ValueError as e: # Handles GitHub token not found or DATABASE_URL not found from init path
        logger.critical(f"Failed to initialize AnalyzerService: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    while datetime.now(timezone.utc) < end_time_overall:
        logger.info("Starting new analysis and scan cycle...")
        cycle_start_time = datetime.now(timezone.utc)
        remaining_duration_for_cycle_td = end_time_overall - cycle_start_time
        logger.info(f"Overall scan end time: {end_time_overall.isoformat()}. Remaining duration for this cycle and its subprocesses: {remaining_duration_for_cycle_td}")

        if remaining_duration_for_cycle_td.total_seconds() <= 0:
            logger.info("Total scan duration reached before starting new cycle. Exiting.")
            break

        # Pass the overall end_time to the orchestration cycle
        # The orchestration cycle will then pass it to the find-repos command
        scan_attempted = analyzer.run_scanner_orchestration_cycle(end_time_iso=end_time_overall.isoformat())

        if analyzer.api_limit_reset_time and datetime.now(timezone.utc) < analyzer.api_limit_reset_time:
            # API limit was hit *during* the cycle (either proactively by analyzer or reported by scanner)
            wait_time_seconds = (analyzer.api_limit_reset_time - datetime.now(timezone.utc)).total_seconds()
            wait_time_seconds = max(1, wait_time_seconds) # Ensure at least 1s sleep
            logger.info(f"API limit encountered in cycle. Reset at {analyzer.api_limit_reset_time}. Sleeping for {wait_time_seconds:.0f}s.")
            time.sleep(wait_time_seconds)
        elif not scan_attempted: # No gaps found, and not an API limit known to analyzer before starting cycle
            logger.info(f"No gaps found or scan not attempted for other reasons (e.g. proactive API limit check). Sleeping for {no_gaps_sleep_seconds:.0f}s (no_gaps_sleep)." )
            time.sleep(no_gaps_sleep_seconds)
        else: # Scan was attempted (and didn't immediately report an API limit that set analyzer.api_limit_reset_time)
            logger.info(f"Scan cycle finished. Sleeping for {cycle_sleep_seconds:.0f}s (cycle_sleep)." )
            time.sleep(cycle_sleep_seconds)
        
        # Check duration limit again before starting next iteration
        if datetime.now(timezone.utc) >= end_time_overall:
            logger.info(f"Total scan duration of {total_duration_td} reached. Exiting scan loop.")
            break
        
        # Optional: Add a small sleep here too, regardless of outcome, to prevent extremely rapid looping if sleeps above are short
        # time.sleep(1) 

    logger.info("Scan command finished.")
    click.echo("Scan command finished.")


if __name__ == '__main__':
    cli() # Changed to call the group 