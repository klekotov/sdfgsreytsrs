import asyncio
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime
from curl_cffi.requests import AsyncSession
from config import DEFAULT_HEADERS, TIMEOUT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InfernoCookiesPayment:
    BASE_URL = "https://inferno-cookies.com"
    ORDERS_ENDPOINT = "/api/v1/orders"

    def __init__(self):
        self.session: Optional[AsyncSession] = None

    async def init(self):
        self.session = AsyncSession(impersonate="chrome120")

    async def close(self):
        if self.session:
            await self.session.close()

    async def place_order(self, product_ids: List[str]) -> Dict[str, Any]:
        try:
            url = f"{self.BASE_URL}{self.ORDERS_ENDPOINT}"

            resp = await self.session.post(
                url,
                json={"product_ids": product_ids},
                headers={
                    "Content-Type": "application/json",
                    "Origin": self.BASE_URL,
                    "Referer": f"{self.BASE_URL}/",
                    "User-Agent": DEFAULT_HEADERS["User-Agent"],
                },
                timeout=TIMEOUT
            )

            if resp.status_code in (200, 201):
                result = resp.json()
                order_id = result.get('order_id')
                logger.info(f"✓ ORDER PLACED: {order_id}")
                return {
                    'success': True,
                    'order_id': order_id,
                    'items_summary': result.get('items_summary'),
                    'bundle_download_url': result.get('bundle_download_url'),
                    'bundle_download_filename': result.get('bundle_download_filename'),
                    'timestamp': datetime.now().isoformat()
                }
            else:
                logger.error(f"Order failed: {resp.status_code} - {resp.text[:300]}")
                return {
                    'success': False,
                    'error': f"Status {resp.status_code}",
                    'detail': resp.text[:200]
                }

        except asyncio.TimeoutError:
            logger.error("Order timeout")
            return {'success': False, 'error': 'Timeout'}
        except Exception as e:
            logger.error(f"Order error: {e}")
            return {'success': False, 'error': str(e)}

    async def execute_purchase(self, product_id: str) -> Dict[str, Any]:
        await self.init()
        try:
            return await self.place_order([product_id])
        finally:
            await self.close()
