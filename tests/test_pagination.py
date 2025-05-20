"""Tests for the pagination module."""
from unittest.mock import patch, MagicMock
import pytest

from src.integrations.pagination import KworkPagination, PageInfo, PageInfo


class TestKworkPagination:
    """Test cases for KworkPagination class."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.base_url = "https://kwork.ru/projects"
        self.pagination = KworkPagination(base_url=self.base_url)
    
    def test_get_page_url_first_page(self):
        """Test generating URL for the first page."""
        url = self.pagination.get_page_url(1)
        assert url == "https://kwork.ru/projects"
    
    def test_get_page_url_second_page(self):
        """Test generating URL for the second page."""
        url = self.pagination.get_page_url(2)
        assert url == "https://kwork.ru/projects?page=2"
    
    def test_get_page_url_with_existing_params(self):
        """Test generating URL with existing query parameters."""
        pagination = KworkPagination(
            base_url="https://kwork.ru/projects?category=web-development"
        )
        url = pagination.get_page_url(2)
        assert url == "https://kwork.ru/projects?category=web-development&page=2"
    
    def test_get_page_url_with_filters(self):
        """Test generating URL with additional filters."""
        filters = {
            "price_min": 1000,
            "price_max": 5000,
            "categories": ["web-development", "design"],
        }
        url = self.pagination.get_page_url(1, **filters)
        assert "price_min=1000" in url
        assert "price_max=5000" in url
        assert "categories=web-development" in url or "categories=design" in url
    
    def test_parse_page_info_first_page(self):
        """Test parsing pagination info from the first page."""
        html = """
        <div class="pager">
            <span class="active">1</span>
            <a href="/projects?page=2">2</a>
            <a href="/projects?page=3">3</a>
            <a href="/projects?page=2" class="next">Следующая</a>
        </div>
        """
        page_info = self.pagination.parse_page_info(html)
        
        assert page_info.current_page == 1
        assert page_info.total_pages == 3
        assert page_info.has_next is True
        assert page_info.next_page_url == "https://kwork.ru/projects?page=2"
    
    def test_parse_page_info_middle_page(self):
        """Test parsing pagination info from a middle page."""
        html = """
        <div class="pager">
            <a href="/projects?page=1">1</a>
            <span class="active">2</span>
            <a href="/projects?page=3">3</a>
            <a href="/projects?page=3" class="next">Следующая</a>
        </div>
        """
        page_info = self.pagination.parse_page_info(html)
        
        assert page_info.current_page == 2
        assert page_info.total_pages == 3
        assert page_info.has_next is True
        assert page_info.next_page_url == "https://kwork.ru/projects?page=3"
    
    def test_parse_page_info_last_page(self):
        """Test parsing pagination info from the last page."""
        html = """
        <div class="pager">
            <a href="/projects?page=1">1</a>
            <a href="/projects?page=2">2</a>
            <span class="active">3</span>
        </div>
        """
        page_info = self.pagination.parse_page_info(html)
        
        assert page_info.current_page == 3
        assert page_info.total_pages == 3
        assert page_info.has_next is False
        assert page_info.next_page_url is None
    
    def test_parse_page_info_single_page(self):
        """Test parsing pagination info when there's only one page."""
        html = "<div class='pager'><span class='active'>1</span></div>"
        page_info = self.pagination.parse_page_info(html)
        
        assert page_info.current_page == 1
        assert page_info.total_pages == 1
        assert page_info.has_next is False
        assert page_info.next_page_url is None
    
    def test_parse_page_info_no_pagination(self):
        """Test parsing when there's no pagination element."""
        html = "<div>No pagination here</div>"
        page_info = self.pagination.parse_page_info(html)
        
        assert page_info.current_page == 1
        assert page_info.total_pages == 1
        assert page_info.has_next is False
        assert page_info.next_page_url is None
    
    @patch('src.integrations.pagination.requests.get')
    def test_get_total_pages(self, mock_get):
        """Test getting total pages by making a request."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.text = """
        <div class="pager">
            <a href="/projects?page=1">1</a>
            <a href="/projects?page=2">2</a>
            <span class="active">3</span>
        </div>
        """
        mock_get.return_value = mock_response
        
        # Test getting total pages
        total_pages = self.pagination.get_total_pages()
        
        assert total_pages == 3
        mock_get.assert_called_once_with(
            self.base_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
    
    def test_extract_project_links(self):
        """Test extracting project links from HTML."""
        html = """
        <div class="wants-list">
            <div class="card">
                <a href="/project/123" class="wants-card__header-title">Project 1</a>
            </div>
            <div class="card">
                <a href="/project/456" class="wants-card__header-title">Project 2</a>
            </div>
        </div>
        """
        links = self.pagination.extract_project_links(html)
        
        assert len(links) == 2
        assert links[0] == "https://kwork.ru/project/123"
        assert links[1] == "https://kwork.ru/project/456"
    
    def test_extract_project_links_no_links(self):
        """Test extracting project links when there are no links."""
        html = "<div class='wants-list'></div>"
        links = self.pagination.extract_project_links(html)
        
        assert len(links) == 0
    
    def test_parse_page_info_with_ellipsis(self):
        """Test parsing pagination with ellipsis in the middle."""
        html = """
        <div class="pager">
            <a href="/projects?page=1">1</a>
            <a href="/projects?page=2">2</a>
            <span class="active">3</span>
            <a href="/projects?page=4">4</a>
            <a href="/projects?page=5">5</a>
            <span class="dots">...</span>
            <a href="/projects?page=10">10</a>
            <a href="/projects?page=4" class="next">Следующая</a>
        </div>
        """
        page_info = self.pagination.parse_page_info(html)
        
        assert page_info.current_page == 3
        assert page_info.total_pages == 10
        assert page_info.has_next is True
        assert page_info.next_page_url == "https://kwork.ru/projects?page=4"
    
    def test_parse_page_info_with_relative_urls(self):
        """Test parsing pagination with relative URLs."""
        pagination = KworkPagination(base_url="https://kwork.ru/projects")
        
        html = """
        <div class="pager">
            <a href="/projects?page=1">1</a>
            <span class="active">2</span>
            <a href="/projects?page=3">3</a>
            <a href="/projects?page=3" class="next">Следующая</a>
        </div>
        """
        page_info = pagination.parse_page_info(html)
        
        assert page_info.current_page == 2
        assert page_info.total_pages == 3
        assert page_info.has_next is True
        assert page_info.next_page_url == "https://kwork.ru/projects?page=3"
    
    def test_parse_page_info_with_full_urls(self):
        """Test parsing pagination with full URLs."""
        html = """
        <div class="pager">
            <a href="https://kwork.ru/projects?page=1">1</a>
            <span class="active">2</span>
            <a href="https://kwork.ru/projects?page=3">3</a>
            <a href="https://kwork.ru/projects?page=3" class="next">Следующая</a>
        </div>
        """
        page_info = self.pagination.parse_page_info(html)
        
        assert page_info.current_page == 2
        assert page_info.total_pages == 3
        assert page_info.has_next is True
        assert page_info.next_page_url == "https://kwork.ru/projects?page=3"
    
    def test_parse_page_info_with_complex_urls(self):
        """Test parsing pagination with complex URLs and parameters."""
        pagination = KworkPagination(
            base_url="https://kwork.ru/projects?category=web-development&price_min=1000"
        )
        
        html = """
        <div class="pager">
            <a href="/projects?category=web-development&price_min=1000">1</a>
            <span class="active">2</span>
            <a href="/projects?category=web-development&price_min=1000&page=3">3</a>
            <a href="/projects?category=web-development&price_min=1000&page=3" class="next">Следующая</a>
        </div>
        """
        page_info = pagination.parse_page_info(html)
        
        assert page_info.current_page == 2
        assert page_info.total_pages == 3
        assert page_info.has_next is True
        assert page_info.next_page_url == "https://kwork.ru/projects?category=web-development&price_min=1000&page=3"
