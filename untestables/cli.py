import click
from typing import Optional

@click.command()
@click.option('--min-stars', type=int, default=5, help='Minimum number of stars')
@click.option('--max-stars', type=int, default=1000, help='Maximum number of stars')
@click.option('--query', type=str, help='Additional search query terms')
@click.option('--output', type=click.Choice(['csv', 'json', 'md']), default='md', help='Output format')
def main(min_stars: int, max_stars: int, query: Optional[str], output: str) -> None:
    """Find Python repositories that need unit tests."""
    click.echo(f"Searching for repositories with {min_stars} to {max_stars} stars")
    if query:
        click.echo(f"Additional search terms: {query}")
    click.echo(f"Output format: {output}")

if __name__ == '__main__':
    main() 