from selenium.webdriver.remote.webelement import WebElement
from typing import Optional, Dict, Any, List
import re
import logging

logger = logging.getLogger(__name__)

class KworkPriceParser:
    """A class to handle price extraction from Kwork project cards."""
    
    # Common price-related class names and attributes
    PRICE_SELECTORS = [
        # Priority selectors (most specific)
        ".project-price",
        ".wants-card__price",
        ".wants-card__price-title",
        
        # Data attributes
        "[data-test='price']",
        "[data-test-id='price']",
        "[data-price]",
        
        # Class patterns
        "[class*='price']",
        "[class*='budget']",
        "[class*='cost']",
        "[class*='amount']",
        
        # Mobile versions
        "[class*='mobile-price']",
        
        # Currency indicators
        "[class*='currency']",
        
        # Generic value indicators
        "[class*='value']",
        "[class*='sum']",
    ]
    
    # Patterns to clean up price text
    PRICE_CLEANUP_PATTERNS = [
        (r'\s+', ' '),                   # Normalize whitespace
        (r'[^\d\s\-–—,.]', ''),        # Remove non-numeric characters except spaces, hyphens, and decimal points
        (r'\s+', ' '),                   # Normalize whitespace again after cleanup
    ]
    
    @classmethod
    def extract_price(cls, element: WebElement) -> Optional[str]:
        """
        Extract and normalize price from a project card element.
        
        Args:
            element: WebElement containing the project card
            
        Returns:
            str: Normalized price text or None if not found
        """
        price_text = cls._find_price_text(element)
        if not price_text:
            return None
            
        return cls._normalize_price(price_text)
    
    @classmethod
    def _find_price_text(cls, element: WebElement) -> Optional[str]:
        """Find price text using multiple selectors."""
        for selector in cls.PRICE_SELECTORS:
            try:
                price_elements = element.find_elements(By.CSS_SELECTOR, selector)
                for elem in price_elements:
                    price_text = elem.text.strip()
                    if not price_text:
                        continue
                        
                    logger.debug(f"Found potential price text: {price_text} (selector: {selector})")
                    
                    # Skip elements that are too long to be prices
                    if len(price_text) > 50:
                        logger.debug("Skipping: Text too long to be a price")
                        continue
                        
                    # Skip elements that don't contain any digits
                    if not any(char.isdigit() for char in price_text):
                        logger.debug("Skipping: No digits found")
                        continue
                        
                    # If we found a price-like text, return it
                    if cls._looks_like_price(price_text):
                        logger.info(f"✅ Found price text: {price_text}")
                        return price_text
                        
            except Exception as e:
                logger.debug(f"Error checking selector {selector}: {e}")
                continue
                
        logger.warning("⚠️ No valid price text found in element")
        return None
    
    @classmethod
    def _looks_like_price(cls, text: str) -> bool:
        """Check if text looks like a price."""
        # Check for common price patterns
        price_patterns = [
            r'\d+\s*[\-–—]\s*\d+',  # Range: 1000-2000
            r'\d+\s*[\.,]\s*\d+',    # Decimal: 1,000 or 1.000
            r'\d+\s*[рr]\b',         # With currency: 1000р
            r'\d+\s*[рr]\.',         # With currency and dot: 1000р.
            r'\$\s*\d+',              # $1000
            r'\d+\s*USD',              # 1000 USD
            r'\d+\s*руб',              # 1000 руб
            r'\d+\s*₽',                # 1000₽
            r'\b\d{3,}\b',            # Any 3+ digit number
        ]
        
        text = text.lower()
        return any(re.search(pattern, text) for pattern in price_patterns)
    
    @classmethod
    def _normalize_price(cls, price_text: str) -> Optional[str]:
        """
        Normalize price text to a consistent format.
        
        Args:
            price_text: Raw price text
            
        Returns:
            str: Normalized price or None if invalid
        """
        if not price_text:
            return None
            
        try:
            # Apply cleanup patterns
            for pattern, repl in cls.PRICE_CLEANUP_PATTERNS:
                price_text = re.sub(pattern, repl, price_text, flags=re.UNICODE)
            
            price_text = price_text.strip()
            
            # Skip if empty after cleanup
            if not price_text:
                return None
                
            # Replace different dash types with a standard one
            price_text = re.sub(r'[–—]', '-', price_text)
            
            # Normalize decimal separators
            price_text = price_text.replace(',', '.')
            
            # Handle cases like "1.000.000" -> "1000000"
            parts = price_text.split('.')
            if len(parts) > 2:  # If there are multiple dots
                # Check if it's a decimal number with thousand separators
                if all(len(part) == 3 for part in parts[1:-1]):
                    # It's probably using dots as thousand separators
                    price_text = price_text.replace('.', '')
            
            # Final cleanup
            price_text = ' '.join(price_text.split())  # Normalize spaces
            
            return price_text if price_text else None
            
        except Exception as e:
            logger.warning(f"Error normalizing price '{price_text}': {e}")
            return None
