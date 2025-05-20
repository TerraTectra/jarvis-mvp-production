"""Tests for the Kwork price parser."""
import pytest
from unittest.mock import MagicMock

from src.integrations.kwork_parser import KworkPriceParser


class TestKworkPriceParser:
    """Test cases for KworkPriceParser class."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.parser = KworkPriceParser()
    
    def test_extract_price_rub(self):
        """Test extracting price in rubles."""
        element = MagicMock()
        element.text = "1 000 ₽"
        
        price = self.parser.extract_price(element)
        assert price == 1000.0
    
    def test_extract_price_usd(self):
        """Test extracting price in USD."""
        element = MagicMock()
        element.text = "100 $"
        
        price = self.parser.extract_price(element)
        assert price == 100.0
    
    def test_extract_price_range(self):
        """Test extracting price range."""
        element = MagicMock()
        element.text = "1 000 - 2 000 ₽"
        
        price = self.parser.extract_price(element)
        assert price == 1500.0  # Average of 1000 and 2000
    
    def test_extract_price_with_text(self):
        """Test extracting price with additional text."""
        element = MagicMock()
        element.text = "Цена: 1 000 ₽ (договорная)"
        
        price = self.parser.extract_price(element)
        assert price == 1000.0
    
    def test_extract_price_with_decimal(self):
        """Test extracting price with decimal places."""
        element = MagicMock()
        element.text = "1 234.56 $"
        
        price = self.parser.extract_price(element)
        assert price == 1234.56
    
    def test_extract_price_with_thousands_separator(self):
        """Test extracting price with thousands separator."""
        element = MagicMock()
        element.text = "10,000.50 $"
        
        price = self.parser.extract_price(element)
        assert price == 10000.5
    
    def test_extract_price_with_currency_code(self):
        """Test extracting price with currency code."""
        element = MagicMock()
        element.text = "1 000 RUB"
        
        price = self.parser.extract_price(element)
        assert price == 1000.0
    
    def test_extract_price_with_currency_symbol_after(self):
        """Test extracting price with currency symbol after the number."""
        element = MagicMock()
        element.text = "1000р."
        
        price = self.parser.extract_price(element)
        assert price == 1000.0
    
    def test_extract_price_with_currency_symbol_before(self):
        """Test extracting price with currency symbol before the number."""
        element = MagicMock()
        element.text = "$1000"
        
        price = self.parser.extract_price(element)
        assert price == 1000.0
    
    def test_extract_price_with_negative_number(self):
        """Test extracting a negative price."""
        element = MagicMock()
        element.text = "-1000 ₽"
        
        price = self.parser.extract_price(element)
        assert price == -1000.0
    
    def test_extract_price_with_multiple_numbers(self):
        """Test extracting price when multiple numbers are present."""
        element = MagicMock()
        element.text = "Project budget: 1000-2000 ₽, deadline: 5 days"
        
        price = self.parser.extract_price(element)
        assert price == 1500.0  # Average of 1000 and 2000
    
    def test_extract_price_no_match(self):
        """Test extracting price when no price is found."""
        element = MagicMock()
        element.text = "Цена договорная"
        
        price = self.parser.extract_price(element)
        assert price is None
    
    def test_extract_price_empty_string(self):
        """Test extracting price from an empty string."""
        element = MagicMock()
        element.text = ""
        
        price = self.parser.extract_price(element)
        assert price is None
    
    def test_extract_price_none(self):
        """Test extracting price from None."""
        price = self.parser.extract_price(None)
        assert price is None
    
    def test_extract_price_with_whitespace(self):
        """Test extracting price with extra whitespace."""
        element = MagicMock()
        element.text = "   1 000  ₽   "
        
        price = self.parser.extract_price(element)
        assert price == 1000.0
    
    def test_extract_price_with_multiple_currencies(self):
        """Test extracting price with multiple currency symbols."""
        element = MagicMock()
        element.text = "1000 ₽ ($15)"
        
        price = self.parser.extract_price(element)
        # Should take the first number found (1000)
        assert price == 1000.0
    
    def test_extract_price_with_unicode_spaces(self):
        """Test extracting price with non-breaking spaces."""
        element = MagicMock()
        element.text = "1\u202F000\u00A0₽"  # Non-breaking space and thin space
        
        price = self.parser.extract_price(element)
        assert price == 1000.0
    
    def test_extract_price_with_negative_range(self):
        """Test extracting a negative price range."""
        element = MagicMock()
        element.text = "-1000 - -500 $"
        
        price = self.parser.extract_price(element)
        assert price == -750.0  # Average of -1000 and -500
    
    def test_extract_price_with_scientific_notation(self):
        """Test extracting price in scientific notation."""
        element = MagicMock()
        element.text = "1.23e3 $"  # 1230
        
        price = self.parser.extract_price(element)
        assert price == 1230.0
    
    def test_extract_price_with_currency_code_after(self):
        """Test extracting price with currency code after the number."""
        element = MagicMock()
        element.text = "1000 RUB"
        
        price = self.parser.extract_price(element)
        assert price == 1000.0
    
    def test_extract_price_with_currency_code_before(self):
        """Test extracting price with currency code before the number."""
        element = MagicMock()
        element.text = "USD 1000"
        
        price = self.parser.extract_price(element)
        assert price == 1000.0
    
    def test_extract_price_with_currency_name(self):
        """Test extracting price with currency name instead of symbol."""
        element = MagicMock()
        element.text = "1000 рублей"
        
        price = self.parser.extract_price(element)
        assert price == 1000.0
    
    def test_extract_price_with_currency_name_and_symbol(self):
        """Test extracting price with both currency name and symbol."""
        element = MagicMock()
        element.text = "1000 рублей (₽)"
        
        price = self.parser.extract_price(element)
        assert price == 1000.0
    
    def test_extract_price_with_multiple_currencies_and_ranges(self):
        """Test extracting price with multiple currencies and ranges."""
        element = MagicMock()
        element.text = "Budget: $1000-2000 USD (70000-140000 ₽)"
        
        price = self.parser.extract_price(element)
        # Should take the first range found (1000-2000)
        assert price == 1500.0
