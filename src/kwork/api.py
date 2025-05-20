"""
Kwork API client implementation.
"""
import os
import logging
import httpx
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from pathlib import Path

# Import Node.js bridge if available
try:
    from .node_bridge import KworkNodeBridge, KworkBridgeError
    NODE_BRIDGE_AVAILABLE = True
except ImportError:
    NODE_BRIDGE_AVAILABLE = False

logger = logging.getLogger(__name__)

class KworkAPIError(Exception):
    """Base exception for Kwork API errors."""
    pass

class KworkAPI:
    """Client for interacting with Kwork API with optional Node.js bridge support."""
    
    BASE_URL = "https://api.kwork.ru"
    
    def __init__(self, token: Optional[str] = None):
        """Initialize the Kwork API client."""
        self.use_node_bridge = os.getenv("USE_NODE_BRIDGE") == "1"
        self.token = token
        
        if self.use_node_bridge and NODE_BRIDGE_AVAILABLE:
            logger.info("Initializing Kwork API with Node.js bridge")
            self.bridge = KworkNodeBridge(
                node_path=os.getenv("KWORK_NODE_PATH") or "node",
                script_path=Path(__file__).parent.parent.parent / "scripts" / "kwork_node_bridge.js"
            )
            # No need for token when using Node.js bridge
        else:
            if not self.token:
                self.token = os.getenv("KWORK_TOKEN")
                if not self.token:
                    raise ValueError("KWORK_TOKEN is not set in environment variables")
            
            self.client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            logger.info("Kwork API client initialized with token authentication")
    
    async def close(self):
        """Close the client and release resources."""
        if hasattr(self, 'client'):
            await self.client.aclose()
        if hasattr(self, 'bridge'):
            # The bridge manages its own cleanup
            pass
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def get_recent_orders(self, page: int = 1, per_page: int = 20) -> Dict[str, Any]:
        """
        Get recent orders from Kwork.
        
        Args:
            page: Page number
            per_page: Number of items per page
            
        Returns:
            Dictionary with orders data
        """
        if self.use_node_bridge and hasattr(self, 'bridge'):
            try:
                # Use Node.js bridge to get orders
                orders = await asyncio.to_thread(
                    self.bridge.get_orders,
                    page=page,
                    per_page=per_page
                )
                # Convert to the expected format
                return {
                    "data": {
                        "list": orders,
                        "pager": {
                            "page": page,
                            "total": len(orders),
                            "pages": 1  # Simplified, adjust as needed
                        }
                    }
                }
            except Exception as e:
                logger.error(f"Error fetching orders via Node.js bridge: {str(e)}")
                raise KworkAPIError(f"Node.js bridge error: {str(e)}")
        else:
            # Fall back to direct API with token
            params = {
                "page": page,
                "perPage": per_page,
            }
            
            try:
                response = await self.client.get(
                    "/api/v1/orders",
                    params=params
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Error fetching orders: {e.response.text}")
                raise KworkAPIError(f"HTTP error: {e.response.status_code}")
            except httpx.RequestError as e:
                logger.error(f"Request error: {str(e)}")
                raise KworkAPIError(f"Request failed: {str(e)}")
    
    async def get_order_details(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific order.
        
        Args:
            order_id: Kwork order ID
            
        Returns:
            Order details or None if not found
        """
        try:
            response = await self.client.get(f"/api/v1/orders/{order_id}")
            
            if response.status_code == 404:
                return None
                
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            logger.error(f"HTTP error fetching order {order_id}: {e}")
            raise KworkAPIError(f"Failed to fetch order {order_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in get_order_details: {e}", exc_info=True)
            raise KworkAPIError(f"Unexpected error: {e}")

    async def send_reply(
        self, 
        order_id: str, 
        message: str, 
        price: Optional[float] = None,
        days: int = 2
    ) -> Dict[str, Any]:
        """
        Send a reply to an order.
        
        Args:
            order_id: Kwork order ID
            message: Reply message text
            price: Proposed price (optional)
            days: Days to complete the work
            
        Returns:
            API response
        """
        try:
            data = {
                "message": message,
                "days": max(1, min(30, days)),
            }
            
            if price is not None:
                data["price"] = max(0, price)
            
            response = await self.client.post(
                f"/api/v1/orders/{order_id}/replies",
                json=data
            )
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error sending reply to order {order_id}: {e}")
            raise KworkAPIError(f"Failed to send reply: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in send_reply: {e}", exc_info=True)
            raise KworkAPIError(f"Unexpected error: {e}")
