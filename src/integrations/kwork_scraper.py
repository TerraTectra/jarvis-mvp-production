"""Async Kwork scraper with browser pool and database integration."""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, AsyncIterator, Tuple
from urllib.parse import urljoin, urlparse

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from loguru import logger

from .browser_pool import BrowserPool, BrowserConfig
from .pagination import KworkPagination
from .kwork_parser import KworkParser
from ..database.kwork_crud import KworkCRUD, ScrapeSession
from ..database.session import async_session


class KworkScraper:
    """Async Kwork scraper with browser pool and database integration."""
    
    def __init__(
        self,
        base_url: str = "https://kwork.ru/projects",
        pool_size: int = 3,
        headless: bool = True,
        max_pages: Optional[int] = None,
        session_id: Optional[int] = None,
        **filters
    ):
        """Initialize the Kwork scraper.
        
        Args:
            base_url: Base URL for Kwork projects
            pool_size: Number of browser instances in the pool
            headless: Run browser in headless mode
            max_pages: Maximum number of pages to scrape (None for no limit)
            session_id: Existing scrape session ID (for resuming)
            **filters: Additional filters (e.g., category, price_min, price_max)
        """
        self.base_url = base_url
        self.pool_size = pool_size
        self.headless = headless
        self.max_pages = max_pages
        self.filters = filters
        
        # Initialize components
        self.pagination = KworkPagination(base_url=base_url)
        self.parser = KworkParser()
        
        # Browser pool will be initialized on first use
        self.browser_pool: Optional[BrowserPool] = None
        
        # Database session and CRUD
        self.db_session = None
        self.crud: Optional[KworkCRUD] = None
        
        # Scraping session
        self.session_id = session_id
        self.session: Optional[ScrapeSession] = None
        
        # Statistics
        self.stats = {
            'pages_scraped': 0,
            'projects_found': 0,
            'new_projects': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None,
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def initialize(self) -> None:
        """Initialize the scraper and its components."""
        # Initialize browser pool
        browser_config = BrowserConfig(
            headless=self.headless,
            window_size=(1920, 1080),
            disable_images=True,
            disable_javascript=False,
        )
        self.browser_pool = BrowserPool(pool_size=self.pool_size, config=browser_config)
        await self.browser_pool.initialize()
        
        # Initialize database session
        self.db_session = async_session()
        self.crud = KworkCRUD(self.db_session)
        
        # Initialize or resume scraping session
        await self._init_scrape_session()
        
        logger.info(f"Initialized KworkScraper with {self.pool_size} browsers")
    
    async def _init_scrape_session(self) -> None:
        """Initialize or resume a scraping session."""
        if self.session_id:
            # Resume existing session
            result = await self.db_session.execute(
                select(ScrapeSession).filter(ScrapeSession.id == self.session_id)
            )
            self.session = result.scalars().first()
            if not self.session:
                raise ValueError(f"Session {self.session_id} not found")
            
            logger.info(f"Resumed scrape session {self.session.id}")
        else:
            # Start new session
            self.session = await self.crud.create_scrape_session(
                max_pages=self.max_pages,
                filters=self.filters
            )
            logger.info(f"Started new scrape session {self.session.id}")
        
        # Update stats from session
        self.stats.update({
            'pages_scraped': self.session.pages_scraped or 0,
            'projects_found': self.session.projects_found or 0,
            'new_projects': self.session.new_projects or 0,
            'errors': self.session.errors_encountered or 0,
            'start_time': self.session.start_time,
        })
    
    async def close(self) -> None:
        """Close the scraper and release resources."""
        # Update session end time and stats
        if self.session and not self.session.end_time:
            self.stats['end_time'] = datetime.utcnow()
            await self.crud.update_scrape_session(
                self.session.id,
                end_time=self.stats['end_time'],
                status='completed' if self.stats['errors'] == 0 else 'failed',
                pages_scraped=self.stats['pages_scraped'],
                projects_found=self.stats['projects_found'],
                new_projects=self.stats['new_projects'],
                errors_encountered=self.stats['errors'],
            )
        
        # Close browser pool
        if self.browser_pool:
            await self.browser_pool.close()
        
        # Close database session
        if self.db_session:
            await self.db_session.close()
        
        logger.info("KworkScraper closed")
    
    async def scrape_projects(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Scrape projects from Kwork.
        
        Args:
            limit: Maximum number of projects to scrape (None for no limit)
            
        Returns:
            List of scraped projects
        """
        if not self.browser_pool or not self.crud:
            raise RuntimeError("Scraper not initialized. Call initialize() first.")
        
        logger.info(f"Starting to scrape projects with filters: {self.filters}")
        self.stats['start_time'] = datetime.utcnow()
        
        projects = []
        current_page = 1
        
        try:
            while True:
                # Check if we've reached the page limit
                if self.max_pages and current_page > self.max_pages:
                    logger.info(f"Reached maximum page limit ({self.max_pages})")
                    break
                    
                # Scrape current page
                page_projects = await self._scrape_page(current_page)
                if not page_projects:
                    logger.info(f"No more projects found on page {current_page}")
                    break
                
                # Process projects
                for project in page_projects:
                    try:
                        # Save to database
                        db_project = await self.crud.upsert_project(project)
                        is_new = db_project.is_processed is False
                        
                        # Update stats
                        self.stats['projects_found'] += 1
                        if is_new:
                            self.stats['new_projects'] += 1
                        
                        # Add to results
                        projects.append(project)
                        
                        # Check if we've reached the project limit
                        if limit and len(projects) >= limit:
                            logger.info(f"Reached project limit ({limit})")
                            return projects
                            
                    except Exception as e:
                        self.stats['errors'] += 1
                        logger.error(f"Error processing project: {e}")
                
                # Update session stats
                self.stats['pages_scraped'] += 1
                await self.crud.update_scrape_session(
                    self.session.id,
                    pages_scraped=self.stats['pages_scraped'],
                    projects_found=self.stats['projects_found'],
                    new_projects=self.stats['new_projects'],
                    errors_encountered=self.stats['errors'],
                )
                
                # Get next page URL
                current_page += 1
                
        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Error during scraping: {e}")
            raise
        
        finally:
            # Update session end time
            self.stats['end_time'] = datetime.utcnow()
            await self.crud.update_scrape_session(
                self.session.id,
                end_time=self.stats['end_time'],
                status='completed' if self.stats['errors'] == 0 else 'failed',
            )
        
        return projects
    
    async def _scrape_page(self, page_number: int) -> List[Dict[str, Any]]:
        """Scrape a single page of projects.
        
        Args:
            page_number: Page number to scrape
            
        Returns:
            List of project data dictionaries
        """
        if not self.browser_pool:
            raise RuntimeError("Browser pool not initialized")
        
        url = self.pagination.get_page_url(page_number, **self.filters)
        logger.info(f"Scraping page {page_number}: {url}")
        
        async with self.browser_pool.get_browser() as browser:
            try:
                # Load the page
                browser.get(url)
                
                # Wait for projects to load
                WebDriverWait(browser, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".card, .wants-card"))
                )
                
                # Get page source and parse projects
                page_source = browser.page_source
                project_elements = browser.find_elements(By.CSS_SELECTOR, ".card, .wants-card")
                
                # Parse each project
                projects = []
                for element in project_elements:
                    try:
                        project = self.parser.parse_project_card(element)
                        if project:
                            project['page_url'] = url
                            project['scraped_at'] = datetime.utcnow().isoformat()
                            projects.append(project)
                    except Exception as e:
                        self.stats['errors'] += 1
                        logger.error(f"Error parsing project: {e}")
                
                logger.info(f"Found {len(projects)} projects on page {page_number}")
                return projects
                
            except Exception as e:
                self.stats['errors'] += 1
                logger.error(f"Error scraping page {page_number}: {e}")
                # Take a screenshot for debugging
                try:
                    screenshot = browser.get_screenshot_as_png()
                    with open(f"error_page_{page_number}.png", "wb") as f:
                        f.write(screenshot)
                except Exception as screenshot_error:
                    logger.error(f"Failed to take screenshot: {screenshot_error}")
                
                # If it's the first page and we got an error, the site might be blocking us
                if page_number == 1:
                    logger.error("Failed to load the first page. The site might be blocking the request.")
                
                return []


async def scrape_kwork(
    categories: Optional[List[str]] = None,
    price_min: Optional[float] = None,
    price_max: Optional[float] = None,
    max_pages: Optional[int] = 5,
    max_projects: Optional[int] = None,
    headless: bool = True,
    pool_size: int = 3,
) -> List[Dict[str, Any]]:
    """Convenience function to scrape Kwork projects.
    
    Args:
        categories: List of category slugs to filter by
        price_min: Minimum project price
        price_max: Maximum project price
        max_pages: Maximum number of pages to scrape
        max_projects: Maximum number of projects to return
        headless: Run browser in headless mode
        pool_size: Number of browser instances in the pool
        
    Returns:
        List of scraped projects
    """
    # Prepare filters
    filters = {}
    if categories:
        filters['c'] = categories
    if price_min is not None:
        filters['price_min'] = price_min
    if price_max is not None:
        filters['price_max'] = price_max
    
    async with KworkScraper(
        max_pages=max_pages,
        headless=headless,
        pool_size=pool_size,
        **filters
    ) as scraper:
        return await scraper.scrape_projects(limit=max_projects)


if __name__ == "__main__":
    # Example usage
    import asyncio
    
    async def main():
        # Scrape first 2 pages of web development projects
        projects = await scrape_kwork(
            categories=["web-programming"],
            price_min=1000,
            price_max=50000,
            max_pages=2,
            headless=False,  # Set to True in production
            pool_size=2
        )
        
        print(f"\nScraped {len(projects)} projects:")
        for i, project in enumerate(projects, 1):
            print(f"{i}. {project.get('title')} - {project.get('price')}")
    
    asyncio.run(main())
