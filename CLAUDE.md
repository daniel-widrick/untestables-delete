# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Running Tests
```bash
poetry run test  # or poetry run tests
poetry run pytest  # Runs with coverage automatically
```

### Running the Application
```bash
poetry run untestables find-repos --min-stars 5 --max-stars 1000  # Search for repos
poetry run untestables scan --duration 7d  # Run orchestrator for 7 days
```

### Database Migrations
```bash
poetry run alembic upgrade head  # Apply all migrations
poetry run alembic revision -m "description"  # Create new migration
```

### Docker
```bash
docker-compose build scanner  # Build scanner service
docker-compose run scanner  # Run scanner
docker build -f tests.Dockerfile -t untestables-tests .  # Build test image
```

## Architecture

### Purpose
Untestables identifies Python repositories on GitHub that lack unit tests. It systematically scans GitHub by star count ranges, analyzes repositories for test presence, and stores results in a database.

### Key Components

**CLI Interface (`cli.py`)**: Two commands - `find-repos` searches GitHub within a star range, `scan` orchestrates continuous scanning by identifying gaps.

**GitHub Client (`github/client.py`)**: Manages GitHub API interactions with rate limit handling, retry logic, and comprehensive test detection (directories, files, CI/CD configs, README mentions).

**Analyzer Service (`analyzer.py`)**: Identifies unprocessed star ranges, breaks them into chunks, and executes scanner commands. Handles orchestration and gap detection.

**Database Model (`github/models.py`)**: Repository table tracks metadata, test indicators (5 boolean flags), and timestamps. Uses SQLAlchemy with Alembic migrations.

### Key Patterns

**Rate Limit Management**: Exponential backoff with automatic retries when hitting GitHub API limits. Gracefully handles 403/429 responses.

**Gap Detection Algorithm**: Queries database for processed star counts, identifies missing ranges, and processes them in configurable chunks (default 100 stars).

**Subprocess Execution**: Analyzer spawns scanner processes to handle chunks independently, enabling parallel processing and better error isolation.

**Logging**: Hierarchical logger setup (app.cli, app.github_client, app.analyzer) with file and console output. Uses custom LoggingManager for consistent formatting.

### Test Detection
The system checks for tests through multiple indicators:
- Test directories: `test/`, `tests/`, `testing/`, `spec/`, `specs/`
- Test files: `*test*.py`, `*spec*.py`
- Test configs: `pytest.ini`, `setup.cfg`, `tox.ini`, `.coveragerc`
- CI/CD: `.github/workflows/`, `.travis.yml`, `.gitlab-ci.yml`, etc.
- README mentions: Searches for test-related keywords

### Environment Configuration
Required environment variables (via `.env` file):
- `GITHUB_TOKEN`: GitHub API access token
- `DATABASE_URL`: PostgreSQL or SQLite connection string
- `ABS_MIN_STARS`: Absolute minimum stars to scan (default: 0)
- `ABS_MAX_STARS`: Absolute maximum stars to scan (default: 1000000)
- `DEFAULT_CHUNK_SIZE`: Stars per chunk (default: 100)