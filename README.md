# Mission Untestable

A tool to find Python repositories that need unit tests.

## Command-Line Interface (CLI)

You can run the CLI using Poetry:

```sh
poetry run untestables [OPTIONS]
```

### Options

- `--min-stars INTEGER` Minimum number of stars (default: 5)
- `--max-stars INTEGER` Maximum number of stars (default: 1000)
- `--rescan-days INTEGER` Re-scan repositories that were last scanned more than this many days ago
- `--force-rescan` Force re-scan of all repositories, ignoring last scan time

### Repository Scanning Behavior

By default, the tool will only scan repositories that haven't been scanned before. This helps minimize API calls and processing time. You can control this behavior using the following options:

- Without any options: Only scan new repositories
- With `--rescan-days`: Re-scan repositories that haven't been scanned in the specified number of days
- With `--force-rescan`: Scan all repositories regardless of when they were last scanned

### Examples

Find new Python repos with 10–500 stars:

```sh
poetry run untestables --min-stars 10 --max-stars 500
```

Re-scan repositories that haven't been checked in 30 days:

```sh
poetry run untestables --rescan-days 30
```

Force re-scan of all repositories in a specific star range:

```sh
poetry run untestables --min-stars 10 --max-stars 50 --force-rescan
```

### Results

Results are stored in a database for further analysis. The database tracks:

- Repository metadata (name, description, stars, URL)
- Test coverage status (missing test directories, files, configs, etc.)
- Last scan timestamp

### Environment Variables

The following environment variables are required:

- `GITHUB_TOKEN`: Your GitHub personal access token
- `DATABASE_URL`: URL for the database connection

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
