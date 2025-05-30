"""
Unit tests for the AnalyzerService.
"""
import pytest
from unittest.mock import patch, MagicMock

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
    return config

@pytest.fixture
def analyzer_service(mock_config):
    with patch('untestables.analyzer.get_config', return_value=mock_config):
        # Mock GitHubClient to prevent actual DB calls / token requirements during unit tests
        with patch('untestables.analyzer.GitHubClient') as MockGHClient:
            mock_gh_instance = MockGHClient.return_value
            service = AnalyzerService()
            service.github_client = mock_gh_instance # Ensure the service uses the mock
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
    # Simulate all individual stars being processed
    processed = list(range(mock_config.abs_min_stars, mock_config.abs_max_stars + 1))
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=processed)
    
    gaps = analyzer_service.calculate_missing_ranges()
    assert gaps == []

def test_calculate_missing_ranges_some_gaps(analyzer_service, mock_config):
    """Test gap calculation with some gaps present."""
    # Processed: 100-149 (covered by first default chunk), 200-249, 300-349, 400-449, 500
    # Config: min=100, max=500, chunk=50
    # Expected Gaps:
    # (150,199)
    # (250,299)
    # (350,399)
    # (450,499)
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
    
    # Expect the full range to be chunked as none of the processed stars are relevant
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
    mock_config.abs_max_stars = 299 # Creates a 300 star range (0-299)
    mock_config.default_chunk_size = 100
    # processed = [0, 299] leaves a gap of 1-298
    processed = [0, 299] 
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=processed)

    # Analyzer config is updated via the fixture if we re-patch get_config
    with patch('untestables.analyzer.get_config', return_value=mock_config):
        # Re-initialize or update service's config if it's cached internally by instance
        analyzer_service.config = mock_config 
        expected_gaps = [
            (1, 100),    # 0 is processed, gap 1-298. chunk 1: 1-100
            (101, 200),  # chunk 2: 101-200
            (201, 298)   # chunk 3: 201-298. 299 is processed.
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
    
    with patch('untestables.analyzer.get_config', return_value=mock_config):
        analyzer_service.config = mock_config
        expected_gaps = [
            (10, 11),      # Gap before 12. Chunk (10, min(14,11)=11)
            (14, 18),      # Gap 14-19. Chunk (14, min(18,19)=18)
            (19, 19),      # Remainder of 14-19. Chunk (19, min(23,19)=19)
            (21, 25),      # Gap 21-27. Chunk (21, min(25,27)=25)
            (26, 27),      # Remainder of 21-27. Chunk (26, min(30,27)=27)
            (31, 35)       # Gap 31-35. Chunk (31, min(35,35)=35)
        ]
        gaps = analyzer_service.calculate_missing_ranges()
        assert gaps == expected_gaps

def test_calculate_missing_ranges_perfect_coverage_by_chunks(analyzer_service, mock_config):
    """Test when processed stars align perfectly with chunk boundaries, leaving no gaps."""
    mock_config.abs_min_stars = 0
    mock_config.abs_max_stars = 99
    mock_config.default_chunk_size = 50
    # Processed covers 0-49 and 50-99
    processed = list(range(0, 100))
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=processed)

    with patch('untestables.analyzer.get_config', return_value=mock_config):
        analyzer_service.config = mock_config
        gaps = analyzer_service.calculate_missing_ranges()
        assert gaps == []

def test_calculate_missing_ranges_no_processed_stars_min_max_equal(analyzer_service, mock_config):
    """Test when min_stars == max_stars and no stars processed."""
    mock_config.abs_min_stars = 100
    mock_config.abs_max_stars = 100
    mock_config.default_chunk_size = 10
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=[])
    with patch('untestables.analyzer.get_config', return_value=mock_config):
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
    with patch('untestables.analyzer.get_config', return_value=mock_config):
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
    with patch('untestables.analyzer.get_config', return_value=mock_config):
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
    with patch('untestables.analyzer.get_config', return_value=mock_config):
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
    with patch('untestables.analyzer.get_config', return_value=mock_config):
        analyzer_service.config = mock_config
        expected_gaps = [(0,0)]
        gaps = analyzer_service.calculate_missing_ranges()
        assert gaps == expected_gaps

    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=[0])
    with patch('untestables.analyzer.get_config', return_value=mock_config):
        analyzer_service.config = mock_config
        expected_gaps = []
        gaps = analyzer_service.calculate_missing_ranges()
        assert gaps == expected_gaps

def test_select_next_gap_with_available_gaps(analyzer_service):
    """Test that select_next_gap returns the first available gap."""
    # Mock calculate_missing_ranges to return a predefined list of gaps
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
    """Test that select_next_gap correctly uses the output of calculate_missing_ranges.
    This test integrates more with the actual calculate_missing_ranges logic via mocks.
    """
    # This setup is similar to test_calculate_missing_ranges_some_gaps
    # Config: min=100, max=500, chunk=50
    # Processed: 100-149, 200-249, 300-349, 400-449, 500
    # Expected Gaps from calculate_missing_ranges: (150,199), (250,299), (350,399), (450,499)
    processed = list(range(100,150)) + list(range(200,250)) + list(range(300,350)) + list(range(400,450)) + [500]
    analyzer_service.github_client.get_processed_star_counts = MagicMock(return_value=processed)
    
    # select_next_gap should pick the first of these calculated gaps
    expected_first_gap = (150, 199)
    selected_gap = analyzer_service.select_next_gap()
    assert selected_gap == expected_first_gap 