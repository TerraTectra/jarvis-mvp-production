"""
Script to set up initial Kwork filter.
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import List, Optional

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm

from src.kwork.service import KworkService
from src.database.session import init_db

app = typer.Typer()
console = Console()

async def setup_filter_interactive():
    """Interactive setup for Kwork filter."""
    # Initialize database
    await init_db()
    
    console.print("\n[bold blue]Kwork Filter Setup[/bold blue]")
    console.print("=" * 50 + "\n")
    
    # Get filter details
    name = Prompt.ask("Enter filter name")
    
    # Get keywords
    keywords = []
    console.print("\n[bold]Enter keywords to include (one per line, leave empty to finish):[/bold]")
    while True:
        keyword = Prompt.ask("  Keyword").strip()
        if not keyword:
            break
        keywords.append(keyword.lower())
    
    # Get categories
    categories = []
    console.print("\n[bold]Available categories:[/bold]")
    console.print("1. Web Development")
    console.print("2. Design")
    console.print("3. Marketing")
    console.print("4. Text and Content")
    console.print("5. Audio and Video")
    
    console.print("\n[bold]Enter category numbers (comma-separated, leave empty to skip):[/bold]")
    cats = Prompt.ask("  Categories").strip()
    if cats:
        categories = [int(cat.strip()) for cat in cats.split(",") if cat.strip().isdigit()]
    
    # Get price range
    console.print("\n[bold]Price range (in RUB):[/bold]")
    min_price = Prompt.ask("  Minimum price (leave empty for no minimum)", default="")
    max_price = Prompt.ask("  Maximum price (leave empty for no maximum)", default="")
    
    min_price = float(min_price) if min_price else None
    max_price = float(max_price) if max_price else None
    
    # Create filter
    service = KworkService()
    try:
        filter_ = await service.create_filter(
            name=name,
            keywords=keywords,
            categories=categories,
            min_price=min_price,
            max_price=max_price
        )
        
        console.print("\n✅ [green]Filter created successfully![/green]")
        console.print(f"Name: {filter_.name}")
        console.print(f"Keywords: {', '.join(filter_.keywords) if filter_.keywords else 'None'}")
        console.print(f"Categories: {', '.join(str(cat) for cat in filter_.categories) if filter_.categories else 'None'}")
        console.print(f"Price range: {filter_.min_price or 'Any'} - {filter_.max_price or 'Any'} RUB")
        
    except Exception as e:
        console.print(f"\n❌ [red]Error creating filter: {e}[/red]")
        raise typer.Exit(1)

@app.command()
def setup():
    """Interactive setup for Kwork filter."""
    asyncio.run(setup_filter_interactive())

if __name__ == "__main__":
    app()
