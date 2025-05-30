# Mission Untestable

A tool to find Python repositories that need unit tests and to continuously scan for gaps in processed star ranges.

## Command-Line Interface (CLI)

The application now provides two main commands under the `untestables` entry point, managed via Poetry.

```sh
poetry run untestables --help
```

This will show the available subcommands.

### 1. `find-repos` Command

This command is responsible for searching GitHub for repositories within a specific star range, analyzing their test coverage, and storing the results in the database. This is the command that the `scan` orchestrator calls for individual chunks.

**Usage:**

```sh
poetry run untestables find-repos [OPTIONS]
```

**Options for `find-repos`:**

- `--min-stars INTEGER` Minimum number of stars for this specific scan (default: 5).
- `--max-stars INTEGER` Maximum number of stars for this specific scan (default: 1000).
- `--rescan-days INTEGER` Re-scan repositories that were last scanned more than this many days ago. If not provided, the decision to rescan is based on whether the repository URL is already known from a previous scan (and `force-rescan` is not set).
- `--force-rescan` Force re-scan of all repositories within the given `min-stars` and `max-stars` range, ignoring their last scan time.

**Behavior of `find-repos`:**

- This command performs a single pass for the given star range.
- It checks for previously scanned repositories (unless `--force-rescan` is used or `--rescan-days` criteria are met for a specific repository) to avoid redundant work.
- If it encounters a GitHub API rate limit, it will print a special error message to `stderr` (e.g., `ANALYZER_ERROR:APILimitError:timestamp`) and exit with a specific code (2). This signal is used by the `scan` command.

**Examples for `find-repos`:**

Scan for Python repos with 100-200 stars that haven't been processed before:

```sh
poetry run untestables find-repos --min-stars 100 --max-stars 200
```

Force re-scan of repositories between 50-75 stars:

```sh
poetry run untestables find-repos --min-stars 50 --max-stars 75 --force-rescan
```

### 2. `scan` Command

This command orchestrates the scanning process over a longer period. It identifies unprocessed star ranges ("gaps") based on the application's overall configuration and previously scanned data, then calls the `find-repos` command for manageable chunks within those gaps.

**Usage:**

```sh
poetry run untestables scan [OPTIONS]
```

**Options for `scan`:**

- `--duration TEXT` Total duration to run the scanner for (e.g., '7d', '12h', '30m'). Default: '7d' (7 days).
- `--no-gaps-sleep TEXT` Sleep interval when no gaps are found to process (e.g., '1h', '30m'). Default: '1h' (1 hour).
- `--cycle-sleep TEXT` Sleep interval between individual scan attempts/cycles (after a `find-repos` chunk is processed). Default: '1m' (1 minute).
- `--db-url TEXT` Database URL. Can also be set via the `DATABASE_URL` environment variable.

**Behavior of `scan`:**

- The `scan` command runs continuously for the specified `--duration`.
- It repeatedly performs the following cycle:
  1. Checks for active GitHub API rate limits. If a limit is active (either from a previous cycle or by querying the API), it sleeps until the API reset time.
  2. Calculates missing star ranges (gaps) based on `ABS_MIN_STARS`, `ABS_MAX_STARS` from the configuration (`.env` file) and data in the database.
  3. Selects the next chunk from a gap to process (e.g., the lowest star range first).
  4. Constructs and executes the `find-repos` command for that chunk.
  5. Handles the result: If `find-repos` signaled an API limit, `scan` will wait until the API reset time. If no gaps were found, it sleeps for `no-gaps-sleep`. Otherwise, it sleeps for `cycle-sleep`.
- The loop continues until the total `--duration` is reached.

**Example for `scan`:**

Run the scanner orchestrator for 24 hours, checking for new gaps every 30 minutes if none are found, and pausing 2 minutes between processing individual star chunks:

```sh
poetry run untestables scan --duration 24h --no-gaps-sleep 30m --cycle-sleep 2m
```

### Results

Results from both `find-repos` and the `scan` (via `find-repos`) are stored in a database for further analysis. The database tracks:

- Repository metadata (name, description, stars, URL, language, creation/push/update times)
- Test coverage status (missing test directories, files, configs, CI/CD, README mentions)
- Last scan timestamp for each repository.

### Environment Variables

The following environment variables are used:

- `GITHUB_TOKEN`: (Required) Your GitHub personal access token.
- `DATABASE_URL`: (Required) URL for the database connection (e.g., `postgresql://user:pass@host/db` or `sqlite:///./untestables.db`).
- `ABS_MIN_STARS`: (Optional) The absolute minimum star count for the entire project scope when identifying gaps. Default: 0.
- `ABS_MAX_STARS`: (Optional) The absolute maximum star count for the entire project scope. Default: 1,000,000.
- `DEFAULT_CHUNK_SIZE`: (Optional) The size of star chunks the `AnalyzerService` (used by `scan`) will break large gaps into. Default: 100.
- `SCANNER_COMMAND`: (Optional) The base command used by `AnalyzerService` to invoke the scanner. Default: `poetry run untestables find-repos`. This typically does not need to be changed.

These can be set in a `.env` file in the project root.

### Database Migrations

The project uses Alembic for database migrations. Here's how to work with migrations:

1. Run migrations:

   ```sh
   poetry run alembic upgrade head
   ```

2. Create a new migration:

   ```sh
   poetry run alembic revision -m "description of changes"
   ```

3. Roll back one migration:

   ```sh
   poetry run alembic downgrade -1
   ```

4. Roll back all migrations:

   ```sh
   poetry run alembic downgrade base
   ```

5. View migration history:
   ```sh
   poetry run alembic history
   ```

Migration files are stored in the `migrations/versions` directory. Always review migration files before applying them to ensure they make the expected changes.
