"""
Management script for Kwork integration.
"""
# Load environment variables from .env file before any other imports
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Now import other modules
import asyncio
from typing import List, Optional

import typer
from rich.console import Console
from rich.table import Table, box
from src.kwork.service import KworkService
from src.kwork.tasks import KworkPoller
from src.database.session import init_db, async_session
from src.kwork.models import KworkFilter

app = typer.Typer()
console = Console()

# Global poller instance
_poller: Optional[KworkPoller] = None

@app.command()
def start(
    poll_interval: int = typer.Option(
        300,
        "--interval",
        "-i",
        help="Polling interval in seconds"
    ),
    use_node_bridge: bool = typer.Option(
        False,
        "--use-node-bridge",
        help="Use Node.js bridge for authentication"
    )
):
    """Start the Kwork order poller."""
    global _poller
    
    async def _start():
        global _poller
        
        if _poller and _poller.is_running():
            console.print("[yellow]Kwork poller is already running[/yellow]")
            return
        
        # Initialize database
        await init_db()
        
        # Set environment variable for Node.js bridge if needed
        if use_node_bridge:
            os.environ["USE_NODE_BRIDGE"] = "1"
            console.print("🔌 [blue]Using Node.js bridge for Kwork authentication[/blue]")
        
        _poller = KworkPoller(poll_interval=poll_interval)
        
        try:
            # Start Telegram bot if available
            try:
                from src.bot.telegram_bot import run_bot
                bot_task = asyncio.create_task(run_bot())
                console.print("🤖 [green]Telegram bot started[/green]")
            except Exception as e:
                console.print(f"⚠️ [yellow]Failed to start Telegram bot: {e}[/yellow]")
                bot_task = None
            
            console.print("🚀 [green]Starting Kwork poller...[/green]")
            console.print(f"📡 Polling interval: {poll_interval} seconds")
            console.print("Press Ctrl+C to stop\n")
            
            await _poller.start()
            
            # Keep the poller running
            while _poller and _poller.is_running():
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            console.print("\n🛑 [yellow]Stopping Kwork poller...[/yellow]")
        except Exception as e:
            console.print(f"❌ [red]Error in Kwork poller: {e}[/red]")
            console.print("\nStack trace:", exc_info=True)
        finally:
            # Stop the poller if it's running
            if _poller:
                await _poller.stop()
                _poller = None
            
            # Cancel the bot task if it exists
            if 'bot_task' in locals() and bot_task:
                bot_task.cancel()
                try:
                    await bot_task
                except asyncio.CancelledError:
                    console.print("🛑 [yellow]Telegram bot stopped[/yellow]")
    
    # Run the async function
    asyncio.run(_start())

@app.command()
def stop():
    """Stop the Kwork order poller."""
    global _poller
    
    async def _stop():
        global _poller
        
        if not _poller or not _poller.is_running():
            console.print("[yellow]Kwork poller is not running[/yellow]")
            return
        
        try:
            console.print("🛑 [yellow]Stopping Kwork poller...[/yellow]")
            await _poller.stop()
            console.print("✅ [green]Kwork poller stopped[/green]")
        except Exception as e:
            console.print(f"❌ [red]Error stopping poller: {e}[/red]")
            raise typer.Exit(1)
    
    # Run the async function
    asyncio.run(_stop())

@app.command()
def status():
    """Show status of the Kwork integration."""
    global _poller
    
    async def _get_status():
        global _poller
        
        try:
            # Initialize database
            console.print("🔍 Initializing database...", style="yellow")
            await init_db()
            
            # Get stats
            from sqlalchemy import select, func, text
            from src.kwork.models import KworkOrder, KworkReply, KworkFilter
            
            console.print("📊 Fetching statistics...", style="yellow")
            
            async with async_session() as session:
                # Count orders
                try:
                    result = await session.execute(select(func.count()).select_from(KworkOrder))
                    order_count = result.scalar() or 0
                except Exception as e:
                    console.print(f"❌ Error counting orders: {e}", style="red")
                    order_count = 0
                
                # Count replies
                try:
                    result = await session.execute(select(func.count()).select_from(KworkReply))
                    reply_count = result.scalar() or 0
                except Exception as e:
                    console.print(f"❌ Error counting replies: {e}", style="red")
                    reply_count = 0
                
                # Count active filters
                try:
                    result = await session.execute(
                        select(func.count()).select_from(KworkFilter).where(KworkFilter.is_active == True)
                    )
                    active_filter_count = result.scalar() or 0
                except Exception as e:
                    console.print(f"❌ Error counting filters: {e}", style="red")
                    active_filter_count = 0
            
            # Get poller status
            poller_status = "Running" if _poller and _poller.is_running() else "Stopped"
            
            # Create table
            table = Table(title="[bold cyan]Kwork Integration Status[/bold cyan]", show_header=False, show_lines=True, box=box.ROUNDED)
            table.add_column("Metric", style="cyan", no_wrap=True)
            table.add_column("Value", style="green")
            
            table.add_row("🔵 Poller Status", f"[bold]{poller_status}[/bold]")
            table.add_row("📦 Orders in Database", f"[bold]{order_count}[/bold]")
            table.add_row("📤 Replies Sent", f"[bold]{reply_count}[/bold]")
            table.add_row("⚙️ Active Filters", f"[bold]{active_filter_count}[/bold]")
            
            console.print()
            console.print(table)
            console.print("\n✅ [green]Status check completed successfully[/green]")
            
        except Exception as e:
            console.print(f"\n❌ [bold red]Error getting status:[/bold red] {e}")
            import traceback
            console.print(traceback.format_exc())
            raise typer.Exit(1)
    
    # Run the async function
    try:
        asyncio.run(_get_status())
    except Exception as e:
        console.print(f"\n❌ [bold red]Fatal error:[/bold red] {e}")
        raise typer.Exit(1)

