import aiohttp
import asyncio
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime
from config import DEFAULT_HEADERS, TIMEOUT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InfernoCookiesPayment:
    """Payment processor для inferno-cookies.com"""
    
    BASE_URL = "https://inferno-cookies.com"
    ORDERS_ENDPOINT = "/api/v1/orders"
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def init(self):
        self.session = aiohttp.ClientSession(headers=DEFAULT_HEADERS)
    
    async def close(self):
        if self.session:
            await self.session.close()
    
    async def place_order(self, product_ids: List[str]) -> Dict[str, Any]:
        """
        Place order with list of product IDs
        Никакой авторизации не требуется
        """
        try:
            url = f"{self.BASE_URL}{self.ORDERS_ENDPOINT}"
            payload = {"product_ids": product_ids}
            
            async with self.session.post(
                url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT)
            ) as resp:
                if resp.status in (200, 201):
                    result = await resp.json()
                    order_id = result.get('order_id')
                    
                    logger.info(f"✓✓✓ ORDER PLACED: {order_id}")
                    
                    return {
                        'success': True,
                        'order_id': order_id,
                        'items_summary': result.get('items_summary'),
                        'bundle_download_url': result.get('bundle_download_url'),
                        'bundle_download_filename': result.get('bundle_download_filename'),
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    error_text = await resp.text()
                    logger.error(f"Order failed: {resp.status} - {error_text}")
                    return {'success': False, 'error': f"Status {resp.status}"}
        
        except asyncio.TimeoutError:
            logger.error("Order timeout")
            return {'success': False, 'error': 'Timeout'}
        except Exception as e:
            logger.error(f"Order error: {e}")
            return {'success': False, 'error': str(e)}
    
    async def execute_purchase(self, product_id: str) -> Dict[str, Any]:
        """
        Simple purchase: just send product ID
        inferno-cookies не требует ничего кроме этого
        """
        await self.init()
        
        try:
            result = await self.place_order([product_id])
            return result
        finally:
            await self.close()
