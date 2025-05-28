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
- `--query TEXT` Additional search query terms
- `--output [csv|json|md]` Output format (default: md)

### Examples

Find Python repos with 10–500 stars and output as JSON:

```sh
poetry run untestables --min-stars 10 --max-stars 500 --output json
```

Add a search keyword and output as CSV:

```sh
poetry run untestables --query "machine learning" --output csv
```
