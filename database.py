import asyncio
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

class Database:
    def __init__(self, db_path: str = "autobuy.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Watched products table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watched_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                site_key TEXT NOT NULL,
                product_name TEXT NOT NULL,
                product_sku TEXT,
                target_price REAL,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Products cache table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_key TEXT NOT NULL,
                product_name TEXT NOT NULL,
                product_sku TEXT,
                price REAL,
                in_stock BOOLEAN DEFAULT 0,
                available_count INTEGER DEFAULT 0,
                last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(site_key, product_sku)
            )
        """)
        
        # Purchase history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                site_key TEXT NOT NULL,
                product_name TEXT NOT NULL,
                price REAL,
                status TEXT,
                order_id TEXT,
                purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def add_user(self, user_id: int, username: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        conn.commit()
        conn.close()
    
    def add_watched_product(self, user_id: int, site_key: str, product_name: str, 
                           product_sku: Optional[str] = None, target_price: Optional[float] = None) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO watched_products (user_id, site_key, product_name, product_sku, target_price)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, site_key, product_name, product_sku, target_price))
        conn.commit()
        product_id = cursor.lastrowid
        conn.close()
        return product_id
    
    def get_watched_products(self, user_id: int, status: str = "active") -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM watched_products 
            WHERE user_id = ? AND status = ?
        """, (user_id, status))
        products = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return products
    
    def update_product_cache(self, site_key: str, product_name: str, product_sku: str, 
                            price: float, in_stock: bool, available_count: int = 0):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products_cache (site_key, product_name, product_sku, price, in_stock, available_count)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(site_key, product_sku) 
            DO UPDATE SET price=excluded.price, in_stock=excluded.in_stock, available_count=excluded.available_count, last_checked=CURRENT_TIMESTAMP
        """, (site_key, product_name, product_sku, price, in_stock, available_count))
        conn.commit()
        conn.close()
    
    def get_cached_products(self, site_key: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM products_cache WHERE site_key = ?
        """, (site_key,))
        products = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return products
    
    def add_purchase(self, user_id: int, site_key: str, product_name: str, 
                    price: float, status: str, order_id: Optional[str] = None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO purchase_history (user_id, site_key, product_name, price, status, order_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, site_key, product_name, price, status, order_id))
        conn.commit()
        conn.close()
    
    def remove_watched_product(self, product_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE watched_products SET status = 'inactive' WHERE id = ?", (product_id,))
        conn.commit()
        conn.close()
    
    def get_purchase_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM purchase_history 
            WHERE user_id = ?
            ORDER BY purchased_at DESC
            LIMIT ?
        """, (user_id, limit))
        purchases = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return purchases
