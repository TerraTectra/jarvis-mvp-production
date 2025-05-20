"""
Interactive console for testing Kwork API integration.
"""
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm

from src.kwork.api import KworkAPI
from src.kwork.service import KworkService
from src.database.session import init_db, async_session

console = Console()

def print_header():
    """Print the application header."""
    console.print("\n[bold blue]Kwork API Console[/bold blue]")
    console.print("=" * 50 + "\n")

async def test_connection(api: KworkAPI):
    """Test connection to Kwork API."""
    with console.status("Testing connection to Kwork API..."):
        try:
            result = await api.get_recent_orders(per_page=1)
            if result.get("data", {}).get("list"):
                console.print("✅ [green]Successfully connected to Kwork API[/green]")
                return True
            else:
                console.print("⚠️ [yellow]Connected but no orders found[/yellow]")
                return True
        except Exception as e:
            console.print(f"❌ [red]Connection failed: {e}[/red]")
            return False

async def list_orders(api: KworkAPI, limit: int = 5):
    """List recent Kwork orders."""
    with console.status(f"Fetching {limit} recent orders..."):
        try:
            result = await api.get_recent_orders(per_page=limit)
            orders = result.get("data", {}).get("list", [])
            
            if not orders:
                console.print("No orders found.")
                return
            
            # Create a table
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("ID", style="dim")
            table.add_column("Title")
            table.add_column("Price")
            table.add_column("Category")
            table.add_column("Replies")
            
            for order in orders:
                table.add_row(
                    str(order.get("id")),
                    order.get("name", "N/A"),
                    f"{order.get('price', {}).get('amount', '?')} {order.get('price', {}).get('currency', '')}",
                    order.get("category", {}).get("name", "N/A"),
                    str(order.get("replies_count", 0))
                )
            
            console.print(table)
            
        except Exception as e:
            console.print(f"[red]Error fetching orders: {e}[/red]")

async def view_order(api: KworkAPI, order_id: str):
    """View details of a specific order."""
    with console.status(f"Fetching order {order_id}..."):
        try:
            order = await api.get_order_details(order_id)
            if not order:
                console.print(f"[yellow]Order {order_id} not found[/yellow]")
                return
            
            console.print(f"\n[bold]{order.get('name', 'N/A')}[/bold]")
            console.print(f"ID: {order.get('id')}")
            console.print(f"Price: {order.get('price', {}).get('amount', '?')} {order.get('price', {}).get('currency', '')}")
            console.print(f"Category: {order.get('category', {}).get('name', 'N/A')}")
            console.print(f"Views: {order.get('views', 0)}")
            console.print(f"Replies: {order.get('replies_count', 0)}")
            console.print(f"Published: {order.get('published_at', 'N/A')}")
            console.print("\n[underline]Description:[/underline]")
            console.print(order.get('description', 'No description')[:500] + (order.get('description', '')[500:] and '...'))
            
        except Exception as e:
            console.print(f"[red]Error fetching order: {e}[/red]")

async def send_reply(api: KworkAPI, order_id: str, message: str, price: float, days: int):
    """Send a reply to an order."""
    if not message or not price or not days:
        console.print("[red]Message, price, and days are required[/red]")
        return
    
    if not Confirm.ask(f"Send reply to order {order_id} for {price} RUB?"):
        return
    
    with console.status("Sending reply..."):
        try:
            result = await api.send_reply(
                order_id=order_id,
                message=message,
                price=price,
                days=days
            )
            console.print("✅ [green]Reply sent successfully![/green]")
            console.print(result)
        except Exception as e:
            console.print(f"[red]Error sending reply: {e}[/red]")

async def main():
    """Main entry point for the Kwork console."""
    # Initialize database
    await init_db()
    
    # Check for Kwork token
    token = os.getenv("KWORK_TOKEN")
    if not token or token == "your_kwork_token_here":
        console.print("[red]KWORK_TOKEN is not set in .env file[/red]")
        return
    
    # Initialize API client
    async with KworkAPI(token) as api:
        # Test connection
        if not await test_connection(api):
            return
        
        # Main menu loop
        while True:
            print_header()
            console.print("1. List recent orders")
            console.print("2. View order details")
            console.print("3. Send reply to order")
            console.print("4. Exit")
            
            choice = Prompt.ask("\nSelect an option", choices=["1", "2", "3", "4"])
            
            if choice == "1":
                limit = int(Prompt.ask("How many orders to show?", default="5"))
                await list_orders(api, limit)
            
            elif choice == "2":
                order_id = Prompt.ask("Enter order ID")
                await view_order(api, order_id)
            
            elif choice == "3":
                order_id = Prompt.ask("Enter order ID")
                message = Prompt.ask("Enter your message")
                price = float(Prompt.ask("Enter your price (RUB)"))
                days = int(Prompt.ask("Enter days to complete"))
                await send_reply(api, order_id, message, price, days)
            
            elif choice == "4":
                console.print("\nGoodbye! 👋\n")
                break
            
            # Pause before clearing screen
            if Confirm.ask("\nContinue?", default=True):
                console.clear()
            else:
                break

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\nOperation cancelled by user")
    except Exception as e:
        console.print(f"\n[red]An error occurred: {e}[/red]", file=sys.stderr)
