"""
Analyzer service to identify star ranges that need scanning.
"""
from typing import List, Tuple

# Replace standard logging with LoggingManager
from common.logging import LoggingManager
from untestables.config import get_config
from untestables.github.client import GitHubClient # Assuming GitHubClient is the way to access get_processed_star_counts

logger = LoggingManager.get_logger(__name__)


class AnalyzerService:
    def __init__(self, db_url: str = None): # db_url might be needed for GitHubClient
        self.config = get_config()
        # We need a way to get processed star counts.
        # This might involve instantiating GitHubClient or having a dedicated DB access class.
        # For now, let's assume GitHubClient provides this.
        # A GITHUB_TOKEN might be required for GitHubClient, even if only DB is used.
        # This needs clarification based on GitHubClient's __init__.
        # If GITHUB_TOKEN is strictly for API calls not related to get_processed_star_counts,
        # we might need to adjust GitHubClient or provide a dummy token.
        self.github_client = GitHubClient(db_url=db_url) # This will raise ValueError if GITHUB_TOKEN is not set

    def get_processed_star_ranges(self) -> List[int]:
        """
        Retrieves a sorted list of distinct star counts that have been processed.
        """
        # This is the function identified from Task 1
        return self.github_client.get_processed_star_counts()

    def calculate_missing_ranges(self) -> List[Tuple[int, int]]:
        """
        Calculates the ranges of star counts that have not yet been scanned,
        respecting the absolute min/max stars and chunking large gaps.
        """
        processed_stars = self.get_processed_star_ranges()
        logger.info(f"Processed star counts: {processed_stars}")

        desired_min = self.config.abs_min_stars
        desired_max = self.config.abs_max_stars
        chunk_size = self.config.default_chunk_size

        gaps: List[Tuple[int, int]] = []
        current_scan_point = desired_min

        # Add a sentinel value to processed_stars to handle the last gap easily
        # Ensure processed_stars are within desired_min and desired_max and sorted
        relevant_processed_stars = sorted(list(set(
            [s for s in processed_stars if desired_min <= s <= desired_max] + [desired_max + 1]
        )))
        
        if not relevant_processed_stars or relevant_processed_stars[0] > desired_max: # Handle empty or out of bound processed stars
             # If no stars processed or all are beyond max, the whole range is a gap
            if desired_min <= desired_max:
                gaps.append((desired_min, desired_max))
        else:
            # Iterate through relevant processed stars to find gaps
            last_processed_star = desired_min -1 # Ensure the first gap starts from desired_min

            for star_val in relevant_processed_stars:
                if star_val > last_processed_star + 1:
                    # A gap exists from (last_processed_star + 1) to (star_val - 1)
                    gap_start = last_processed_star + 1
                    gap_end = min(star_val - 1, desired_max) # Ensure gap_end does not exceed desired_max
                    
                    if gap_start <= gap_end: # Ensure valid gap
                         gaps.append((gap_start, gap_end))
                last_processed_star = star_val
                if last_processed_star >= desired_max:
                    break # Stop if we've processed up to or beyond desired_max
        
        # Chunk the identified gaps
        chunked_gaps: List[Tuple[int, int]] = []
        for start, end in gaps:
            current = start
            while current <= end:
                chunk_end = min(current + chunk_size - 1, end)
                chunked_gaps.append((current, chunk_end))
                current = chunk_end + 1
        
        logger.info(f"Identified {len(chunked_gaps)} chunked gap(s): {chunked_gaps}")
        return chunked_gaps

