"""
Command-line interface for Kwork integration.
"""
import asyncio
import logging
import typer
from typing import Optional, List

from .tasks import KworkPoller
from .service import KworkService

app = typer.Typer()
logger = logging.getLogger(__name__)

# Global poller instance
_poller: Optional[KworkPoller] = None

@app.command()
def start(
    poll_interval: int = typer.Option(
        300,
        "--interval",
        "-i",
        help="Polling interval in seconds"
    )
):
    """Start the Kwork order poller."""
    global _poller
    
    if _poller and _poller.is_running():
        logger.warning("Kwork poller is already running")
        return
    
    _poller = KworkPoller(poll_interval=poll_interval)
    
    try:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(_poller.start())
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down Kwork poller...")
        if _poller:
            loop.run_until_complete(_poller.stop())
    except Exception as e:
        logger.error(f"Error in Kwork poller: {e}", exc_info=True)
    finally:
        if _poller:
            loop.run_until_complete(_poller.stop())
        loop.close()

@app.command()
async def stop():
    """Stop the Kwork order poller."""
    global _poller
    
    if not _poller or not _poller.is_running():
        logger.warning("Kwork poller is not running")
        return
    
    await _poller.stop()
    logger.info("Kwork poller stopped")

@app.command()
async def test_connection():
    """Test connection to Kwork API."""
    from .api import KworkAPI
    
    try:
        async with KworkAPI() as api:
            # Try to fetch recent orders
            orders = await api.get_recent_orders(per_page=1)
            if orders.get("data", {}).get("list"):
                typer.echo("✅ Successfully connected to Kwork API")
                return
            
            typer.echo("⚠️ Connected to Kwork API but no orders found")
            
    except Exception as e:
        typer.echo(f"❌ Failed to connect to Kwork API: {e}", err=True)
        raise typer.Exit(1)

@app.command()
async def create_filter(
    name: str = typer.Argument(..., help="Filter name"),
    keywords: List[str] = typer.Option(
        None, "--keyword", "-k", 
        help="Keywords to include (can be used multiple times)"
    ),
    categories: List[int] = typer.Option(
        None, "--category", "-c",
        help="Category IDs to include (can be used multiple times)"
    ),
    min_price: Optional[float] = typer.Option(
        None, "--min-price",
        help="Minimum order price"
    ),
    max_price: Optional[float] = typer.Option(
        None, "--max-price",
        help="Maximum order price"
    )
):
    """Create a new Kwork filter."""
    service = KworkService()
    
    try:
        filter_ = await service.create_filter(
            name=name,
            keywords=keywords,
            categories=categories,
            min_price=min_price,
            max_price=max_price
        )
        
        typer.echo(f"✅ Created filter: {filter_.name} (ID: {filter_.id})")
        
    except Exception as e:
        typer.echo(f"❌ Failed to create filter: {e}", err=True)
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
