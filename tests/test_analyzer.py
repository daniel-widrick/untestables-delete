"""
Unit tests for the AnalyzerService.
"""
import pytest
from unittest.mock import patch, MagicMock
import shlex
import subprocess

from untestables.analyzer import AnalyzerService
from untestables.config import Config

# Mock GITHUB_TOKEN and DATABASE_URL for all tests in this file
@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test_token_analyzer")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

@pytest.fixture
def mock_config():
    config = Config()
    config.abs_min_stars = 100
    config.abs_max_stars = 500
    config.default_chunk_size = 50
    config.scanner_command = "poetry run untestables" # Default for predictability
    return config

@pytest.fixture
def analyzer_service(mock_config):
    with patch('untestables.analyzer.get_config', return_value=mock_config):
        with patch('untestables.analyzer.GitHubClient') as MockGHClient:
            mock_gh_instance = MockGHClient.return_value
            service = AnalyzerService()
            service.github_client = mock_gh_instance 
            service.config = mock_config # Ensure service uses the mock_config
            return service

def test_calculate_missing_ranges_no_processed_stars(analyzer_service, mock_config):
    """Test gap calculation when no stars have been processed yet."""
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=[])

    expected_gaps = []
    current_min = mock_config.abs_min_stars
    while current_min <= mock_config.abs_max_stars:
        chunk_end = min(current_min + mock_config.default_chunk_size - 1, mock_config.abs_max_stars)
        expected_gaps.append((current_min, chunk_end))
        current_min = chunk_end + 1

    gaps = analyzer_service.calculate_missing_ranges()
    assert gaps == expected_gaps

def test_calculate_missing_ranges_all_stars_processed(analyzer_service, mock_config):
    """Test gap calculation when all stars in the range are already processed."""
    processed = list(range(mock_config.abs_min_stars, mock_config.abs_max_stars + 1))
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=processed)

    gaps = analyzer_service.calculate_missing_ranges()
    assert gaps == []

def test_calculate_missing_ranges_some_gaps(analyzer_service, mock_config):
    """Test gap calculation with some gaps present."""
    processed = list(range(100,150)) + list(range(200,250)) + list(range(300,350)) + list(range(400,450)) + [500]
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=processed)

    expected_gaps = [
        (150, 199),
        (250, 299),
        (350, 399),
        (450, 499)
    ]
    gaps = analyzer_service.calculate_missing_ranges()
    assert gaps == expected_gaps

def test_calculate_missing_ranges_edge_cases(analyzer_service, mock_config):
    """Test with edge cases like processed stars outside configured range."""
    processed = [10, 20, mock_config.abs_min_stars -10, mock_config.abs_max_stars + 10, 600]
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=processed)

    expected_gaps = []
    current_min = mock_config.abs_min_stars
    while current_min <= mock_config.abs_max_stars:
        chunk_end = min(current_min + mock_config.default_chunk_size - 1, mock_config.abs_max_stars)
        expected_gaps.append((current_min, chunk_end))
        current_min = chunk_end + 1

    gaps = analyzer_service.calculate_missing_ranges()
    assert gaps == expected_gaps

def test_calculate_missing_ranges_large_gap_chunking(analyzer_service, mock_config):
    """Test that a large gap is correctly chunked."""
    mock_config.abs_min_stars = 0
    mock_config.abs_max_stars = 299 
    mock_config.default_chunk_size = 100
    processed = [0, 299] 
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=processed)
    analyzer_service.config = mock_config # Update service's config

    expected_gaps = [
        (1, 100),   
        (101, 200), 
        (201, 298)  
    ]
    gaps = analyzer_service.calculate_missing_ranges()
    assert gaps == expected_gaps

def test_calculate_missing_ranges_small_chunks(analyzer_service, mock_config):
    """Test with a chunk size smaller than some gaps."""
    mock_config.abs_min_stars = 10
    mock_config.abs_max_stars = 35
    mock_config.default_chunk_size = 5
    processed = [12, 13, 20, 28, 29, 30]
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=processed)
    analyzer_service.config = mock_config
    expected_gaps = [
        (10, 11),      
        (14, 18),      
        (19, 19),      
        (21, 25),      
        (26, 27),      
        (31, 35)       
    ]
    gaps = analyzer_service.calculate_missing_ranges()
    assert gaps == expected_gaps

