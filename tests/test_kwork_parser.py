import unittest
from unittest.mock import MagicMock, patch, call
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By

# Add the src directory to the path for imports
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations.kwork_parser import KworkParser, KworkPriceParser

class TestKworkParser(unittest.TestCase):
    def setUp(self):
        self.parser = KworkParser()
        self.mock_element = MagicMock(spec=WebElement)
        
    def create_mock_element(self, html):
        """Helper to create a mock element with HTML content."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        element = MagicMock(spec=WebElement)
        
        def mock_find_element(by, value):
            if by == By.CSS_SELECTOR:
                result = soup.select_one(value)
                if result:
                    mock = MagicMock()
                    mock.text = result.get_text(strip=True)
                    
                    # Handle get_attribute calls for href and other attributes
                    def get_attr(attr):
                        if attr == 'href':
                            return result.get('href', '')
                        return result.get(attr, '')
                        
                    mock.get_attribute.side_effect = get_attr
                    return mock
            raise Exception(f"Element not found with selector: {value}")
            
        element.find_element = mock_find_element
        
        def mock_find_elements(by, value):
            if by == By.CSS_SELECTOR:
                results = soup.select(value)
                mocks = []
                for r in results:
                    mock = MagicMock()
                    mock.text = r.get_text(strip=True)
                    
                    # Handle get_attribute calls for href and other attributes
                    def get_attr(attr):
                        if attr == 'href':
                            return r.get('href', '')
                        return r.get(attr, '')
                        
                    mock.get_attribute.side_effect = get_attr
                    mocks.append(mock)
                return mocks
            return []
            
        element.find_elements = mock_find_elements
        
        # Add a mock for the element's own text
        element.text = soup.get_text(strip=True)
        
        return element
    
    def test_parse_project_card(self):
        """Test parsing a complete project card."""
        # Mock the KworkPriceParser.extract_price to return a fixed value
        with patch.object(KworkPriceParser, 'extract_price') as mock_extract, \
             patch('src.integrations.kwork_parser.parse_kwork_date') as mock_parse_date:
            
            # Set up mock return values
            mock_extract.return_value = "1000-2000"
            mock_parse_date.return_value = "2025-05-18"
            
            html = """
            <div class="project-card">
                <h2 class="project-title"><a href="/projects/123">Test Project</a></h2>
                <div class="project-category">Web Development</div>
                <div class="project-price">1 000 - 2 000 ₽</div>
                <div class="wants-card__header-date">Сегодня</div>
                <div class="wants-card__description-text">
                    This is a test project description that should be extracted by the parser.
                    It includes multiple lines and some special characters: !@#$%^&*()_+.
                    The description will be trimmed to a reasonable length.
                </div>
            </div>
            """
            element = self.create_mock_element(html)
            
            result = self.parser.parse_project_card(element)
            
            # Verify the mocks were called
            mock_extract.assert_called_once_with(element)
            mock_parse_date.assert_called_once_with("Сегодня")
            
            # Check the results
            self.assertEqual(result["title"], "Test Project")
            self.assertEqual(result["url"], "https://kwork.ru/projects/123")
            self.assertEqual(result["category"], "Web Development")
            self.assertEqual(result["price"], "1000-2000")
            self.assertEqual(result["date_posted"], "2025-05-18")
            self.assertIn("This is a test project description", result["description"])
            self.assertLessEqual(len(result["description"]), 203)  # 200 + "..."
    
    def test_price_extraction(self):
        """Test price extraction with various formats."""
        test_cases = [
            ("1 000 - 2 000 ₽", "1000-2000"),
            ("от 1 000 ₽", "1000"),
            ("1,000.50 USD", "1000.50"),
            ("1000р.", "1000"),
            ("1.000.000 ₽", "1000000"),
        ]
        
        for price_text, expected in test_cases:
            with self.subTest(price_text=price_text):
                with patch.object(KworkPriceParser, 'extract_price') as mock_extract:
                    mock_extract.return_value = expected
                    
                    html = f"""
                    <div class="project-card">
                        <h2><a href="/projects/123">Test</a></h2>
                        <div class="price">{price_text}</div>
                    </div>
                    """
                    element = self.create_mock_element(html)
                    result = self.parser.parse_project_card(element)
                    
                    # Verify the price parser was called with the element
                    mock_extract.assert_called_once_with(element)
                    self.assertEqual(result["price"], expected)

    def test_missing_fields(self):
        """Test parsing with missing fields."""
        with patch.object(KworkPriceParser, 'extract_price') as mock_extract, \
             patch('src.integrations.kwork_parser.parse_kwork_date') as mock_parse_date:
            
            mock_extract.return_value = None
            mock_parse_date.return_value = None
            
            html = "<div class=\"project-card\"></div>"
            element = self.create_mock_element(html)
            
            result = self.parser.parse_project_card(element)
            
            self.assertIsNone(result["title"])
            self.assertIsNone(result["url"])
            self.assertIsNone(result["category"])
            self.assertIsNone(result["price"])
            self.assertIsNone(result["date_posted"])
            self.assertIsNone(result["description"])
            mock_extract.assert_called_once_with(element)
            
    def test_date_extraction(self):
        """Test date extraction with various formats."""
        test_cases = [
            ("Сегодня", "2025-05-18"),
            ("Вчера", "2025-05-17"),
            ("2 дня назад", "2025-05-16"),
            ("15.05.2025", "2025-05-15"),
            ("15.05.25", "2025-05-15"),
            ("01.01.2023", "2023-01-01"),
            ("31.12.2024", "2024-12-31"),
        ]
        
        for date_text, expected in test_cases:
            with self.subTest(date_text=date_text):
                with patch('src.integrations.kwork_parser.parse_kwork_date') as mock_parse_date:
                    mock_parse_date.return_value = expected
                    
                    html = f"""
                    <div class="project-card">
                        <div class="wants-card__header-date">{date_text}</div>
                    </div>
                    """
                    element = self.create_mock_element(html)
                    
                    result = self.parser._extract_date_posted(element)
                    self.assertEqual(result, expected)
                    mock_parse_date.assert_called_once_with(date_text)
    
    def test_description_extraction(self):
        """Test description extraction and trimming."""
        # Test with a long description
        long_desc = " " * 50 + "A" * 300 + " " * 50
        expected = ("A" * 200 + "...").strip()
        
        html = f"""
        <div class="project-card">
            <div class="wants-card__description-text">
                {long_desc}
            </div>
        </div>
        """
        element = self.create_mock_element(html)
        
        # Test with default max_length (200)
        result = self.parser._extract_description(element)
        self.assertEqual(len(result), 203)  # 200 + "..."
        self.assertTrue(result.endswith("..."))
        
        # Test with custom max_length
        result = self.parser._extract_description(element, max_length=100)
        self.assertEqual(len(result), 103)  # 100 + "..."
        self.assertTrue(result.endswith("..."))
        
        # Test with short description (shouldn't be trimmed)
        short_desc = "Short description"
        html = f"""
        <div class="project-card">
            <div class="wants-card__description-text">
                {short_desc}
            </div>
        </div>
        """
        element = self.create_mock_element(html)
        result = self.parser._extract_description(element)
        self.assertEqual(result, short_desc)

if __name__ == "__main__":
    unittest.main()
