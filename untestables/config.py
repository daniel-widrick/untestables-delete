import os
from dotenv import load_dotenv

class Config:
    """Application configuration."""
    def __init__(self):
        load_dotenv()
        self.abs_min_stars = int(os.getenv("ABS_MIN_STARS", "0"))
        self.abs_max_stars = int(os.getenv("ABS_MAX_STARS", "1000000"))
        self.default_chunk_size = int(os.getenv("DEFAULT_CHUNK_SIZE", "100"))
        self.scanner_command = os.getenv("SCANNER_COMMAND", "poetry run untestables")

def get_config():
    return Config()

if __name__ == '__main__':
    config = get_config()
    print(f"Absolute Min Stars: {config.abs_min_stars}")
    print(f"Absolute Max Stars: {config.abs_max_stars}")
    print(f"Default Chunk Size: {config.default_chunk_size}")
    print(f"Scanner Command: {config.scanner_command}")