@app.command()
def test_connection():
    """Test connection to Kwork API."""
    from src.kwork.api import KworkAPI
    
    async def _test_connection():
        token = os.getenv("KWORK_TOKEN")
        if not token or token == "your_kwork_token_here":
            console.print("❌ [red]KWORK_TOKEN is not set in .env file[/red]")
            raise typer.Exit(1)
        
        try:
            async with KworkAPI(token) as api:
                with console.status("Testing connection to Kwork API..."):
                    result = await api.get_recent_orders(per_page=1)
                    
                if result.get("data", {}).get("list"):
                    console.print("✅ [green]Successfully connected to Kwork API[/green]")
                    return
                
                console.print("⚠️ [yellow]Connected but no orders found[/yellow]")
                
        except Exception as e:
            console.print(f"❌ [red]Error connecting to Kwork API: {e}[/red]")
            raise typer.Exit(1)
    
    # Run the async function
    asyncio.run(_test_connection())

@app.command()
def create_filter(
    name: str = typer.Option(..., "--name", "-n", help="Filter name"),
    keywords: str = typer.Option(..., "--keywords", "-k", help="Comma-separated list of keywords"),
    min_price: int = typer.Option(None, "--min-price", "-p", help="Minimum price in rubles"),
    max_price: int = typer.Option(None, "--max-price", "-m", help="Maximum price in rubles"),
    categories: str = typer.Option("", "--categories", "-c", help="Comma-separated list of category IDs"),
    is_active: bool = typer.Option(True, "--active/--inactive", help="Whether the filter is active"),
):
    """Create a new Kwork filter."""
    async def _create_filter():
        # Initialize database
        await init_db()
        
        # Create filter
        filter_data = {
            "name": name,
            "keywords": keywords,
            "min_price": min_price,
            "max_price": max_price,
            "categories": categories.split(",") if categories else [],
            "is_active": is_active
        }
        
        async with async_session() as session:
            try:
                # Create new filter
                new_filter = KworkFilter(**filter_data)
                session.add(new_filter)
                await session.commit()
                await session.refresh(new_filter)
                
                console.print(f"✅ [green]Created new filter: {new_filter.name} (ID: {new_filter.id})[/green]")
                return new_filter
                
            except Exception as e:
                await session.rollback()
                console.print(f"❌ [red]Error creating filter: {e}[/red]")
                raise typer.Exit(1)
    
    # Run the async function
    asyncio.run(_create_filter())

@app.command()
def list_filters():
    """List all Kwork filters."""
    from sqlalchemy import select
    from src.kwork.models import KworkFilter
    
    async def _list_filters():
        # Initialize database
        await init_db()
        
        async with async_session() as session:
            # Get all filters
            result = await session.execute(select(KworkFilter).order_by(KworkFilter.name))
            filters = result.scalars().all()
        
        if not filters:
            console.print("[yellow]No filters found. Create one with 'python manage_kwork.py create-filter'[/yellow]")
            return
        
        # Create table
        table = Table(title="Kwork Filters", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="dim")
        table.add_column("Name")
        table.add_column("Keywords")
        table.add_column("Min Price")
        table.add_column("Max Price")
        table.add_column("Active", justify="center")
        table.add_column("Created At", style="dim")
        
        for f in filters:
            table.add_row(
                str(f.id),
                f.name,
                f.keywords[:30] + ("..." if len(f.keywords) > 30 else ""),
                str(f.min_price) if f.min_price is not None else "-",
                str(f.max_price) if f.max_price is not None else "-",
                "✅" if f.is_active else "❌",
                f.created_at.strftime("%Y-%m-%d %H:%M") if f.created_at else "-"
            )
        
        console.print(table)
    
    # Run the async function
    asyncio.run(_list_filters())

async def run_async():
    """Run the Typer app with proper async handling."""
    try:
        # This will run the async commands
        app()
    except Exception as e:
        console.print(f"❌ [red]Error: {e}[/red]")
        raise typer.Exit(1)

def run():
    """Run the async app."""
    asyncio.run(run_async())

if __name__ == "__main__":
    import asyncio
    
    # Run the async app
    try:
        run()
    except KeyboardInterrupt:
        console.print("\n👋 [yellow]Goodbye![/yellow]")
    except Exception as e:
        console.print(f"❌ [red]Unexpected error: {e}[/red]")
        raise typer.Exit(1)
