"""
Background tasks for Kwork integration.
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from .service import KworkService
from .api import KworkAPI

logger = logging.getLogger(__name__)

class KworkPoller:
    """Background task for polling Kwork for new orders."""
    
    def __init__(self, poll_interval: int = 300):
        """Initialize the poller."""
        self.poll_interval = poll_interval
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self.service = KworkService()
    
    async def start(self):
        """Start the polling task."""
        if self._running:
            logger.warning("Kwork poller is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("Kwork poller started")
    
    async def stop(self):
        """Stop the polling task."""
        if not self._running:
            return
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Kwork poller stopped")
    
    async def _poll_loop(self):
        """Main polling loop."""
        logger.info("Starting Kwork polling loop")
        
        while self._running:
            try:
                start_time = datetime.utcnow()
                
                # Process new orders
                await self.service.process_new_orders()
                
                # Calculate sleep time to maintain consistent interval
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                sleep_time = max(0, self.poll_interval - elapsed)
                
                # Sleep until next poll
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                logger.info("Kwork poller received cancellation signal")
                break
            except Exception as e:
                logger.error(f"Error in Kwork poller: {e}", exc_info=True)
                # Sleep a bit before retrying on error
                await asyncio.sleep(min(60, self.poll_interval))
    
    def is_running(self) -> bool:
        """Check if the poller is running."""
        return self._running and self._task and not self._task.done()
