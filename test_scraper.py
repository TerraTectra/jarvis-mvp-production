"""Test script for the Kwork scraper."""
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime

from loguru import logger
from dotenv import load_dotenv

from src.integrations.kwork_scraper import KworkScraper, scrape_kwork

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


async def test_scraper():
    """Test the Kwork scraper with basic configuration."""
    # Output directory for test results
    output_dir = Path("test_results")
    output_dir.mkdir(exist_ok=True)
    
    # Test configuration
    test_config = {
        "categories": ["web-programming"],
        "price_min": 1000,
        "price_max": 50000,
        "max_pages": 2,
        "headless": False,  # Set to True in CI
        "pool_size": 2,
    }
    
    logger.info("Starting Kwork scraper test...")
    logger.info(f"Test configuration: {json.dumps(test_config, indent=2)}")
    
    # Run the scraper
    start_time = datetime.now()
    
    try:
        # Create a new scraper instance
        async with KworkScraper(
            max_pages=test_config["max_pages"],
            headless=test_config["headless"],
            pool_size=test_config["pool_size"],
            category=test_config["categories"],
            price_min=test_config["price_min"],
            price_max=test_config["price_max"],
        ) as scraper:
            # Scrape projects
            projects = await scraper.scrape_projects()
            
            # Save results
            output_file = output_dir / f"kwork_projects_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(projects, f, ensure_ascii=False, indent=2)
            
            # Print summary
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Test completed in {duration:.2f} seconds")
            logger.info(f"Scraped {len(projects)} projects")
            logger.info(f"Results saved to: {output_file.absolute()}")
            
            # Print first project as sample
            if projects:
                logger.info("\nSample project:")
                sample = projects[0]
                print(json.dumps(sample, ensure_ascii=False, indent=2))
                
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(test_scraper())
