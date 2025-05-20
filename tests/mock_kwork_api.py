"""Mock Kwork API for testing."""
from typing import Dict, Any, Optional

class MockKworkAPI:
    """Mock Kwork API for testing purposes."""
    
    def __init__(self):
        self.authenticated = True
    
    async def get_recent_orders(self, per_page: int = 20) -> Dict[str, Any]:
        """Return mock recent orders."""
        return {
            "success": True,
            "data": {
                "list": [
                    {
                        "id": "test_order_123",
                        "name": "Test Order",
                        "description": "This is a test order for bot testing",
                        "price": {
                            "amount": 5000,
                            "currency": "RUB"
                        },
                        "category": "Web Development",
                        "status": "active",
                        "views": 10,
                        "replies_count": 3,
                        "published_at": 1716102000,  # 2025-05-20 10:00:00 UTC
                        "is_remote": True,
                        "is_premium": False,
                        "is_safe_deal": True,
                        "is_urgent": False,
                        "is_budget_flexible": True
                    }
                ],
                "pagination": {
                    "total": 1,
                    "pages": 1,
                    "page": 1,
                    "per_page": per_page
                }
            }
        }
    
    async def get_order_details(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Return mock order details."""
        return {
            "id": order_id,
            "name": "Test Order",
            "description": "This is a test order for bot testing",
            "price": {
                "amount": 5000,
                "currency": "RUB"
            },
            "category": "Web Development",
            "status": "publish",
            "views": 10,
            "replies_count": 3,
            "published_at": 1716102000,  # 2025-05-20 10:00:00 UTC
            "is_remote": True,
            "is_premium": False,
            "is_safe_deal": True,
            "is_urgent": False,
            "is_budget_flexible": True
        }
    
    async def send_reply(self, order_id: str, message: str, **kwargs) -> Dict[str, Any]:
        """Mock sending a reply to an order."""
        return {
            "success": True,
            "data": {
                "id": 12345,
                "order_id": order_id,
                "message": message,
                **kwargs
            }
        }
    
    async def __aenter__(self):
        return self
    
    async def get_orders(self, **kwargs) -> list[Dict[str, Any]]:
        """Return mock orders based on filter criteria.
        
        Args:
            **kwargs: Filter criteria (e.g., category_id, budget_from, budget_to)
            
        Returns:
            List of orders matching the criteria
        """
        # Create a test order based on the test data
        test_order = {
            "id": "test_order_123",
            "name": "Test Order",
            "description": "This is a test order for bot testing",
            "price": {
                "amount": 5000,
                "currency": "RUB"
            },
            "category": "Web Development",
            "status": "active",
            "views": 10,
            "replies_count": 3,
            "published_at": 1716102000,  # 2025-05-20 10:00:00 UTC
            "is_remote": True,
            "is_premium": False,
            "is_safe_deal": True,
            "is_urgent": False,
            "is_budget_flexible": True
        }
        
        # In a real implementation, we would filter based on the provided criteria
        # For testing, we'll just return the test order if it matches basic criteria
        if kwargs.get('category_id') and kwargs['category_id'] not in [1, 2, 3]:
            return []
            
        if kwargs.get('budget_from') and test_order['price']['amount'] < kwargs['budget_from']:
            return []
            
        if kwargs.get('budget_to') and test_order['price']['amount'] > kwargs['budget_to']:
            return []
            
        return [test_order]
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
