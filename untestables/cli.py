import click
from typing import Optional

@click.command()
@click.option('--min-stars', type=int, default=5, help='Minimum number of stars')
@click.option('--max-stars', type=int, default=1000, help='Maximum number of stars')
def main(min_stars: int, max_stars: int) -> None:
    """Find Python repositories that need unit tests."""
    click.echo(f"Searching for repositories with {min_stars} to {max_stars} stars")

if __name__ == '__main__':
    main() 