if __name__ == '__main__':
    # This is for basic testing of the AnalyzerService
    # You would need to set GITHUB_TOKEN and DATABASE_URL environment variables
    # or ensure GitHubClient can be instantiated without them for this specific case.
    
    # Configure logging using LoggingManager for standalone execution
    LoggingManager(__name__, log_level="INFO", console_output=True)
    # Also configure for the other loggers used in the main block, if any, or a root logger.
    # For simplicity, configuring __name__ should cover logs from this file.
    # If GitHubClient or Config also log, they'd need their loggers configured too for this test run,
    # or they should inherit from a root logger configured by LoggingManager.
    # For now, this primarily ensures logger.info calls within this file's scope are handled.
    LoggingManager.get_logger("untestables.config").setLevel("INFO") # Example if config logs
    LoggingManager.get_logger("untestables.github.client").setLevel("INFO") # Example if client logs and needs specific setup here

    # Example: Simulate already processed star counts
    # To run this, you might need to mock get_processed_star_counts or setup a test DB
    # For now, let's assume we can proceed if GITHUB_TOKEN is set.
    # analyzer = AnalyzerService(db_url='sqlite:///:memory:') # Example in-memory DB

    # To make this runnable without full DB setup for a quick test:
    # One approach is to allow GitHubClient to be initialized without a token if only DB ops are needed,
    # or provide a dummy token.
    # For now, this __main__ block will likely fail if GITHUB_TOKEN is not in .env

    print("AnalyzerService basic test. Ensure GITHUB_TOKEN and DATABASE_URL are set in .env")
    print(f"Using config: MinStars={get_config().abs_min_stars}, MaxStars={get_config().abs_max_stars}, Chunk={get_config().default_chunk_size}")

    # Mocking processed stars for a standalone test run.
    # In a real scenario, this comes from the database.
    class MockGitHubClient:
        def get_processed_star_counts(self):
            # Simulate some processed star counts for testing
            # return [10, 11, 12, 50, 51, 200, 201, 202, 300, 450, 451, 600]
            return [150, 151, 152, 190, 300, 301, 302, 303, 400]


    analyzer = AnalyzerService() # Will use env for GITHUB_TOKEN and DATABASE_URL
    # Override the client for this test block
    analyzer.github_client = MockGitHubClient() 
    
    # Test with specific config values (can be set in .env for this test)
    # Example: ABS_MIN_STARS=100, ABS_MAX_STARS=500, DEFAULT_CHUNK_SIZE=50
    print(f"ABS_MIN_STARS (config): {analyzer.config.abs_min_stars}")
    print(f"ABS_MAX_STARS (config): {analyzer.config.abs_max_stars}")
    print(f"DEFAULT_CHUNK_SIZE (config): {analyzer.config.default_chunk_size}")

    missing_ranges = analyzer.calculate_missing_ranges()
    print(f"Calculated missing ranges: {missing_ranges}")
    
    # Example: Test with an empty database (no processed stars)
    class MockEmptyGitHubClient:
        def get_processed_star_counts(self):
            return []
    analyzer.github_client = MockEmptyGitHubClient()
    print("Testing with no processed stars:")
    missing_ranges_empty = analyzer.calculate_missing_ranges()
    print(f"Calculated missing ranges (empty DB): {missing_ranges_empty}")

    # Example: Test where all stars are processed within a smaller range
    analyzer.config.abs_min_stars = 150
    analyzer.config.abs_max_stars = 190
    analyzer.github_client = MockGitHubClient() # reuse client with [150,151,152,190..]
    print(f"Testing with a range fully covered (min={analyzer.config.abs_min_stars}, max={analyzer.config.abs_max_stars})")
    missing_ranges_covered = analyzer.calculate_missing_ranges()
    print(f"Calculated missing ranges (fully covered): {missing_ranges_covered}")

    # Example: Test with a large gap
    analyzer.config.abs_min_stars = 0
    analyzer.config.abs_max_stars = 1000
    analyzer.config.default_chunk_size = 100
    class MockLargeGapClient:
        def get_processed_star_counts(self):
            return [10, 20, 900, 950]
    analyzer.github_client = MockLargeGapClient()
    print(f"Testing with large gaps (min={analyzer.config.abs_min_stars}, max={analyzer.config.abs_max_stars}, chunk={analyzer.config.default_chunk_size})")
    missing_ranges_large_gap = analyzer.calculate_missing_ranges()
    print(f"Calculated missing ranges (large gap): {missing_ranges_large_gap}") 