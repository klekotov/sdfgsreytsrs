import aiohttp
import asyncio
import json
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Any
from datetime import datetime
from config import DEFAULT_HEADERS, TIMEOUT
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SiteParser:
    def __init__(self, site_config: Dict[str, Any]):
        self.config = site_config
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def init(self):
        self.session = aiohttp.ClientSession(headers=DEFAULT_HEADERS)
    
    async def close(self):
        if self.session:
            await self.session.close()
    
    async def _fetch(self, url: str, method: str = "GET", **kwargs) -> Optional[str]:
        try:
            async with self.session.request(
                method, 
                url, 
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
                **kwargs
            ) as resp:
                if resp.status == 200:
                    return await resp.text()
                else:
                    logger.warning(f"Fetch failed: {url} - Status {resp.status}")
                    return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout: {url}")
            return None
        except Exception as e:
            logger.error(f"Fetch error: {e}")
            return None
    
    async def get_all_products(self) -> List[Dict[str, Any]]:
        """Fetch and parse all products from the site"""
        url = f"{self.config['base_url']}{self.config['product_endpoint']}"
        content = await self._fetch(url)
        
        if not content:
            return []
        
        if self.config['parser_type'] == 'json':
            return self._parse_json(content)
        else:
            return self._parse_html(content)
    
    def _parse_json(self, content: str) -> List[Dict[str, Any]]:
        """Parse JSON response"""
        try:
            data = json.loads(content)
            products = []
            
            # Adjust based on actual API response structure
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict) and 'products' in data:
                items = data['products']
            else:
                items = []
            
            for item in items:
                in_stock = item.get('in_stock', item.get('available_count', 0) > 0)
                product = {
                    'name': item.get('name', item.get('title', 'Unknown')),
                    'id': item.get('id', item.get('sku', '')),
                    'price': float(item.get('price', 0)),
                    'in_stock': in_stock,
                    'available_count': int(item.get('available_count', 0)),
                    'url': item.get('url', ''),
                    'image': item.get('image', item.get('image_url', '')),
                    'raw': item
                }
                if product['name']:
                    products.append(product)
            
            return products
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return []
    
    def _parse_html(self, content: str) -> List[Dict[str, Any]]:
        """Parse HTML response"""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            products = []
            
            # Adjust selectors based on actual site structure
            product_elements = soup.select('[data-product], .product-item, .product-card')
            
            for elem in product_elements:
                try:
                    name_elem = elem.select_one('h2, .product-name, [data-name]')
                    price_elem = elem.select_one('.price, [data-price], .product-price')
                    sku_elem = elem.select_one('[data-sku], .sku')
                    stock_elem = elem.select_one('[data-stock], .in-stock, .stock-status')
                    
                    product = {
                        'name': name_elem.get_text(strip=True) if name_elem else 'Unknown',
                        'id': sku_elem.get_text(strip=True) if sku_elem else '',
                        'price': self._extract_price(price_elem.get_text(strip=True)) if price_elem else 0,
                        'in_stock': stock_elem is not None if stock_elem else False,
                        'available_count': 1 if stock_elem else 0,
                        'url': elem.get('href', ''),
                        'image': ''
                    }
                    
                    if product['name'] and product['name'] != 'Unknown':
                        products.append(product)
                except Exception as e:
                    logger.debug(f"Element parse error: {e}")
                    continue
            
            return products
        except Exception as e:
            logger.error(f"HTML parse error: {e}")
            return []
    
    @staticmethod
    def _extract_price(price_str: str) -> float:
        """Extract price from string like '$99.99' or '99,99 EUR'"""
        import re
        match = re.search(r'[\d.,]+', price_str.replace(',', '.'))
        if match:
            try:
                return float(match.group())
            except:
                return 0
        return 0
    
    async def search_product(self, product_name: str) -> Optional[Dict[str, Any]]:
        """Search for specific product by name"""
        all_products = await self.get_all_products()
        
        search_lower = product_name.lower()
        
        # Exact match
        for product in all_products:
            if product['name'].lower() == search_lower:
                return product
        
        # Partial match
        for product in all_products:
            if search_lower in product['name'].lower():
                return product
        
        return None
    
    async def check_stock(self, product_name: str) -> Dict[str, Any]:
        """Check if specific product is in stock"""
        product = await self.search_product(product_name)
        
        if product:
            return {
                'found': True,
                'in_stock': product['in_stock'],
                'available_count': product.get('available_count', 0),
                'product': product
            }
        
        return {'found': False, 'in_stock': False, 'available_count': 0}