def test_calculate_missing_ranges_perfect_coverage_by_chunks(analyzer_service, mock_config):
    """Test when processed stars align perfectly with chunk boundaries, leaving no gaps."""
    mock_config.abs_min_stars = 0
    mock_config.abs_max_stars = 99
    mock_config.default_chunk_size = 50
    processed = list(range(0, 100))
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=processed)
    analyzer_service.config = mock_config
    gaps = analyzer_service.calculate_missing_ranges()
    assert gaps == []

def test_calculate_missing_ranges_no_processed_stars_min_max_equal(analyzer_service, mock_config):
    """Test when min_stars == max_stars and no stars processed."""
    mock_config.abs_min_stars = 100
    mock_config.abs_max_stars = 100
    mock_config.default_chunk_size = 10
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=[])
    analyzer_service.config = mock_config
    expected_gaps = [(100, 100)]
    gaps = analyzer_service.calculate_missing_ranges()
    assert gaps == expected_gaps

def test_calculate_missing_ranges_one_star_processed_min_max_equal(analyzer_service, mock_config):
    """Test when min_stars == max_stars and that one star is processed."""
    mock_config.abs_min_stars = 100
    mock_config.abs_max_stars = 100
    mock_config.default_chunk_size = 10
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=[100])
    analyzer_service.config = mock_config
    expected_gaps = []
    gaps = analyzer_service.calculate_missing_ranges()
    assert gaps == expected_gaps

def test_calculate_missing_ranges_processed_outside_bounds(analyzer_service, mock_config):
    """Test when processed stars are completely outside the configured min/max range."""
    mock_config.abs_min_stars = 100
    mock_config.abs_max_stars = 200
    mock_config.default_chunk_size = 50
    processed = [10, 20, 30, 250, 300]
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=processed)
    analyzer_service.config = mock_config
    expected_gaps = [
        (100,149),
        (150,199),
        (200,200)
    ]
    gaps = analyzer_service.calculate_missing_ranges()
    assert gaps == expected_gaps

def test_calculate_missing_ranges_processed_is_empty_list(analyzer_service, mock_config):
    """Test when processed star list is explicitly empty."""
    mock_config.abs_min_stars = 0
    mock_config.abs_max_stars = 9
    mock_config.default_chunk_size = 5
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=[])
    analyzer_service.config = mock_config
    expected_gaps = [
        (0,4),
        (5,9)
    ]
    gaps = analyzer_service.calculate_missing_ranges()
    assert gaps == expected_gaps

def test_calculate_missing_ranges_max_stars_is_zero(analyzer_service, mock_config):
    """Test when abs_max_stars is 0."""
    mock_config.abs_min_stars = 0
    mock_config.abs_max_stars = 0
    mock_config.default_chunk_size = 5
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=[])
    analyzer_service.config = mock_config
    expected_gaps = [(0,0)]
    gaps = analyzer_service.calculate_missing_ranges()
    assert gaps == expected_gaps

    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=[0])
    analyzer_service.config = mock_config
    expected_gaps = []
    gaps = analyzer_service.calculate_missing_ranges()
    assert gaps == expected_gaps

def test_select_next_gap_with_available_gaps(analyzer_service):
    """Test that select_next_gap returns the first available gap."""
    mock_gaps = [(10, 20), (30, 40), (50, 60)]
    analyzer_service.calculate_missing_ranges = MagicMock(return_value=mock_gaps)

    selected_gap = analyzer_service.select_next_gap()
    assert selected_gap == mock_gaps[0]
    analyzer_service.calculate_missing_ranges.assert_called_once()

def test_select_next_gap_no_gaps_available(analyzer_service):
    """Test that select_next_gap returns None when no gaps are available."""
    analyzer_service.calculate_missing_ranges = MagicMock(return_value=[])

    selected_gap = analyzer_service.select_next_gap()
    assert selected_gap is None
    analyzer_service.calculate_missing_ranges.assert_called_once()

def test_select_next_gap_uses_calculate_missing_ranges_output(analyzer_service, mock_config):
    """Test that select_next_gap correctly uses the output of calculate_missing_ranges."""
    processed = list(range(100,150)) + list(range(200,250)) + list(range(300,350)) + list(range(400,450)) + [500]
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=processed)
    analyzer_service.config = mock_config # Ensure it uses the base mock_config for this test

    expected_first_gap = (150, 199)
    selected_gap = analyzer_service.select_next_gap()
    assert selected_gap == expected_first_gap

