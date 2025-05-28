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

### Example

Find Python repos with 10–500 stars:

```sh
poetry run untestables --min-stars 10 --max-stars 500
```

Results are stored in a database for further analysis.
