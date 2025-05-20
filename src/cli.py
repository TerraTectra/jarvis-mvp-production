"""CLI interface for Kwork scraper."""
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import click
from loguru import logger

from .integrations.kwork_scraper import KworkScraper, scrape_kwork
from .database.kwork_models import Base
from .database.session import engine, async_session

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def cli(ctx, verbose):
    """Kwork Scraper - Scrape projects from kwork.ru"""
    # Set log level based on verbose flag
    log_level = "DEBUG" if verbose else "INFO"
    logger.remove()  # Remove default handler
    logger.add(sys.stderr, level=log_level)
    
    # Store config in context
    ctx.ensure_object(dict)
    ctx.obj['VERBOSE'] = verbose


@cli.command()
@click.option('--output', '-o', type=click.Path(dir_okay=False), help='Output JSON file')
@click.option('--max-pages', type=int, default=5, help='Maximum number of pages to scrape')
@click.option('--max-projects', type=int, help='Maximum number of projects to return')
@click.option('--category', '-c', multiple=True, help='Filter by category slug')
@click.option('--price-min', type=float, help='Minimum project price')
@click.option('--price-max', type=float, help='Maximum project price')
@click.option('--headless/--no-headless', default=True, help='Run browser in headless mode')
@click.option('--pool-size', type=int, default=3, help='Number of browser instances in the pool')
@click.pass_context
def scrape(
    ctx,
    output: Optional[str],
    max_pages: int,
    max_projects: Optional[int],
    category: List[str],
    price_min: Optional[float],
    price_max: Optional[float],
    headless: bool,
    pool_size: int,
):
    """Scrape projects from Kwork."""
    async def run_scraper():
        categories = list(category) if category else None
        
        projects = await scrape_kwork(
            categories=categories,
            price_min=price_min,
            price_max=price_max,
            max_pages=max_pages,
            max_projects=max_projects,
            headless=headless,
            pool_size=pool_size,
        )
        
        # Print summary
        print(f"\nScraped {len(projects)} projects:")
        for i, project in enumerate(projects, 1):
            print(f"{i}. {project.get('title')} - {project.get('price')}")
        
        # Save to file if output path is provided
        if output:
            output_path = Path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert datetime objects to ISO format
            def json_serializer(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(projects, f, ensure_ascii=False, indent=2, default=json_serializer)
            
            print(f"\nResults saved to {output_path.absolute()}")
    
    try:
        asyncio.run(run_scraper())
    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error during scraping: {e}")
        if ctx.obj['VERBOSE']:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation')
@click.pass_context
def initdb(ctx, yes: bool):
    """Initialize the database."""
    async def init_db():
        if not yes:
            click.confirm('This will drop and recreate all database tables. Continue?', abort=True)
        
        async with engine.begin() as conn:
            # Drop all tables
            await conn.run_sync(Base.metadata.drop_all)
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
        
        print("Database initialized successfully")
    
    asyncio.run(init_db())


@cli.command()
@click.option('--limit', type=int, default=10, help='Number of projects to show')
@click.option('--output', type=click.Path(dir_okay=False), help='Output JSON file')
@click.pass_context
def list_projects(ctx, limit: int, output: Optional[str]):
    """List scraped projects from the database."""
    async def list_projects_db():
        async with async_session() as session:
            crud = KworkCRUD(session)
            projects = await crud.get_recent_projects(limit=limit)
            
            if not projects:
                print("No projects found in the database")
                return
            
            # Convert SQLAlchemy objects to dicts
            projects_data = []
            for project in projects:
                project_dict = {
                    'id': project.id,
                    'kwork_id': project.kwork_id,
                    'title': project.title,
                    'url': project.url,
                    'category': project.category,
                    'price': project.price,
                    'date_posted': project.date_posted.isoformat() if project.date_posted else None,
                    'created_at': project.created_at.isoformat(),
                    'updated_at': project.updated_at.isoformat(),
                }
                projects_data.append(project_dict)
                
                # Print project info
                print(f"[{project.id}] {project.title}")
                print(f"  URL: {project.url}")
                print(f"  Price: {project.price}")
                print(f"  Category: {project.category}")
                print(f"  Posted: {project.date_posted}" if project.date_posted else "")
                print()
            
            # Save to file if output path is provided
            if output:
                output_path = Path(output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(projects_data, f, ensure_ascii=False, indent=2)
                
                print(f"\nProjects saved to {output_path.absolute()}")
    
    asyncio.run(list_projects_db())


@cli.command()
@click.option('--chat-id', required=True, help='Telegram chat ID')
@click.option('--token', required=True, help='Telegram bot token')
@click.pass_context
def send_report(ctx, chat_id: str, token: str):
    """Send daily scraping report to Telegram."""
    async def generate_report():
        from datetime import datetime, timedelta
        from telegram import Bot
        
        bot = Bot(token=token)
        
        async with async_session() as session:
            crud = KworkCRUD(session)
            
            # Get stats for the last 24 hours
            yesterday = datetime.utcnow() - timedelta(days=1)
            
            # Get total projects count
            total_projects = await crud.get_active_projects_count()
            
            # Get recent projects
            recent_projects = await crud.get_recent_projects(limit=5)
            
            # Format message
            message = [
                "📊 *Daily Kwork Scraper Report*",
                f"🕒 Generated at: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                "",
                f"📂 *Total Projects:* {total_projects}",
                "",
                "🚀 *Recently Added Projects:*",
            ]
            
            for i, project in enumerate(recent_projects, 1):
                message.append(f"{i}. [{project.title}]({project.url}) - {project.price}")
            
            # Send message
            await bot.send_message(
                chat_id=chat_id,
                text="\n".join(message),
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
    
    try:
        asyncio.run(generate_report())
        print("Report sent successfully")
    except Exception as e:
        logger.error(f"Error sending report: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
