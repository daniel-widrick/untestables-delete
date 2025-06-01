import os
import pytest
from unittest.mock import patch
from untestables.config import Config, get_config

@pytest.fixture
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("ABS_MIN_STARS", "10")
    monkeypatch.setenv("ABS_MAX_STARS", "5000")
    monkeypatch.setenv("DEFAULT_CHUNK_SIZE", "50")
    monkeypatch.setenv("SCANNER_COMMAND", "my-custom-scanner --arg")

def test_config_loads_from_env(mock_env_vars):
    config = get_config()
    assert config.abs_min_stars == 10
    assert config.abs_max_stars == 5000
    assert config.default_chunk_size == 50
    assert config.scanner_command == "my-custom-scanner --arg"

@patch.dict(os.environ, {}, clear=True)
def test_config_default_values():
    # Ensure all relevant env vars are cleared for this test
    if "ABS_MIN_STARS" in os.environ: del os.environ["ABS_MIN_STARS"]
    if "ABS_MAX_STARS" in os.environ: del os.environ["ABS_MAX_STARS"]
    if "DEFAULT_CHUNK_SIZE" in os.environ: del os.environ["DEFAULT_CHUNK_SIZE"]
    if "SCANNER_COMMAND" in os.environ: del os.environ["SCANNER_COMMAND"]

    config = get_config(load_env=False)
    assert config.abs_min_stars == 0  # Default from config.py
    assert config.abs_max_stars == 1000000  # Default from config.py
    assert config.default_chunk_size == 100  # Default from config.py
    assert config.scanner_command == "poetry run untestables find-repos"  # Default from config.py

@patch.dict(os.environ, {}, clear=True)
def test_config_class_instantiation():
    # Clear relevant env vars to test default loading by Config class constructor
    if "ABS_MIN_STARS" in os.environ: del os.environ["ABS_MIN_STARS"]
    if "ABS_MAX_STARS" in os.environ: del os.environ["ABS_MAX_STARS"]
    if "DEFAULT_CHUNK_SIZE" in os.environ: del os.environ["DEFAULT_CHUNK_SIZE"]
    if "SCANNER_COMMAND" in os.environ: del os.environ["SCANNER_COMMAND"]

    config = Config(load_env=False) # Instantiating Config directly will load .env or defaults
    assert config.abs_min_stars == 0 # Default from os.getenv in Config.__init__
    assert config.abs_max_stars == 1000000 # Default from os.getenv in Config.__init__
    assert config.default_chunk_size == 100 # Default from os.getenv in Config.__init__
    assert config.scanner_command == "poetry run untestables find-repos" # Default from os.getenv in Config.__init__
