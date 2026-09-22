import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///autobuy.db")

# Webhooks (для хоста)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", "8443"))

# Sites configuration
SITES_CONFIG = {
    "inferno_cookies": {
        "name": "Inferno Cookies",
        "base_url": "https://inferno-cookies.com",
        "product_endpoint": "/api/v1/products",
        "categories_endpoint": "/api/v1/categories",
        "orders_endpoint": "/api/v1/orders",
        "requires_auth": False,
        "parser_type": "json"
    }
}

# Polling settings
CHECK_INTERVAL = float(os.getenv("CHECK_INTERVAL", "60.0"))
TIMEOUT = float(os.getenv("TIMEOUT", "5.0"))

# Headers
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