def test_construct_scanner_command_default_config(analyzer_service, mock_config):
    """Test constructing the scanner command with default configuration."""
    min_stars, max_stars = 100, 200
    # mock_config.scanner_command is "poetry run untestables" from fixture
    expected_command = f"{mock_config.scanner_command} --min-stars {min_stars} --max-stars {max_stars}"
    command = analyzer_service.construct_scanner_command(min_stars, max_stars)
    assert command == expected_command

def test_construct_scanner_command_custom_config(analyzer_service, mock_config):
    """Test constructing the scanner command with a custom command in config."""
    custom_base_command = "custom_script --option value"
    analyzer_service.config.scanner_command = custom_base_command # Modify on the service's config
    min_stars, max_stars = 50, 75

    expected_command = f"{custom_base_command} --min-stars {min_stars} --max-stars {max_stars}"
    command = analyzer_service.construct_scanner_command(min_stars, max_stars)
    assert command == expected_command

def test_construct_scanner_command_different_star_values(analyzer_service, mock_config):
    """Test with different min/max star values."""
    analyzer_service.config.scanner_command = "scan_tool"
    min_stars, max_stars = 0, 10
    expected_command = f"scan_tool --min-stars {min_stars} --max-stars {max_stars}"
    command = analyzer_service.construct_scanner_command(min_stars, max_stars)
    assert command == expected_command

    min_stars, max_stars = 999, 10000
    expected_command_2 = f"scan_tool --min-stars {min_stars} --max-stars {max_stars}"
    command_2 = analyzer_service.construct_scanner_command(min_stars, max_stars)
    assert command_2 == expected_command_2

