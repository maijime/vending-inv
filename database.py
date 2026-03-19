#!/usr/bin/env python3
"""Database schema and operations for vending machine tracking."""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = 'vending.db'

def get_connection():
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database schema."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Items table (replaces items.csv)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            item_num TEXT PRIMARY KEY,
            item_name TEXT NOT NULL,
            capacity INTEGER NOT NULL,
            unit_cost REAL NOT NULL,
            active INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Daily sales records
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            item_num TEXT NOT NULL,
            quantity_sold INTEGER NOT NULL,
            price REAL NOT NULL,
            revenue REAL NOT NULL,
            cost REAL NOT NULL,
            profit REAL NOT NULL,
            FOREIGN KEY (item_num) REFERENCES items(item_num),
            UNIQUE(date, item_num)
        )
    ''')
    
    # Inventory snapshots
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            item_num TEXT NOT NULL,
            current_level INTEGER NOT NULL,
            capacity INTEGER NOT NULL,
            FOREIGN KEY (item_num) REFERENCES items(item_num),
            UNIQUE(date, item_num)
        )
    ''')
    
    # Home inventory
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS home_inventory (
            item_num TEXT PRIMARY KEY,
            quantity INTEGER NOT NULL DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_num) REFERENCES items(item_num)
        )
    ''')
    
    # Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # Set default low stock threshold
    cursor.execute('''
        INSERT OR IGNORE INTO settings (key, value) VALUES ('low_stock_threshold', '3')
    ''')
    
    conn.commit()
    conn.close()

def migrate_items_from_csv(csv_path: str = 'in/items.csv'):
    """Migrate items from CSV to database."""
    import csv
    
    # Default capacities from original vending-inv.py
    default_capacities = {
        "0111": 7, "0113": 7, "0115": 7, "0117": 7,
        "0121": 7, "0123": 7, "0125": 7, "0127": 7,
        "0130": 14, "0131": 14, "0132": 14, "0133": 14,
        "0134": 14, "0135": 14, "0136": 14, "0137": 14,
        "0140": 15, "0141": 15, "0142": 15, "0143": 15,
        "0144": 15, "0145": 15, "0146": 15
    }
    
    conn = get_connection()
    cursor = conn.cursor()
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            item_num = row['iNum'].zfill(4)
            capacity = int(row.get('Cap', row.get('capacity', default_capacities.get(item_num, 10))))
            
            cursor.execute('''
                INSERT OR REPLACE INTO items (item_num, item_name, capacity, unit_cost)
                VALUES (?, ?, ?, ?)
            ''', (
                item_num,
                row['iName'],
                capacity,
                float(row.get('cost', row.get('Cost', 0)))
            ))
    
    conn.commit()
    conn.close()

def save_daily_data(date: str, sales_data: List[Dict]):
    """Save daily sales and inventory data."""
    conn = get_connection()
    cursor = conn.cursor()
    
    for item in sales_data:
        # Save sales
        cursor.execute('''
            INSERT OR REPLACE INTO daily_sales 
            (date, item_num, quantity_sold, price, revenue, cost, profit)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            date,
            item['item_num'],
            item['sold'],
            item['price'],
            item['sales'],
            item['cost'] * item['sold'],
            item['profit']
        ))
        
        # Save inventory snapshot
        cursor.execute('''
            INSERT OR REPLACE INTO inventory_snapshots
            (date, item_num, current_level, capacity)
            VALUES (?, ?, ?, ?)
        ''', (
            date,
            item['item_num'],
            item['inventory'],
            item['capacity']
        ))
    
    conn.commit()
    conn.close()

def get_latest_inventory() -> List[Dict]:
    """Get most recent inventory levels."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT i.item_num, i.item_name, i.capacity, 
               COALESCE(inv.current_level, i.capacity) as current_level,
               inv.date
        FROM items i
        LEFT JOIN inventory_snapshots inv ON i.item_num = inv.item_num
        WHERE i.active = 1 AND (inv.date = (
            SELECT MAX(date) FROM inventory_snapshots WHERE item_num = i.item_num
        ) OR inv.date IS NULL)
        ORDER BY i.item_num
    ''')
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def get_sales_summary(start_date: str, end_date: str) -> Dict:
    """Get sales summary for date range."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            SUM(quantity_sold) as total_items,
            SUM(revenue) as total_revenue,
            SUM(cost) as total_cost,
            SUM(profit) as total_profit
        FROM daily_sales
        WHERE date BETWEEN ? AND ?
    ''', (start_date, end_date))
    
    result = dict(cursor.fetchone())
    conn.close()
    return result

def get_setting(key: str) -> Optional[str]:
    """Get setting value."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    result = cursor.fetchone()
    conn.close()
    return result['value'] if result else None

def set_setting(key: str, value: str):
    """Set setting value."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

def seed_default_items():
    """Seed items table with default vending machine items (no CSV needed)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM items')
    if cursor.fetchone()[0] > 0:
        conn.close()
        return False

    items = [
        ("0111", "Gold Fish", 7, 0.55),
        ("0113", "Kettle", 7, 0.50),
        ("0115", "Kettle", 7, 0.50),
        ("0117", "Pretzels", 7, 0.40),
        ("0121", "Lays", 7, 0.40),
        ("0123", "Lays", 7, 0.40),
        ("0125", "Lays", 7, 0.40),
        ("0127", "Choc Chips", 7, 0.30),
        ("0130", "Granola Bar", 14, 0.20),
        ("0131", "Slim Jim", 14, 0.20),
        ("0132", "Cheese Crackers", 14, 0.50),
        ("0133", "Wafer", 14, 0.30),
        ("0134", "Kinder", 14, 0.90),
        ("0135", "Trail Mix", 14, 0.40),
        ("0136", "Peanuts", 14, 0.20),
        ("0137", "M&M's", 14, 1.10),
        ("0140", "Coca Cola", 15, 0.33),
        ("0141", "Sprite", 15, 0.33),
        ("0142", "Coca Cola", 15, 0.33),
        ("0143", "Jupiña", 15, 0.45),
        ("0144", "Dr Pepper", 15, 0.45),
        ("0145", "Monster", 15, 1.75),
        ("0146", "Iron Beer", 15, 0.55),
    ]

    cursor.executemany(
        'INSERT INTO items (item_num, item_name, capacity, unit_cost) VALUES (?, ?, ?, ?)',
        items
    )
    conn.commit()
    conn.close()
    return True


if __name__ == '__main__':
    print("Initializing database...")
    init_database()
    print("Database initialized successfully!")

    # Try CSV first, fall back to built-in defaults
    try:
        migrate_items_from_csv()
        print("Items migrated from CSV!")
    except FileNotFoundError:
        if seed_default_items():
            print("Items seeded from defaults!")
        else:
            print("Items already exist, skipping.")
