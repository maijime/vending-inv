#!/usr/bin/env python3
"""Database schema and operations for vending machine tracking."""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = 'vending.db'

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    conn = get_connection()
    c = conn.cursor()

    # Products — the actual snack/drink you buy and store
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        unit_cost REAL NOT NULL DEFAULT 0,
        category TEXT NOT NULL DEFAULT 'Other',
        home_qty INTEGER NOT NULL DEFAULT 0,
        active INTEGER DEFAULT 1
    )''')

    # Slots — positions in the machine, each assigned a product
    c.execute('''CREATE TABLE IF NOT EXISTS items (
        item_num TEXT PRIMARY KEY,
        item_name TEXT NOT NULL,
        capacity INTEGER NOT NULL,
        unit_cost REAL NOT NULL,
        product_id INTEGER,
        active INTEGER DEFAULT 1,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS daily_sales (
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
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS inventory_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date DATE NOT NULL,
        item_num TEXT NOT NULL,
        current_level INTEGER NOT NULL,
        capacity INTEGER NOT NULL,
        FOREIGN KEY (item_num) REFERENCES items(item_num),
        UNIQUE(date, item_num)
    )''')

    # Keep home_inventory table for backward compat but products.home_qty is the source of truth
    c.execute('''CREATE TABLE IF NOT EXISTS home_inventory (
        item_num TEXT PRIMARY KEY,
        quantity INTEGER NOT NULL DEFAULT 0,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (item_num) REFERENCES items(item_num)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''')

    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('low_stock_threshold', '3')")

    # Add product_id column if missing (migration)
    try:
        c.execute("ALTER TABLE items ADD COLUMN product_id INTEGER REFERENCES products(id)")
    except:
        pass

    # Add product_id to daily_sales for slot rotation tracking
    try:
        c.execute("ALTER TABLE daily_sales ADD COLUMN product_id INTEGER REFERENCES products(id)")
    except:
        pass

    conn.commit()
    conn.close()


def migrate_products():
    """Create products from existing items, grouping duplicates."""
    conn = get_connection()
    c = conn.cursor()

    # Skip if products already exist
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] > 0:
        conn.close()
        return False

    # Product definitions: name -> (unit_cost, category)
    product_defs = {
        "Gold Fish": (0.55, "Salty Snacks"),
        "Kettle": (0.50, "Chips"),
        "Pretzels": (0.40, "Salty Snacks"),
        "Lays": (0.40, "Chips"),
        "Choc Chips": (0.30, "Sweets"),
        "Granola Bar": (0.20, "Sweets"),
        "Slim Jim": (0.20, "Salty Snacks"),
        "Cheese Crackers": (0.50, "Salty Snacks"),
        "Wafer": (0.30, "Sweets"),
        "Kinder": (0.90, "Sweets"),
        "Trail Mix": (0.40, "Salty Snacks"),
        "Peanuts": (0.20, "Salty Snacks"),
        "M&M's": (1.10, "Sweets"),
        "Coca Cola": (0.33, "Drinks"),
        "Sprite": (0.33, "Drinks"),
        "Jupiña": (0.45, "Drinks"),
        "Dr Pepper": (0.45, "Drinks"),
        "Monster": (1.75, "Drinks"),
        "Iron Beer": (0.55, "Drinks"),
    }

    # Insert products
    product_ids = {}
    for name, (cost, cat) in product_defs.items():
        c.execute("INSERT INTO products (name, unit_cost, category) VALUES (?, ?, ?)", (name, cost, cat))
        product_ids[name] = c.lastrowid

    # Link slots to products
    c.execute("SELECT item_num, item_name FROM items WHERE active = 1")
    for row in c.fetchall():
        pid = product_ids.get(row['item_name'])
        if pid:
            c.execute("UPDATE items SET product_id = ? WHERE item_num = ?", (pid, row['item_num']))

    conn.commit()
    conn.close()
    return True


def save_daily_data(date: str, sales_data: List[Dict]):
    conn = get_connection()
    c = conn.cursor()
    # Get current slot→product mapping
    c.execute('SELECT item_num, product_id FROM items WHERE active = 1')
    slot_products = {row['item_num']: row['product_id'] for row in c.fetchall()}
    for item in sales_data:
        pid = slot_products.get(item['item_num'])
        c.execute('''INSERT OR REPLACE INTO daily_sales
            (date, item_num, quantity_sold, price, revenue, cost, profit, product_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (date, item['item_num'], item['sold'], item['price'],
             item['sales'], item['cost'] * item['sold'], item['profit'], pid))
        c.execute('''INSERT OR REPLACE INTO inventory_snapshots
            (date, item_num, current_level, capacity)
            VALUES (?, ?, ?, ?)''',
            (date, item['item_num'], item['inventory'], item['capacity']))
    conn.commit()
    conn.close()


def get_latest_inventory() -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT i.item_num, i.item_name, i.capacity, i.product_id,
               COALESCE(inv.current_level, i.capacity) as current_level, inv.date
        FROM items i
        LEFT JOIN inventory_snapshots inv ON i.item_num = inv.item_num
            AND inv.date = (SELECT MAX(date) FROM inventory_snapshots WHERE item_num = i.item_num)
        WHERE i.active = 1
        ORDER BY i.item_num
    ''')
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def get_sales_summary(start_date: str, end_date: str) -> Dict:
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT SUM(quantity_sold) as total_items, SUM(revenue) as total_revenue,
                        SUM(cost) as total_cost, SUM(profit) as total_profit
                 FROM daily_sales WHERE date BETWEEN ? AND ?''', (start_date, end_date))
    result = dict(c.fetchone())
    conn.close()
    return result


def get_setting(key: str) -> Optional[str]:
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key = ?', (key,))
    result = c.fetchone()
    conn.close()
    return result['value'] if result else None


def set_setting(key: str, value: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()


def seed_default_items():
    """Seed items table with default slots (no CSV needed)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM items')
    if c.fetchone()[0] > 0:
        conn.close()
        return False

    slots = [
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
        ("0145", "Monster", 10, 1.75),
        ("0146", "Iron Beer", 15, 0.55),
    ]
    c.executemany('INSERT INTO items (item_num, item_name, capacity, unit_cost) VALUES (?, ?, ?, ?)', slots)
    conn.commit()
    conn.close()
    return True


def migrate_items_from_csv(csv_path: str = 'in/items.csv'):
    import csv
    default_capacities = {
        "0111": 7, "0113": 7, "0115": 7, "0117": 7,
        "0121": 7, "0123": 7, "0125": 7, "0127": 7,
        "0130": 14, "0131": 14, "0132": 14, "0133": 14,
        "0134": 14, "0135": 14, "0136": 14, "0137": 14,
        "0140": 15, "0141": 15, "0142": 15, "0143": 15,
        "0144": 15, "0145": 10, "0146": 15
    }
    conn = get_connection()
    c = conn.cursor()
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            item_num = row['iNum'].zfill(4)
            capacity = int(row.get('Cap', row.get('capacity', default_capacities.get(item_num, 10))))
            c.execute('INSERT OR REPLACE INTO items (item_num, item_name, capacity, unit_cost) VALUES (?, ?, ?, ?)',
                      (item_num, row['iName'], capacity, float(row.get('cost', row.get('Cost', 0)))))
    conn.commit()
    conn.close()


if __name__ == '__main__':
    print("Initializing database...")
    init_database()
    print("Database initialized!")

    try:
        migrate_items_from_csv()
        print("Items migrated from CSV!")
    except FileNotFoundError:
        if seed_default_items():
            print("Items seeded from defaults!")
        else:
            print("Items already exist.")

    if migrate_products():
        print("Products created and linked to slots!")
    else:
        print("Products already exist.")