# Tests for execute_scanner_command_with_output
@patch('untestables.analyzer.subprocess.Popen')
def test_execute_scanner_command_with_output_success(mock_popen, analyzer_service):
    """Test execute_scanner_command_with_output for success."""
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("Success output", "") # Expected as str due to text=True
    mock_process.returncode = 0
    mock_popen.return_value = mock_process

    command = "my_scanner --go"
    exit_code, stdout, stderr = analyzer_service.execute_scanner_command_with_output(command)

    assert exit_code == 0
    assert stdout == "Success output"
    assert stderr == ""
    mock_popen.assert_called_once_with(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    mock_process.communicate.assert_called_once()

@patch('untestables.analyzer.subprocess.Popen')
def test_execute_scanner_command_with_output_failure(mock_popen, analyzer_service):
    """Test execute_scanner_command_with_output for failure exit code."""
    mock_process = MagicMock()
    mock_process.communicate.return_value = ("", "Error output") # Expected as str
    mock_process.returncode = 1
    mock_popen.return_value = mock_process

    command = "my_scanner --fail"
    exit_code, stdout, stderr = analyzer_service.execute_scanner_command_with_output(command)

    assert exit_code == 1
    assert stdout == ""
    assert stderr == "Error output"
    mock_popen.assert_called_once_with(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

@patch('untestables.analyzer.subprocess.Popen')
def test_execute_scanner_command_with_output_file_not_found(mock_popen, analyzer_service):
    """Test execute_scanner_command_with_output for FileNotFoundError."""
    mock_popen.side_effect = FileNotFoundError("Command not found")
    command = "non_existent_cmd"
    exit_code, stdout, stderr = analyzer_service.execute_scanner_command_with_output(command)

    assert exit_code == -1
    assert stdout == ""
    assert "Command not found: non_existent_cmd" in stderr 
    mock_popen.assert_called_once_with(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

@patch('untestables.analyzer.subprocess.Popen')
def test_execute_scanner_command_with_output_other_exception(mock_popen, analyzer_service):
    """Test execute_scanner_command_with_output for other Popen exception."""
    exception_message = "Some other Popen error"
    mock_popen.side_effect = Exception(exception_message)
    command = "cmd_that_causes_issues"
    exit_code, stdout, stderr = analyzer_service.execute_scanner_command_with_output(command)

    assert exit_code == -1
    assert stdout == ""
    assert stderr == exception_message 
    mock_popen.assert_called_once_with(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

# Test for the deprecated execute_scanner_command
@patch.object(AnalyzerService, 'execute_scanner_command_with_output')
def test_deprecated_execute_scanner_command_calls_new(mock_execute_with_output, analyzer_service):
    """Test that the deprecated execute_scanner_command calls the new one and logs warning."""
    mock_execute_with_output.return_value = (0, "stdout_data", "stderr_data")
    command_str = "any_command"
    with patch('untestables.analyzer.logger.warning') as mock_logger_warning:
        return_code = analyzer_service.execute_scanner_command(command_str)
        mock_logger_warning.assert_called_once_with(
            "DEPRECATED: execute_scanner_command is called. Use execute_scanner_command_with_output instead."
        )
    assert return_code == 0
    mock_execute_with_output.assert_called_once_with(command_str)

def test_handle_scan_result_success(analyzer_service):
    """Test handle_scan_result for a successful scan (exit code 0)."""
    with patch('untestables.analyzer.logger.info') as mock_logger_info, \
         patch('untestables.analyzer.logger.debug') as mock_logger_debug: # Patch debug as well
        analyzer_service.handle_scan_result(0, "Output data", "", (100, 200))

        mock_logger_info.assert_any_call("Handling scan result for range (100, 200). Exit code: 0")
        mock_logger_info.assert_any_call("Scan of range (100, 200) completed successfully.")
        mock_logger_debug.assert_any_call("Current partial completion signal detection is not implemented beyond exit code analysis.")

def test_handle_scan_result_failure(analyzer_service):
    """Test handle_scan_result for a failed scan (non-zero exit code)."""
    with patch('untestables.analyzer.logger.info') as mock_logger_info, \
         patch('untestables.analyzer.logger.warning') as mock_logger_warning, \
         patch('untestables.analyzer.logger.debug') as mock_logger_debug:
        analyzer_service.handle_scan_result(1, "", "Error on scan", (300, 400))

        mock_logger_info.assert_any_call("Handling scan result for range (300, 400). Exit code: 1")
        mock_logger_warning.assert_any_call("Scan of range (300, 400) failed or reported errors. Exit code: 1")
        mock_logger_debug.assert_any_call("Current partial completion signal detection is not implemented beyond exit code analysis.")

def test_handle_scan_result_potential_partial_completion_signal(analyzer_service):
    """Test handle_scan_result with a hypothetical partial completion exit code (e.g., 2)."""
    with patch('untestables.analyzer.logger.info') as mock_logger_info, \
         patch('untestables.analyzer.logger.warning') as mock_logger_warning, \
         patch('untestables.analyzer.logger.debug') as mock_logger_debug:
        analyzer_service.handle_scan_result(2, "Processed some, then rate limited", "", (500, 600))

        mock_logger_info.assert_any_call("Handling scan result for range (500, 600). Exit code: 2")
        mock_logger_warning.assert_any_call("Scan of range (500, 600) failed or reported errors. Exit code: 2")
        mock_logger_debug.assert_any_call("Current partial completion signal detection is not implemented beyond exit code analysis.")

def test_analyzer_service_init_logging(mock_config): # mock_config already sets scanner_command
    """Test that AnalyzerService.__init__ logs configuration values."""
    with patch('untestables.analyzer.get_config', return_value=mock_config) as mock_get_config, \
         patch('untestables.analyzer.logger.info') as mock_logger_info, \
         patch('untestables.analyzer.GitHubClient'): 

        service = AnalyzerService() 

        mock_get_config.assert_called_once()

        expected_log_calls = [
            "AnalyzerService initialized with configuration:",
            f"  Absolute Min Stars: {mock_config.abs_min_stars}",
            f"  Absolute Max Stars: {mock_config.abs_max_stars}",
            f"  Default Chunk Size: {mock_config.default_chunk_size}",
            f"  Scanner Command: {mock_config.scanner_command}" 
        ]

        actual_log_messages = [call_args[0][0] for call_args in mock_logger_info.call_args_list]

        for expected_msg in expected_log_calls:
            assert any(expected_msg in actual_msg for actual_msg in actual_log_messages), \
                   f"Expected log message fragment '{expected_msg}' not found in actual logs: {actual_log_messages}"

# Tests for run_scanner_orchestration_cycle
def test_run_orchestration_cycle_no_gaps(analyzer_service):
    """Test run_scanner_orchestration_cycle when no gaps are available."""
    analyzer_service.select_next_gap = MagicMock(return_value=None)
    # Patch the module-level logger used by AnalyzerService
    with patch('untestables.analyzer.logger.info') as mock_module_logger_info:
        result = analyzer_service.run_scanner_orchestration_cycle()
        assert result is False
        # Check that specific log messages occurred
        mock_module_logger_info.assert_any_call("Starting new scanner orchestration cycle...")
        mock_module_logger_info.assert_any_call("No gaps available to scan in this cycle.")

def test_run_orchestration_cycle_with_gaps_success(analyzer_service, mock_config):
    """Test run_scanner_orchestration_cycle with available gaps and successful scan."""
    test_gap = (100, 150)
    scanner_cmd_str = f"{mock_config.scanner_command} --min-stars {test_gap[0]} --max-stars {test_gap[1]}"

    analyzer_service.select_next_gap = MagicMock(return_value=test_gap)
    analyzer_service.construct_scanner_command = MagicMock(return_value=scanner_cmd_str)
    analyzer_service.execute_scanner_command_with_output = MagicMock(return_value=(0, "Scan successful", ""))
    analyzer_service.handle_scan_result = MagicMock()

    with patch('untestables.analyzer.logger.info') as mock_module_logger_info:
        result = analyzer_service.run_scanner_orchestration_cycle()

        assert result is True
        analyzer_service.select_next_gap.assert_called_once()
        analyzer_service.construct_scanner_command.assert_called_once_with(test_gap[0], test_gap[1], end_time_iso=None)
        analyzer_service.execute_scanner_command_with_output.assert_called_once_with(scanner_cmd_str)
        analyzer_service.handle_scan_result.assert_called_once_with(0, "Scan successful", "", test_gap)

        # Check for key log messages from the orchestration cycle itself
        mock_module_logger_info.assert_any_call("Starting new scanner orchestration cycle...")
        mock_module_logger_info.assert_any_call(f"Processing selected gap: {test_gap[0]}-{test_gap[1]}")
        mock_module_logger_info.assert_any_call("Scanner orchestration cycle finished.")


def test_run_orchestration_cycle_with_gaps_failure(analyzer_service, mock_config):
    """Test run_scanner_orchestration_cycle with available gaps and failed scan."""
    test_gap = (200, 250)
    scanner_cmd_str = f"{mock_config.scanner_command} --min-stars {test_gap[0]} --max-stars {test_gap[1]}"

    analyzer_service.select_next_gap = MagicMock(return_value=test_gap)
    analyzer_service.construct_scanner_command = MagicMock(return_value=scanner_cmd_str)
    analyzer_service.execute_scanner_command_with_output = MagicMock(return_value=(1, "", "Scan failed"))
    analyzer_service.handle_scan_result = MagicMock()

    with patch('untestables.analyzer.logger.info') as mock_info, \
         patch('untestables.analyzer.logger.warning') as mock_warning: # Also patch warning for stderr
        result = analyzer_service.run_scanner_orchestration_cycle()

        assert result is True 
        analyzer_service.select_next_gap.assert_called_once()
        analyzer_service.construct_scanner_command.assert_called_once_with(test_gap[0], test_gap[1], end_time_iso=None)
        analyzer_service.execute_scanner_command_with_output.assert_called_once_with(scanner_cmd_str)
        analyzer_service.handle_scan_result.assert_called_once_with(1, "", "Scan failed", test_gap)

        # Logs from within execute_scanner_command_with_output are not asserted here as it's mocked.
        # We assert that the correct parameters were passed to the mock and that handle_scan_result was called.
        # We can check for orchestration-level logs if desired.
        mock_info.assert_any_call("Starting new scanner orchestration cycle...")
        mock_info.assert_any_call(f"Processing selected gap: {test_gap[0]}-{test_gap[1]}")
        mock_info.assert_any_call("Scanner orchestration cycle finished.")
        # The following logs are from *inside* the mocked 'execute_scanner_command_with_output' / 'handle_scan_result'.
        # Therefore, they should be commented out for this test, which focuses on orchestration logic.
        # mock_info.assert_any_call(f"Scanner command finished with exit code: 1")
        # mock_warning.assert_any_call("Scanner stderr:\nScan failed")
