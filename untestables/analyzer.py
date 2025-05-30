"""
Analyzer service to identify star ranges that need scanning.
"""
from typing import List, Tuple, Optional
import subprocess # Add for subprocess execution

# Replace standard logging with LoggingManager
from common.logging import LoggingManager
from untestables.config import get_config
from untestables.github.client import GitHubClient # Assuming GitHubClient is the way to access get_processed_star_counts

logger = LoggingManager.get_logger(__name__)


class AnalyzerService:
    def __init__(self, db_url: str = None): # db_url might be needed for GitHubClient
        self.config = get_config()
        logger.info("AnalyzerService initialized with configuration:")
        logger.info(f"  Absolute Min Stars: {self.config.abs_min_stars}")
        logger.info(f"  Absolute Max Stars: {self.config.abs_max_stars}")
        logger.info(f"  Default Chunk Size: {self.config.default_chunk_size}")
        logger.info(f"  Scanner Command: {self.config.scanner_command}")

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

    def select_next_gap(self) -> Optional[Tuple[int, int]]:
        """
        Selects the next gap to process based on the configured strategy.
        Currently, it selects the lowest available star range first.

        Returns:
            Optional[Tuple[int, int]]: The (min_stars, max_stars) for the next scan,
                                       or None if no gaps are available.
        """
        chunked_gaps = self.calculate_missing_ranges()

        if not chunked_gaps:
            logger.info("No gaps found to process.")
            return None

        # Strategy: Select the lowest available star range first.
        # The calculate_missing_ranges already returns them sorted and chunked.
        next_gap = chunked_gaps[0]
        logger.info(f"Selected next gap to process: {next_gap}")
        return next_gap

    def construct_scanner_command(self, min_stars: int, max_stars: int) -> str:
        """
        Constructs the scanner command string with the given min and max stars.

        Args:
            min_stars (int): The minimum number of stars for the scan.
            max_stars (int): The maximum number of of stars for the scan.

        Returns:
            str: The fully constructed scanner command string.
        """
        base_command = self.config.scanner_command
        command = f"{base_command} --min-stars {min_stars} --max-stars {max_stars}"
        logger.info(f"Constructed scanner command: {command}")
        return command

    def execute_scanner_command(self, command: str) -> int:
        """
        DEPRECATED: Prefer execute_scanner_command_with_output for richer results.
        Executes the given scanner command as a subprocess and waits for completion.

        Args:
            command (str): The full command string to execute.

        Returns:
            int: The exit code of the scanner process.
        """
        logger.warning("DEPRECATED: execute_scanner_command is called. Use execute_scanner_command_with_output instead.")
        exit_code, _, _ = self.execute_scanner_command_with_output(command)
        return exit_code

    def handle_scan_result(self, exit_code: int, stdout: str, stderr: str, scanned_range: Tuple[int, int]):
        """
        Handles the result of a scanner execution, including potential partial completion.
        NOTE: Full partial completion logic (adjusting gaps) is not yet implemented.
        This method currently logs the outcome.

        Args:
            exit_code (int): The exit code from the scanner.
            stdout (str): The standard output from the scanner.
            stderr (str): The standard error from the scanner.
            scanned_range (Tuple[int, int]): The (min_stars, max_stars) that were attempted.
        """
        logger.info(f"Handling scan result for range {scanned_range}. Exit code: {exit_code}")
        if exit_code == 0:
            logger.info(f"Scan of range {scanned_range} completed successfully.")
            # In the future, even with exit code 0, stdout/stderr might indicate partial completion.
        # TODO: Define specific exit codes or stdout/stderr messages for partial completion.
        # Example: if exit_code == 2 or "PARTIAL_COMPLETION" in stdout:
        #     logger.warning(f"Scanner indicated partial completion for range {scanned_range}.")
        #     # Here, logic would be needed to determine how much was processed and adjust the gap.
        #     # For now, we assume any non-zero exit code means the whole chunk should be retried or marked as failed.
        elif exit_code !=0:
             logger.warning(f"Scan of range {scanned_range} failed or reported errors. Exit code: {exit_code}")

        # Placeholder for logging related to partial completion signals
        logger.debug("Current partial completion signal detection is not implemented beyond exit code analysis.")
        # The actual adjustment of gap understanding would happen elsewhere, based on this method's findings.

    def run_scanner_orchestration_cycle(self) -> bool:
        """
        Runs one full cycle of the scanner orchestration:
        1. Selects a gap.
        2. If gap found, constructs and executes scanner command, then handles result.
        3. If no gap, logs and indicates completion for this cycle.

        Returns:
            bool: True if a scan was attempted (gap was found), False if no gaps were found.
        """
        logger.info("Starting new scanner orchestration cycle...")
        
        selected_gap = self.select_next_gap()
        
        if not selected_gap:
            logger.info("No gaps available to scan in this cycle.")
            # This addresses part of "Handle 'No Gaps' Scenario"
            return False # No scan attempted
            
        min_stars, max_stars = selected_gap
        logger.info(f"Processing selected gap: {min_stars}-{max_stars}")
        
        command_to_run = self.construct_scanner_command(min_stars, max_stars)
        
        # Here, one might add a check for "scanner busy" if that logic was part of this service.
        # For now, proceeding directly to execution.
        
        # execute_scanner_command already logs stdout/stderr, so we just need exit_code here
        # for handle_scan_result. We need to capture stdout/stderr to pass it though.
        # Modifying execute_scanner_command to return a more structured result might be better in the long run.
        # For now, let's re-fetch stdout/stderr if needed by handle_scan_result, 
        # or adjust execute_scanner_command to return them.
        # The current execute_scanner_command returns only exit_code.
        # For handle_scan_result, we need stdout & stderr strings.
        # Let's make execute_scanner_command return a tuple: (exit_code, stdout_str, stderr_str)

        exit_code, stdout_str, stderr_str = self.execute_scanner_command_with_output(command_to_run)

        self.handle_scan_result(exit_code, stdout_str, stderr_str, selected_gap)
        
        logger.info("Scanner orchestration cycle finished.")
        return True # Scan was attempted

    # To support run_scanner_orchestration_cycle, we need execute_scanner_command 
    # to return stdout/stderr strings. Let's create a new version or modify existing.
    # For clarity, let's make a new one for now that returns output.
    def execute_scanner_command_with_output(self, command: str) -> Tuple[int, str, str]:
        """
        Executes the given scanner command, waits, and returns exit code, stdout, and stderr.
        """
        logger.info(f"Executing scanner command for orchestration: {command}")
        try:
            import shlex
            process = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout_str, stderr_str = process.communicate() # Wait for completion
            exit_code = process.returncode

            if stdout_str.strip():
                logger.info(f"Scanner stdout:\n{stdout_str.strip()}")
            if stderr_str.strip():
                logger.warning(f"Scanner stderr:\n{stderr_str.strip()}")
            
            logger.info(f"Scanner command finished with exit code: {exit_code}")
            return exit_code, stdout_str, stderr_str
        except FileNotFoundError:
            logger.error(f"Error: The scanner command '{command.split()[0]}' was not found. Ensure it is installed and in PATH.")
            return -1, "", f"Command not found: {command.split()[0]}"
        except Exception as e:
            logger.error(f"An error occurred while executing scanner command '{command}': {e}")
            return -1, "", str(e)


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

    # Test select_next_gap
    print("\nTesting select_next_gap method...")
    # analyzer.github_client is already MockLargeGapClient from previous test
    # Config: abs_min=0, abs_max=1000, chunk=100. Processed: [10,20,900,950]
    # Expected gaps from MockLargeGapClient and this config:
    # (0,9), (21,120) -> chunked to (21,100) then (101,120) ... etc.
    # Let's re-initialize for clarity here or use a specific mock setup

    analyzer.config.abs_min_stars = 0
    analyzer.config.abs_max_stars = 250 # Small range for easier verification
    analyzer.config.default_chunk_size = 100
    class MockSelectTestClient:
        def get_processed_star_counts(self):
            return [50, 51, 52, 150, 151] # Gaps: 0-49, 53-149, 152-250
    analyzer.github_client = MockSelectTestClient()
    logger.info(f"Test select_next_gap with config: min={analyzer.config.abs_min_stars}, max={analyzer.config.abs_max_stars}, chunk={analyzer.config.default_chunk_size}")
    
    next_selected_gap = analyzer.select_next_gap()
    print(f"Selected next gap: {next_selected_gap}") # Expected: (0,99) or (0,49) depending on exact gap logic for first block
                                                    # With current logic: gap 0-49 -> chunk (0,99) if chunk is 100. Range is 0-49. So (0,49)
                                                    # Gaps: (0,49), (53,149), (152,250)
                                                    # Chunked: (0,49), (53,149), (152,249), (250,250) based on chunk 100
                                                    # Actually, for 53-149 with chunk 100: (53, 149) -> (53, (53+100-1)=152) -> min(152, 149) -> (53,149)
                                                    # For 152-250: (152, 250) -> (152, (152+100-1)=251) -> min(251, 250) -> (152,250)
                                                    # Let's recheck calculate_missing_ranges output carefully. 
                                                    # Processed: [50, 51, 52, 150, 151]. Min=0, Max=250, Chunk=100
                                                    # Relevant processed for gaps: [50, 51, 52, 150, 151, 251 (sentinel)]
                                                    # 1. last_processed = -1. star_val=50. 50 > 0. gap_start=0, gap_end=min(49,250)=49. Gaps=[(0,49)]
                                                    #    last_processed=50.
                                                    # 2. star_val=51. 51 > 50+1 no. last_processed=51.
                                                    # 3. star_val=52. 52 > 51+1 no. last_processed=52.
                                                    # 4. star_val=150. 150 > 52+1 yes. gap_start=53, gap_end=min(149,250)=149. Gaps=[(0,49), (53,149)]
                                                    #    last_processed=150.
                                                    # 5. star_val=151. 151 > 150+1 no. last_processed=151.
                                                    # 6. star_val=251. 251 > 151+1 yes. gap_start=152, gap_end=min(250,250)=250. Gaps=[(0,49), (53,149), (152,250)]
                                                    #    last_processed=251. Loop ends.
                                                    # Raw gaps: [(0,49), (53,149), (152,250)]
                                                    # Chunking:
                                                    # (0,49) -> current=0. chunk_end=min(0+100-1, 49)=min(99,49)=49. chunked=[(0,49)]. current=50. current>49, loop ends.
                                                    # (53,149) -> current=53. chunk_end=min(53+100-1, 149)=min(152,149)=149. chunked=[(0,49), (53,149)]. current=150. current>149, loop ends.
                                                    # (152,250) -> current=152. chunk_end=min(152+100-1, 250)=min(251,250)=250. chunked=[(0,49), (53,149), (152,250)]. current=251. current>250, loop ends.
                                                    # Final chunked gaps: [(0,49), (53,149), (152,250)]
                                                    # So, select_next_gap should return (0,49).

    # Test with no gaps
    analyzer.config.abs_min_stars = 50
    analyzer.config.abs_max_stars = 52
    # analyzer.github_client is still MockSelectTestClient, processed: [50, 51, 52, 150, 151]
    # Relevant for this config: [50,51,52, 53(sentinel)]
    # Gaps will be empty.
    logger.info(f"Test select_next_gap with NO gaps: min={analyzer.config.abs_min_stars}, max={analyzer.config.abs_max_stars}")
    next_selected_gap_none = analyzer.select_next_gap()
    print(f"Selected next gap (should be None): {next_selected_gap_none}") 

    # Test construct_scanner_command
    print("\nTesting construct_scanner_command method...")
    # analyzer.config.scanner_command should be "poetry run untestables" by default
    # from get_config() if not overridden by .env
    # Let's assume default config for this test print
    
    # Ensure config is using defaults if .env isn't set for SCANNER_COMMAND
    # For the __main__ test, we can explicitly set it on the config instance for predictability
    analyzer.config.scanner_command = "poetry run untestables" # Default
    
    test_min_stars, test_max_stars = 100, 200
    constructed_cmd = analyzer.construct_scanner_command(test_min_stars, test_max_stars)
    expected_cmd = f"poetry run untestables --min-stars {test_min_stars} --max-stars {test_max_stars}"
    print(f"Constructed command: {constructed_cmd}")
    print(f"Expected command:    {expected_cmd}")
    assert constructed_cmd == expected_cmd

    # Test with a different command from config
    analyzer.config.scanner_command = "my_custom_scanner --path /app"
    custom_min, custom_max = 1, 5
    constructed_cmd_custom = analyzer.construct_scanner_command(custom_min, custom_max)
    expected_cmd_custom = f"my_custom_scanner --path /app --min-stars {custom_min} --max-stars {custom_max}"
    print(f"Constructed custom command: {constructed_cmd_custom}")
    print(f"Expected custom command:    {expected_cmd_custom}")
    assert constructed_cmd_custom == expected_cmd_custom

    # Test execute_scanner_command
    print("\nTesting execute_scanner_command method...")
    
    # Test 1: Successful command (e.g., a simple echo)
    # On Windows, 'echo' is a shell builtin. On Unix, '/bin/echo' or 'echo'.
    # Using sys.platform to make it a bit more cross-platform for a simple test.
    import sys
    echo_command = "echo Hello Analyzer"
    if sys.platform == "win32":
        # Popen on Windows might need shell=True for builtins like echo,
        # or use `cmd /c echo ...`. For simplicity, let's use a command that works more universally.
        # `python -c "print('Hello Analyzer')"` is more reliable for a test.
        test_success_cmd = 'python -c "import sys; sys.stdout.write(\'Hello Analyzer\'); sys.exit(0)"'
    else:
        test_success_cmd = "echo Hello Analyzer"

    logger.info(f"Executing test success command: {test_success_cmd}")
    exit_code_success = analyzer.execute_scanner_command(test_success_cmd)
    print(f"Test command '{test_success_cmd}' exited with: {exit_code_success}")
    assert exit_code_success == 0

    # Test 2: Command that fails (e.g., a non-existent command or command that errors)
    test_fail_cmd = "non_existent_command_analyzer_test --arg"
    logger.info(f"Executing test fail command: {test_fail_cmd}")
    exit_code_fail = analyzer.execute_scanner_command(test_fail_cmd)
    print(f"Test command '{test_fail_cmd}' exited with: {exit_code_fail}")
    # Expecting -1 due to FileNotFoundError or other Exception handled in the method
    assert exit_code_fail == -1

    # Test 3: Command that exists but returns non-zero exit code
    if sys.platform == "win32":
        test_error_exit_cmd = 'python -c "import sys; sys.stderr.write(\'Simulated error\'); sys.exit(5)"'
    else:
        # Using `false` command on Unix-like systems
        test_error_exit_cmd = "false" 
    
    logger.info(f"Executing test error exit command: {test_error_exit_cmd}")
    exit_code_error = analyzer.execute_scanner_command(test_error_exit_cmd)
    print(f"Test command '{test_error_exit_cmd}' exited with: {exit_code_error}")
    if sys.platform != "win32": # `false` exits with 1
        assert exit_code_error == 1
    else: # python script exits with 5
        assert exit_code_error == 5 

    # Test handle_scan_result (basic logging test)
    print("\nTesting handle_scan_result method (logging checks mostly)...")
    test_range = (100,200)
    analyzer.handle_scan_result(0, "Completed fully", "", test_range)
    analyzer.handle_scan_result(1, "", "An error occurred", test_range)
    # To test partial completion logging, we'd need to simulate that signal
    # For now, it just logs the debug message about non-implementation
    analyzer.handle_scan_result(2, "PARTIAL_COMPLETION_SIGNAL", "", test_range) 

    # Test run_scanner_orchestration_cycle
    print("\nTesting run_scanner_orchestration_cycle...")

    # Scenario 1: Gaps are available
    analyzer.config.abs_min_stars = 0
    analyzer.config.abs_max_stars = 100
    analyzer.config.default_chunk_size = 50
    class MockOrchestrationClientWithGaps:
        def get_processed_star_counts(self):
            return [10, 20] # Gaps: 0-9, 21-100 -> chunks (0,9), (21,70), (71,100)
    analyzer.github_client = MockOrchestrationClientWithGaps()
    analyzer.config.scanner_command = "echo" # Use a safe command for testing execution
    if sys.platform == "win32":
        analyzer.config.scanner_command = 'python -c "import sys; sys.stdout.write(\'Mock scan output\'); sys.exit(0)"'

    logger.info("Testing orchestration cycle WITH gaps...")
    scan_attempted = analyzer.run_scanner_orchestration_cycle()
    print(f"Scan attempted (with gaps): {scan_attempted}")
    assert scan_attempted is True

    # Scenario 2: No gaps available
    class MockOrchestrationClientNoGaps:
        def get_processed_star_counts(self):
            return list(range(0, 101)) # All processed from 0-100
    analyzer.github_client = MockOrchestrationClientNoGaps()
    logger.info("Testing orchestration cycle with NO gaps...")
    scan_attempted_no_gaps = analyzer.run_scanner_orchestration_cycle()
    print(f"Scan attempted (no gaps): {scan_attempted_no_gaps}")
    assert scan_attempted_no_gaps is False

    # To truly test the loop and sleep, the __main__ would need to change:
    # print("\nSimulating continuous run (2 cycles with 1s sleep, if gaps exist)...")
    # for i in range(2):
    #     logger.info(f"--- Orchestration Iteration {i+1} ---")
    #     # Re-setup client for consistent gap availability if needed for multiple iterations
    #     analyzer.github_client = MockOrchestrationClientWithGaps() 
    #     if sys.platform == "win32":
    #         analyzer.config.scanner_command = 'python -c "import sys; sys.stdout.write(\'Mock scan output\'); sys.exit(0)"'
    #     else:
    #        analyzer.config.scanner_command = "echo" 

    #     attempted = analyzer.run_scanner_orchestration_cycle()
    #     if not attempted:
    #         logger.info("No more gaps, stopping simulation.")
    #         break
    #     if i < 1: # Don't sleep after the last iteration
    #         logger.info("Simulating sleep for 1 second...")
    #         import time
    #         time.sleep(1) 