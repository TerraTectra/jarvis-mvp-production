"""
Service layer for Kwork order processing.
"""
import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Set up logging
logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from .api import KworkAPI, KworkAPIError
from .models import KworkOrder, KworkReply, KworkFilter
from .order_processor import get_order_processor
from src.database.session import async_session
from src.services import generate_response

# Configuration
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

# LLM prompt template for generating replies
REPLY_PROMPT_TEMPLATE = """
Ты — профессиональный фрилансер, который хочет получить заказ на Kwork. 
Сгенерируй отклик на заказ, следуя инструкциям:

1. Обратись к заказчику по имени (если указано) или уважительно
2. Кратко представься (1-2 предложения)
3. Опиши свой опыт и квалификацию (2-3 предложения)
4. Предложи решение задачи (2-3 предложения)
5. Укажи сроки и стоимость (если не указаны в заказе)
6. Заверши призывом к действию

Информация о заказе:
Название: {title}
Описание: {description}
Бюджет: {budget}

Твой отклик (максимум 2000 символов):
"""

try:
    from src.bot.telegram_bot import send_telegram_message
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    logger.warning("Telegram bot is not available. Notifications will be logged to console only.")

class KworkService:
    """Service for handling Kwork order processing."""
    
    def __init__(self, api: Optional[KworkAPI] = None):
        """Initialize the Kwork service."""
        self.api = api
    
    async def process_new_orders(self):
        """Fetch and process new orders from Kwork."""
        if not self.api:
            async with KworkAPI() as api:
                self.api = api
                await self._process_orders()
        else:
            await self._process_orders()
    
    async def _process_orders(self):
        """Process new orders."""
        try:
            # Get active filters
            async with async_session() as session:
                filters = await self._get_active_filters(session)
                if not filters:
                    logger.warning("No active filters found. Please create at least one filter.")
                    return
                
                # Process each filter
                for filter_ in filters:
                    await self._process_filter(session, filter_)
                
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error processing orders: {e}", exc_info=True)
    
    async def _process_filter(self, session: AsyncSession, filter_: KworkFilter):
        """Process orders for a specific filter."""
        logger.info(f" [START] Processing filter: {filter_.name} (ID: {filter_.id})")
        logger.info(f" Filter criteria - Categories: {filter_.categories}, Min Price: {filter_.min_price}, "
                    f"Max Price: {filter_.max_price}, Keywords: {filter_.keywords}")
        
        # Initialize statistics
        self.stats = {
            'new_orders': 0,
            'matched_orders': 0,
            'replied_orders': 0,
            'errors': 0
        }
        
        try:
            # Get orders from Kwork API
            logger.info(" Fetching orders from Kwork API...")
            try:
                orders_data = await self.api.get_recent_orders(per_page=20)
                logger.debug(f" Raw orders data: {orders_data}")
                orders = orders_data.get("data", {}).get("list", [])
                logger.info(f" Found {len(orders)} recent orders in API response")
            except Exception as e:
                logger.error(f" Failed to fetch orders from API: {e}", exc_info=True)
                self.stats['errors'] += 1
                return
            
            if not orders:
                logger.info(" No new orders found in API response")
                return
            
            # Process each order
            for order_idx, order_data in enumerate(orders, 1):
                order_id = str(order_data.get("id", ""))
                logger.info(f"\n[{order_idx}/{len(orders)}] Processing order {order_id}")
                
                # Log important order details
                logger.info(f"Title: {order_data.get('name', 'No title')}")
                logger.info(f"Category: {order_data.get('category', 'No category')}")
                
                # Log price information
                if 'price' in order_data and isinstance(order_data['price'], dict):
                    price = order_data['price']
                    logger.info(f"Price: {price.get('amount', 'N/A')} {price.get('currency', '')}")
                else:
                    logger.warning("No valid price information in order data")
                logger.info(f"\n [{order_idx}/{len(orders)}] Processing order {order_id}")
                logger.info(f" Order data keys: {list(order_data.keys())}")
                logger.debug(f" Order data: {order_data}")
                
                # Log the type of price for debugging
                if 'price' in order_data:
                    logger.info(f" Price type: {type(order_data['price']).__name__}, value: {order_data['price']}")
                else:
                    logger.warning(" No price in order data")
                
                try:
                    # Check if we've already processed this order
                    logger.info("Checking if order already exists in database...")
                    try:
                        existing_order = await session.get(KworkOrder, order_id)
                        if existing_order:
                            logger.info(f"Order {order_id} already exists in database, skipping...")
                            continue
                            
                        logger.info("Order not found in database, creating new order...")
                    except Exception as e:
                        logger.error(f"Error checking for existing order: {e}", exc_info=True)
                        self.stats['errors'] += 1
                        continue
                        
                    # Create new order in database
                    try:
                        logger.info("Creating new order in database...")
                        order = await self._create_order(session, order_data)
                        logger.info(f"Successfully created new order with ID: {order.id}")
                        self.stats['new_orders'] += 1
                        
                        # Log the order details for debugging
                        logger.debug(f"Order details: {order.__dict__}")
                    except Exception as e:
                        logger.error(f"Error creating order in database: {e}", exc_info=True)
                        self.stats['errors'] += 1
                        continue
                        
                    # Check if we've already replied to this order
                    try:
                        existing_reply = await session.scalar(
                            select(KworkReply)
                            .where(KworkReply.order_id == order_id)
                            .limit(1)
                        )
                        if existing_reply and existing_reply.status == 'sent':
                            logger.info(f"Already replied to order {order_id}")
                            continue
                    except Exception as e:
                        logger.error(f"Error checking for existing reply: {e}", exc_info=True)
                        self.stats['errors'] += 1
                        continue
                        
                    # Check if order matches filter
                    logger.info("Checking if order matches filter criteria...")
                    try:
                        matches = await self._matches_filter(order, filter_)
                        if not matches:
                            logger.info("Order does not match filter criteria, skipping...")
                            continue
                            
                        logger.info("Order matches filter criteria")
                        self.stats['matched_orders'] += 1
                    except Exception as e:
                        logger.error(f"Error checking filter criteria: {e}", exc_info=True)
                        self.stats['errors'] += 1
                        continue
                        
                    # Generate reply using LLM
                    try:
                        logger.info("Generating reply using LLM...")
                        reply_text = await self._generate_kwork_reply(order)
                        if not reply_text or not isinstance(reply_text, str):
                            raise ValueError("Invalid reply text generated")
                            
                        logger.info(f"Successfully generated reply (length: {len(reply_text)} chars)")
                        logger.debug(f"Reply preview: {reply_text[:200]}...")
                    except Exception as e:
                        logger.error(f"Error generating reply: {e}", exc_info=True)
                        self.stats['errors'] += 1
                        continue
                        
                    # Create reply record
                    reply = KworkReply(
                        order_id=order.id,
                        filter_id=filter_.id,
                        message=reply_text,
                        status="pending"
                    )
                    
                    # Save reply to database
                    session.add(reply)
                    await session.commit()
                    logger.info(f"Saved reply {reply.id} for order {order.id}")
                    
                    # Update order status and replies count
                    order.replies_count = (order.replies_count or 0) + 1
                    order.status = "replied"
                    session.add(order)
                    await session.commit()
                    
                    # Send the reply (or simulate in dry run)
                    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
                    if not dry_run:
                        try:
                            success = await self._send_kwork_reply(order.id, reply_text)
                            if success:
                                reply.status = "sent"
                                reply.sent_at = datetime.utcnow()
                                self.stats['replied_orders'] += 1
                                logger.info(f"✅ Successfully sent reply to order {order_id}")
                            else:
                                reply.status = "failed"
                                reply.error = "Failed to send reply"
                                self.stats['errors'] += 1
                                logger.error(f"❌ Failed to send reply to order {order_id}")
                        except Exception as e:
                            reply.status = "error"
                            reply.error = str(e)
                            self.stats['errors'] += 1
                            logger.error(f"⚠️ Error sending reply to order {order_id}: {e}", exc_info=True)
                    else:
                        reply.status = "dry_run"
                        logger.info(f"ℹ️ DRY RUN: Would send reply to order {order_id}")
                    
                    # Update reply status in database
                    session.add(reply)
                    await session.commit()
                    
                    # Send notification if enabled
                    if TELEGRAM_AVAILABLE and reply.status == "sent":
                        await self._notify_about_order(
                            order, 
                            f"Automated reply {'sent' if not dry_run else 'simulated'}"
                        )
                
                except Exception as e:
                    self.stats['errors'] += 1
                    logger.error(f"⚠️ Error processing order {order_id}: {e}", exc_info=True)
                    continue
            
            # Log summary for this filter
            logger.info(
                f"📊 Filter {filter_.name} processing complete. "
                f"New: {self.stats['new_orders']}, "
                f"Matched: {self.stats['matched_orders']}, "
                f"Replied: {self.stats['replied_orders']}, "
                f"Errors: {self.stats['errors']}"
            )
            
        except Exception as e:
            logger.error(f"⚠️ Critical error in _process_filter for filter {filter_.id}: {e}", exc_info=True)
            raise
    
    async def _create_order(self, session: AsyncSession, order_data: Dict[str, Any]) -> KworkOrder:
        """Create a new KworkOrder from API data."""
        order = KworkOrder(
            id=str(order_data.get("id")),
            title=order_data.get("name", ""),
            description=order_data.get("description", ""),
            price={
                "amount": order_data.get("price", {}).get("amount"),
                "currency": order_data.get("price", {}).get("currency", "RUB")
            },
            category=order_data.get("category", {}).get("name"),
            status=order_data.get("status"),
            views=order_data.get("views", 0),
            replies_count=order_data.get("replies_count", 0),
            published_at=datetime.fromtimestamp(order_data.get("published_at", 0)) if order_data.get("published_at") else None,
            raw_data=order_data
        )
        
        session.add(order)
        await session.flush()
        return order
    
    async def _generate_kwork_reply(self, order: KworkOrder) -> str:
        """
        Generate a reply for a Kwork order using LLM.
        
        Args:
            order: The KworkOrder to generate a reply for
            
        Returns:
            str: Generated reply text
        """
        try:
            # Prepare the prompt with order details
            prompt = REPLY_PROMPT_TEMPLATE.format(
                title=order.title,
                description=order.description or "Нет описания",
                budget=f"{order.price.get('amount')} {order.price.get('currency', 'RUB')}" 
                       if order.price and isinstance(order.price, dict) else "Не указан"
            )
            
            # Generate the reply using LLM
            reply = await generate_response(
                prompt,
                max_new_tokens=500,  # Longer for detailed replies
                temperature=0.7,
                top_p=0.9
            )
            
            # Clean up the response
            reply = reply.strip()
            if reply.startswith('"') and reply.endswith('"'):
                reply = reply[1:-1]
                
            # Ensure the reply is not too long (Kwork has a limit)
            if len(reply) > 2000:
                reply = reply[:1997] + "..."
                
            return reply
            
        except Exception as e:
            logger.error(f"Error generating reply for order {order.id}: {e}")
            # Fallback reply in case of error
            return (
                "Здравствуйте! Я заинтересован(а) в вашем заказе. "
                "Готов(а) обсудить детали и предложить решение. "
                "С уважением, профессиональный фрилансер."
            )
    
    async def _send_kwork_reply(self, order_id: str, message: str) -> bool:
        """
        Send a reply to a Kwork order using Kwork API.
        
        Args:
            order_id: ID of the order to reply to
            message: Reply message text
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            KworkAPIError: If there's an error with the API request
            ValueError: If the reply couldn't be sent
        """
        if not self.api:
            raise ValueError("KworkAPI is not initialized")
            
        logger.info(f"Preparing to send reply to order {order_id}")
        logger.debug(f"Reply preview: {message[:100]}...")
        
        try:
            # Get order details to check if we can reply
            order_details = await self.api.get_order_details(order_id)
            if not order_details:
                logger.error(f"Order {order_id} not found or access denied")
                return False
                
            # Check if order is still open for replies
            if order_details.get('status') != 'publish':
                logger.warning(f"Order {order_id} is not open for replies (status: {order_details.get('status')})")
                return False
                
            # Check if we've already replied to this order
            async with async_session() as session:
                existing_reply = await session.scalar(
                    select(KworkReply)
                    .where(KworkReply.order_id == order_id)
                    .limit(1)
                )
                if existing_reply and existing_reply.status == 'sent':
                    logger.warning(f"Already replied to order {order_id}")
                    return True
            
            # Prepare reply data
            reply_data = {
                'message': message,
                'days': 3,  # Default delivery time in days
                'price': None  # Will be set based on order price or default
            }
            
            # Set price based on order budget if available
            order_price = order_details.get('price')
            if isinstance(order_price, dict) and 'amount' in order_price:
                # Set our price slightly lower than the budget
                budget = float(order_price['amount'])
                reply_data['price'] = max(100, budget * 0.9)  # At least 100 RUB
                logger.debug(f"Set price to {reply_data['price']} based on order budget")
            
            # Add delay to avoid rate limiting
            delay_seconds = int(os.getenv("REPLY_DELAY", "30"))
            logger.debug(f"Waiting {delay_seconds} seconds before sending reply...")
            await asyncio.sleep(delay_seconds)
            
            # Send the reply
            logger.info(f"Sending reply to order {order_id}")
            response = await self.api.send_reply(
                order_id=order_id,
                **{k: v for k, v in reply_data.items() if v is not None}
            )
            
            if response.get('success'):
                logger.info(f"Successfully sent reply to order {order_id}")
                return True
            else:
                error_msg = response.get('message', 'Unknown error')
                logger.error(f"Failed to send reply to order {order_id}: {error_msg}")
                raise KworkAPIError(f"API error: {error_msg}")
            
        except KworkAPIError as e:
            logger.error(f"Kwork API error in _send_kwork_reply: {e}")
            raise
            
        except asyncio.CancelledError:
            logger.warning(f"Reply to order {order_id} was cancelled")
            raise
            
        except Exception as e:
            logger.error(f"Unexpected error in _send_kwork_reply for order {order_id}: {e}", exc_info=True)
            raise ValueError(f"Failed to send reply: {str(e)}")
    
    async def _matches_filter(self, order: KworkOrder, filter_: KworkFilter) -> bool:
        """Check if an order matches the filter criteria."""
        logger.info(f"🔍 Checking if order {order.id} matches filter {filter_.name}")
        logger.debug(f"Order data: {order}")
        logger.debug(f"Filter criteria: {filter_}")
        
        try:
            # Convert order to dict for processing
            order_dict = {
                'id': order.id,
                'title': order.title,
                'description': order.description,
                'price': order.price,
                'category': order.category,
                'status': order.status,
                'views': order.views,
                'replies_count': order.replies_count,
                'published_at': order.published_at.isoformat() if order.published_at else None,
                'is_remote': order.is_remote,
                'is_premium': order.is_premium,
                'is_safe_deal': order.is_safe_deal,
                'is_urgent': order.is_urgent,
                'is_budget_flexible': order.is_budget_flexible
            }
            
            # Get the order processor and check if the order matches the filter
            order_processor = get_order_processor()
            result = await order_processor.process_order(order_dict)
            
            # Log the result
            logger.info(f"✅ Order {order.id} {'matches' if result.get('is_relevant', False) else 'does not match'} filter {filter_.name}")
            logger.debug(f"Order processing result: {result}")
            
            return result.get('is_relevant', False)
            
        except Exception as e:
            logger.error(f"❌ Error checking if order {order.id} matches filter: {e}", exc_info=True)
            # Default to False to avoid processing orders with errors
            return False
    
    async def _notify_about_order(self, order: KworkOrder, status: str = ""):
        """
        Send notification about an order processing status.
        
        Args:
            order: The KworkOrder that was processed
            status: Status message to include in the notification
        """
        if not TELEGRAM_AVAILABLE:
            logger.info(f"Order processed: {order.title}")
            logger.info(f"Status: {status}")
            logger.info(f"Order URL: https://kwork.ru/projects/{order.id}")
            return
            
        try:
            # Format price for display
            price_info = ""
            if order.price and isinstance(order.price, dict):
                amount = order.price.get('amount', '?')
                currency = order.price.get('currency', 'RUB')
                price_info = f"{amount} {currency}"
            else:
                price_info = "Не указана"
            
            message = (
                "📢 *Обработан заказ*\n\n"
                f"*Название*: {order.title or 'Без названия'}\n"
                f"*Категория*: {order.category or 'Не указана'}\n"
                f"*Бюджет*: {price_info}\n"
                f"*Просмотров*: {getattr(order, 'views', 0)}\n"
                f"*Откликов*: {getattr(order, 'replies_count', 0)}\n\n"
                f"*Статус*: {status}\n"
                f"[Открыть заказ](https://kwork.ru/projects/{order.id})"
            )
                
            await send_telegram_message(message, parse_mode="Markdown")
            
        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}", exc_info=True)
    
    async def _get_active_filters(self, session: AsyncSession) -> List[KworkFilter]:
        """Get all active filters."""
        result = await session.execute(
            select(KworkFilter)
            .where(KworkFilter.is_active == True)  # noqa: E712
        )
        return result.scalars().all()
    
    async def create_filter(
        self,
        name: str,
        keywords: Optional[List[str]] = None,
        categories: Optional[List[int]] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        is_active: bool = True
    ) -> KworkFilter:
        """Create a new Kwork filter."""
        async with async_session() as session:
            filter_ = KworkFilter(
                name=name,
                keywords=keywords or [],
                categories=categories or [],
                min_price=min_price,
                max_price=max_price,
                is_active=is_active
            )
            
            session.add(filter_)
            await session.commit()
            return filter_
