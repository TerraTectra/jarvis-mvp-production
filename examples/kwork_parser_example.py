import logging
import sys
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Add the src directory to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.integrations.kwork_parser import KworkParser

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_driver():
    """Set up and return a configured Chrome WebDriver."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Set up the Chrome driver
    service = Service(executable_path='chromedriver.exe')  # Update this path if needed
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    return driver

def parse_kwork_projects(url: str, max_projects: int = 5):
    """Parse project cards from Kwork.
    
    Args:
        url: URL of the Kwork projects page
        max_projects: Maximum number of projects to parse
    """
    driver = None
    try:
        # Set up the WebDriver
        driver = setup_driver()
        driver.get(url)
        
        # Wait for the page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".card, .wants-card"))
        )
        
        # Find all project cards
        project_cards = driver.find_elements(By.CSS_SELECTOR, ".card, .wants-card")
        logger.info(f"Found {len(project_cards)} project cards")
        
        # Initialize the parser
        parser = KworkParser()
        
        # Parse each project card
        results = []
        for i, card in enumerate(project_cards[:max_projects], 1):
            try:
                logger.info(f"\n--- Parsing project {i} ---")
                result = parser.parse_project_card(card)
                results.append(result)
                
                # Print the parsed data in a clean format
                print("\n" + "="*50)
                print(f"PROJECT #{i}")
                print("="*50)
                print(f"Title:    {result.get('title', 'N/A')}")
                print(f"URL:      {result.get('url', 'N/A')}")
                print(f"Category: {result.get('category', 'N/A')}")
                print(f"Price:    {result.get('price', 'N/A')}")
                print(f"Posted:   {result.get('date_posted', 'N/A')}")
                print("\nDescription:")
                print("-" * 20)
                print(result.get('description', 'N/A'))
                print("")
                
                # Also log the full result as JSON
                import json
                logger.info(f"Parsed project data:\n{json.dumps(result, indent=2, ensure_ascii=False)}")
                
            except Exception as e:
                logger.error(f"Error parsing project {i}: {e}")
                continue
                
        return results
        
    except Exception as e:
        logger.error(f"Error during parsing: {e}")
        return []
        
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    # Example URL - replace with the actual Kwork projects page URL
    kwork_url = "https://kwork.ru/projects"
    
    # Parse projects
    projects = parse_kwork_projects(kwork_url, max_projects=3)
    
    # Print summary
    print("\n" + "="*50)
    print(f"SUMMARY: Parsed {len(projects)} projects")
    print("="*50)
    for i, project in enumerate(projects, 1):
        print(f"{i:2d}. [{project.get('date_posted', '????-??-??')}] "
              f"{project.get('title', 'No title')} - {project.get('price', 'No price')}")
    
    # Save results to a JSON file
    import json
    output_file = "kwork_projects.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(projects, f, ensure_ascii=False, indent=2)
    logger.info(f"\nResults saved to {output_file}")
