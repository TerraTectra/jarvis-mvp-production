"""Pagination module for Kwork project scraping."""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from loguru import logger


@dataclass
class PageInfo:
    """Represents pagination information."""
    current_page: int
    total_pages: Optional[int] = None
    next_page_url: Optional[str] = None
    has_next: bool = False


class KworkPagination:
    """Handles pagination logic for Kwork project listings."""
    
    def __init__(self, base_url: str = "https://kwork.ru/projects"):
        """Initialize with base URL for project listings."""
        self.base_url = base_url
        self.page_param = "page"
    
    def get_page_url(self, page_number: int, **filters) -> str:
        """
        Generate URL for a specific page with optional filters.
        
        Args:
            page_number: Page number to generate URL for
            **filters: Additional query parameters
            
        Returns:
            str: Full URL for the requested page
        """
        # Start with base URL
        parsed = urlparse(self.base_url)
        query_params = parse_qs(parsed.query)
        
        # Update page number
        query_params[self.page_param] = [str(page_number)]
        
        # Add/update filters
        for key, value in filters.items():
            if value is not None:
                query_params[key] = [str(value)]
        
        # Rebuild URL
        new_query = urlencode(query_params, doseq=True)
        return urlunparse(parsed._replace(query=new_query))
    
    def parse_page_info(self, page_source: str) -> PageInfo:
        """
        Extract pagination information from page HTML.
        
        Args:
            page_source: HTML content of the page
            
        Returns:
            PageInfo: Parsed pagination information
        """
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(page_source, 'html.parser')
        page_info = PageInfo(current_page=1)  # Default to page 1
        
        try:
            # Find pagination container
            pagination = soup.select_one('.pager')
            if not pagination:
                return page_info
                
            # Find current page
            current_page_el = pagination.select_one('.active')
            if current_page_el and current_page_el.text.strip().isdigit():
                page_info.current_page = int(current_page_el.text.strip())
            
            # Find total pages
            page_links = pagination.select('a[href*="page="]')
            if page_links:
                page_numbers = []
                for link in page_links:
                    try:
                        page_num = int(link.text.strip())
                        page_numbers.append(page_num)
                    except (ValueError, AttributeError):
                        continue
                
                if page_numbers:
                    page_info.total_pages = max(page_numbers)
                    page_info.has_next = page_info.current_page < page_info.total_pages
            
            # Find next page URL
            next_link = pagination.select_one('.next a')
            if next_link and 'href' in next_link.attrs:
                page_info.next_page_url = urljoin(self.base_url, next_link['href'])
                
        except Exception as e:
            logger.warning(f"Error parsing pagination: {e}")
        
        return page_info
    
    def get_next_page_url(self, current_page: int, current_url: Optional[str] = None) -> Optional[str]:
        """
        Generate URL for the next page.
        
        Args:
            current_page: Current page number
            current_url: Current page URL (for extracting query params)
            
        Returns:
            Optional[str]: URL for the next page or None if no more pages
        """
        if current_url:
            parsed = urlparse(current_url)
            query_params = parse_qs(parsed.query)
            
            # Remove page parameter to avoid duplicates
            if self.page_param in query_params:
                del query_params[self.page_param]
                
            # Rebuild URL with next page
            next_page = current_page + 1
            query_params[self.page_param] = [str(next_page)]
            new_query = urlencode(query_params, doseq=True)
            return urlunparse(parsed._replace(query=new_query))
        
        # If no current URL, use base URL
        return self.get_page_url(current_page + 1)
    
    @staticmethod
    def extract_project_links(page_source: str) -> List[Dict[str, Any]]:
        """
        Extract project links from a page.
        
        Args:
            page_source: HTML content of the page
            
        Returns:
            List of dicts containing project URLs and IDs
        """
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(page_source, 'html.parser')
        projects = []
        
        # Find all project cards
        project_cards = soup.select('.card, .wants-card')
        
        for card in project_cards:
            try:
                # Try different selectors for project links
                link = card.select_one('a[href^="/projects/"]')
                if not link:
                    continue
                    
                href = link.get('href', '').strip()
                if not href.startswith('/projects/'):
                    continue
                    
                # Extract project ID
                project_id = href.split('/')[-1].split('-')[-1]
                if not project_id.isdigit():
                    continue
                    
                projects.append({
                    'id': int(project_id),
                    'url': f"https://kwork.ru{href}",
                    'raw_html': str(card)
                })
                
            except Exception as e:
                logger.warning(f"Error extracting project link: {e}")
                continue
                
        return projects
