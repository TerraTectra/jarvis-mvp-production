from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from typing import Dict, Any, Optional, List
import logging
import sys
import os

# Add the src directory to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations.kwork_price_parser import KworkPriceParser
from src.integrations.date_utils import parse_kwork_date

logger = logging.getLogger(__name__)

class KworkParser:
    """Parser for Kwork project cards."""
    
    def __init__(self, base_url: str = "https://kwork.ru"):
        """Initialize the parser."""
        self.base_url = base_url.rstrip("/")
    
    def parse_project_card(self, element: WebElement) -> Dict[str, Any]:
        """
        Parse a single project card element.
        
        Args:
            element: WebElement containing the project card
            
        Returns:
            Dict with parsed project data including title, url, category, 
            price, date_posted, and description
        """
        result = {
            "title": self._extract_title(element),
            "url": self._extract_url(element),
            "category": self._extract_category(element),
            "price": KworkPriceParser.extract_price(element),
            "date_posted": self._extract_date_posted(element),
            "description": self._extract_description(element)
        }
        
        logger.info(f"✅ Successfully parsed project: {result.get('title')}")
        if not result['price']:
            logger.warning("⚠️ No price found for project")
            
        return result
    
    def _extract_title(self, element: WebElement) -> Optional[str]:
        """Extract project title."""
        try:
            title = element.find_element(By.CSS_SELECTOR, ".project-title a, h2 a, [class*='title'] a").text.strip()
            logger.info(f"🔹 Title found: {title}")
            return title
        except Exception as e:
            logger.warning(f"⚠️ Title not found: {e}")
            return None
    
    def _extract_url(self, element: WebElement) -> Optional[str]:
        """Extract project URL."""
        try:
            url_elem = element.find_element(
                By.CSS_SELECTOR, 
                ".project-title a, h2 a, [class*='title'] a, a[href*='/projects/']"
            )
            url = url_elem.get_attribute("href")
            if url and url.startswith("/"):
                url = f"{self.base_url}{url}"
            logger.info(f"🔗 URL found: {url}")
            return url
        except Exception as e:
            logger.warning(f"⚠️ URL not found: {e}")
            return None
    
    def _extract_category(self, element: WebElement) -> Optional[str]:
        """Extract project category."""
        try:
            # Try different selectors for category
            selectors = [
                ".project-category",
                ".category",
                "[class*='category']",
                "[class*='tag']",
                ".wants-card__left > *:first-child"
            ]
            
            for selector in selectors:
                try:
                    cat_elem = element.find_element(By.CSS_SELECTOR, selector)
                    category = cat_elem.text.strip()
                    if category and len(category) < 100:  # Sanity check
                        logger.info(f"🏷️ Category found: {category}")
                        return category
                except:
                    continue
                    
            logger.warning("⚠️ Category not found")
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Error extracting category: {e}")
            return None
            
    def _extract_date_posted(self, element: WebElement) -> Optional[str]:
        """Extract and parse the project posting date."""
        try:
            # Try different selectors for date
            date_selectors = [
                ".wants-card__header-date",
                "span[data-test='date']",
                "div[class*='date']",
                "[class*='time']",
                "[class*='posted']"
            ]
            
            for selector in date_selectors:
                try:
                    date_elem = element.find_element(By.CSS_SELECTOR, selector)
                    date_text = date_elem.text.strip()
                    if date_text:
                        date_iso = parse_kwork_date(date_text)
                        if date_iso:
                            logger.info(f"📅 Дата найдена: {date_iso}")
                            return date_iso
                except Exception:
                    continue
                    
            logger.warning("⚠️ Дата не распознана")
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Error extracting date: {e}")
            return None
            
    def _extract_description(self, element: WebElement, max_length: int = 200) -> Optional[str]:
        """
        Extract the project description.
        
        Args:
            element: WebElement containing the project card
            max_length: Maximum length of the description to return
            
        Returns:
            str: Trimmed description text or None if not found
        """
        try:
            # Try different selectors for description
            desc_selectors = [
                ".wants-card__description-text",
                "p.description",
                "div[class*='desc']",
                "[class*='text']",
                "[class*='content']"
            ]
            
            for selector in desc_selectors:
                try:
                    desc_elements = element.find_elements(By.CSS_SELECTOR, selector)
                    for desc_elem in desc_elements:
                        desc_text = desc_elem.text.strip()
                        if desc_text:
                            # Trim to max_length if needed
                            if len(desc_text) > max_length:
                                desc_text = desc_text[:max_length].rsplit(' ', 1)[0] + '...'
                            logger.info(f"📝 Description found ({len(desc_text)} chars)")
                            return desc_text
                except Exception:
                    continue
                    
            logger.warning("⚠️ Description not found")
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ Error extracting description: {e}")
            return None
