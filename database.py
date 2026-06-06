#!/usr/bin/env python3
"""Database schema and operations — v3.1 (per-slot restock tracking)."""
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = 'vending.db'

CATEGORIES = ['Snacks', 'Small Snacks', 'Drinks']

# Default category by item_num prefix
def _default_category(item_num: str) -> str:
    if item_num.startswith('014'):
        return 'Drinks'
    if item_num.startswith('013'):
        return 'Small Snacks'
    return 'Snacks'


def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    conn = get_connection()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS slots (
        item_num       TEXT PRIMARY KEY,
        name           TEXT NOT NULL,
        capacity       INTEGER NOT NULL,
        home_stock     INTEGER NOT NULL DEFAULT 0,
        category       TEXT NOT NULL DEFAULT 'Snacks',
        last_fill_qty  INTEGER,
        last_fill_date DATE,
        active         INTEGER DEFAULT 1
    )''')

    # Keep restocks table for history (no longer used for level calc)
    c.execute('''CREATE TABLE IF NOT EXISTS restocks (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        date  DATE NOT NULL,
        notes TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS restock_items (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        restock_id INTEGER NOT NULL,
        item_num   TEXT NOT NULL,
        qty_filled INTEGER NOT NULL,
        FOREIGN KEY (restock_id) REFERENCES restocks(id),
        FOREIGN KEY (item_num)   REFERENCES slots(item_num)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS daily_sales (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        date          DATE NOT NULL,
        item_num      TEXT NOT NULL,
        quantity_sold INTEGER NOT NULL,
        price         REAL NOT NULL,
        revenue       REAL NOT NULL,
        cost          REAL NOT NULL,
        profit        REAL NOT NULL,
        UNIQUE(date, item_num)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )''')

    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('low_stock_threshold', '3')")

    # Migrations for existing installs
    for col, definition in [
        ('category',       "TEXT NOT NULL DEFAULT 'Snacks'"),
        ('last_fill_qty',  'INTEGER'),
        ('last_fill_date', 'DATE'),
    ]:
        try:
            c.execute(f'ALTER TABLE slots ADD COLUMN {col} {definition}')
        except Exception:
            pass  # Column already exists

    # Backfill category from item_num for any row that hasn't been manually set
    # (runs every startup but is idempotent for correctly-set rows)
    c.execute("SELECT item_num, category FROM slots")
    for row in c.fetchall():
        correct = _default_category(row['item_num'])
        # Only overwrite if still at default or blank
        if not row['category'] or row['category'] == 'Snacks' and row['item_num'].startswith('013') or \
           row['category'] == 'Snacks' and row['item_num'].startswith('014'):
            c.execute('UPDATE slots SET category=? WHERE item_num=?',
                      (correct, row['item_num']))

    conn.commit()
    conn.close()


def migrate_from_v2():
    """One-time migration from old products/items schema. Safe to run multiple times."""
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM slots")
    if c.fetchone()[0] > 0:
        conn.close()
        return False

    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'")
    if not c.fetchone():
        conn.close()
        return False

    print("Migrating v2 → v3 schema...")
    c.execute('''
        SELECT i.item_num, i.item_name, i.capacity,
               COALESCE(p.home_qty, 0) as home_qty
        FROM items i
        LEFT JOIN products p ON i.product_id = p.id
        WHERE i.active = 1
        ORDER BY i.item_num
    ''')
    rows = c.fetchall()
    for row in rows:
        cat = _default_category(row['item_num'])
        c.execute('''INSERT OR IGNORE INTO slots (item_num, name, capacity, home_stock, category)
                     VALUES (?, ?, ?, ?, ?)''',
                  (row['item_num'], row['item_name'], row['capacity'], row['home_qty'], cat))

    conn.commit()
    conn.close()
    print(f"  Migrated {len(rows)} slots.")
    return True


def seed_slots():
    """Seed slots for a fresh install."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM slots")
    if c.fetchone()[0] > 0:
        conn.close()
        return False

    default_slots = [
        ("0111", "Kettle",      7,  0, "Snacks"),
        ("0113", "Kettle",      7,  0, "Snacks"),
        ("0115", "Pretzels",    7,  0, "Snacks"),
        ("0117", "Gold Fish",   7,  0, "Snacks"),
        ("0121", "Lays",        7,  0, "Snacks"),
        ("0123", "Lays",        7,  0, "Snacks"),
        ("0125", "Lays",        7,  0, "Snacks"),
        ("0127", "Choc Chips",  7,  0, "Snacks"),
        ("0130", "Vanil Wafer", 14, 0, "Small Snacks"),
        ("0131", "Choc Wafer",  14, 0, "Small Snacks"),
        ("0132", "Oreo",        14, 0, "Small Snacks"),
        ("0133", "Mars Bar",    14, 0, "Small Snacks"),
        ("0134", "Kinder",      14, 0, "Small Snacks"),
        ("0135", "Trail Mix",   14, 0, "Small Snacks"),
        ("0136", "Peanuts",     14, 0, "Small Snacks"),
        ("0137", "M&M's",       14, 0, "Small Snacks"),
        ("0140", "Coca Cola",   15, 0, "Drinks"),
        ("0141", "Sprite",      15, 0, "Drinks"),
        ("0142", "Materva",     15, 0, "Drinks"),
        ("0143", "Jupiña",      15, 0, "Drinks"),
        ("0144", "Iron Beer",   15, 0, "Drinks"),
        ("0145", "Monster",     10, 0, "Drinks"),
        ("0146", "Water",       10, 0, "Drinks"),
    ]
    c.executemany(
        'INSERT INTO slots (item_num, name, capacity, home_stock, category) VALUES (?,?,?,?,?)',
        default_slots)
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------------------------
# Slot helpers
# ---------------------------------------------------------------------------

def get_slots_with_levels() -> List[Dict]:
    """
    Per-slot level calculation:
      current_level = last_fill_qty - SUM(sold since last_fill_date)
    Falls back to capacity if slot has never been filled.
    """
    conn = get_connection()
    c = conn.cursor()

    c.execute('SELECT * FROM slots WHERE active=1 ORDER BY item_num')
    slot_rows = [dict(row) for row in c.fetchall()]

    slots = []
    for s in slot_rows:
        if s['last_fill_date'] and s['last_fill_qty'] is not None:
            c.execute('''SELECT COALESCE(SUM(quantity_sold), 0) as sold
                         FROM daily_sales
                         WHERE item_num=? AND date >= ?''',
                      (s['item_num'], s['last_fill_date']))
            sold = c.fetchone()['sold']
            s['current_level'] = max(0, s['last_fill_qty'] - sold)
        else:
            s['current_level'] = 0  # Never filled — unknown
        slots.append(s)

    conn.close()
    return slots


def get_slot(item_num: str) -> Optional[Dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM slots WHERE item_num=?', (item_num,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def fill_slot(item_num: str, qty: int, date: str) -> bool:
    """Log a fill for a single slot — the core restock action."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''UPDATE slots SET last_fill_qty=?, last_fill_date=?
                 WHERE item_num=?''', (qty, date, item_num))
    # Also deduct from shared home_stock by name
    c.execute('SELECT name FROM slots WHERE item_num=?', (item_num,))
    row = c.fetchone()
    if row:
        c.execute('UPDATE slots SET home_stock = MAX(home_stock - ?, 0) WHERE name=?',
                  (qty, row['name']))
    conn.commit()
    conn.close()
    return True


def swap_slot_product(item_num: str, new_name: str) -> bool:
    """Swap the product in a slot to a different product (same category)."""
    conn = get_connection()
    c = conn.cursor()
    # Get new product's home_stock if it already exists elsewhere
    c.execute('SELECT home_stock FROM slots WHERE name=? AND active=1 LIMIT 1', (new_name,))
    row = c.fetchone()
    home_stock = row['home_stock'] if row else 0
    c.execute('''UPDATE slots SET name=?, home_stock=?,
                 last_fill_qty=NULL, last_fill_date=NULL
                 WHERE item_num=?''',
              (new_name, home_stock, item_num))
    conn.commit()
    conn.close()
    return True


def update_slot(item_num: str, name: str, capacity: int, home_stock: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE slots SET name=?, capacity=?, home_stock=? WHERE item_num=?',
              (name, capacity, home_stock, item_num))
    c.execute('UPDATE slots SET home_stock=? WHERE name=?', (home_stock, name))
    conn.commit()
    conn.close()


def update_home_stock(item_num: str, home_stock: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT name FROM slots WHERE item_num=?', (item_num,))
    row = c.fetchone()
    if row:
        c.execute('UPDATE slots SET home_stock=? WHERE name=?', (home_stock, row['name']))
    conn.commit()
    conn.close()


def get_products() -> List[Dict]:
    """Unique products grouped by name, with category."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT name, category, home_stock,
                        COUNT(*) as slot_count,
                        GROUP_CONCAT(item_num, ', ') as slots,
                        MAX(capacity) as capacity
                 FROM slots WHERE active=1
                 GROUP BY name ORDER BY category, name''')
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def get_products_by_category(category: str) -> List[Dict]:
    """Products available for a given category (for slot swap picker)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT DISTINCT name, home_stock
                 FROM slots WHERE active=1 AND category=?
                 ORDER BY name''', (category,))
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def update_product(name: str, new_name: str, home_stock: int, category: str = None):
    conn = get_connection()
    c = conn.cursor()
    if category:
        c.execute('UPDATE slots SET name=?, home_stock=?, category=? WHERE name=?',
                  (new_name, home_stock, category, name))
    else:
        c.execute('UPDATE slots SET name=?, home_stock=? WHERE name=?',
                  (new_name, home_stock, name))
    conn.commit()
    conn.close()


def delete_product(name: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT COUNT(*) FROM daily_sales ds
                 JOIN slots s ON ds.item_num = s.item_num
                 WHERE s.name=?''', (name,))
    if c.fetchone()[0] > 0:
        conn.close()
        return False
    c.execute('UPDATE slots SET active=0 WHERE name=?', (name,))
    conn.commit()
    conn.close()
    return True


def add_slot(item_num: str, name: str, capacity: int,
             home_stock: int = 0, category: str = 'Snacks') -> bool:
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO slots (item_num, name, capacity, home_stock, category)
                     VALUES (?,?,?,?,?)''',
                  (item_num, name, capacity, home_stock, category))
        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False


# ---------------------------------------------------------------------------
# Sales helpers
# ---------------------------------------------------------------------------

def get_sales_summary(start_date: str, end_date: str) -> Dict:
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT COALESCE(SUM(quantity_sold),0) as total_items,
                        COALESCE(SUM(revenue),0)       as total_revenue,
                        COALESCE(SUM(profit),0)        as total_profit
                 FROM daily_sales WHERE date BETWEEN ? AND ?''', (start_date, end_date))
    result = dict(c.fetchone())
    conn.close()
    return result


def get_sales_by_item(start_date: str, end_date: str) -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT s.name, ds.item_num,
                        SUM(ds.quantity_sold) as total_sold,
                        SUM(ds.revenue)       as total_revenue,
                        SUM(ds.profit)        as total_profit
                 FROM daily_sales ds
                 LEFT JOIN slots s ON ds.item_num = s.item_num
                 WHERE ds.date BETWEEN ? AND ?
                 GROUP BY ds.item_num
                 ORDER BY total_sold DESC''', (start_date, end_date))
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def get_daily_sales(start_date: str, end_date: str) -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT date,
                        SUM(quantity_sold) as items_sold,
                        SUM(revenue)       as revenue,
                        SUM(profit)        as profit
                 FROM daily_sales WHERE date BETWEEN ? AND ?
                 GROUP BY date ORDER BY date DESC''', (start_date, end_date))
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def get_sales_export(start_date: str, end_date: str) -> List[Dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT ds.date, ds.item_num,
                        COALESCE(s.name, ds.item_num) as item_name,
                        ds.quantity_sold, ds.price, ds.revenue, ds.cost, ds.profit
                 FROM daily_sales ds
                 LEFT JOIN slots s ON ds.item_num = s.item_num
                 WHERE ds.date BETWEEN ? AND ?
                 ORDER BY ds.date DESC, ds.item_num''', (start_date, end_date))
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def get_setting(key: str) -> Optional[str]:
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key=?', (key,))
    row = c.fetchone()
    conn.close()
    return row['value'] if row else None


def set_setting(key: str, value: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)', (key, value))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    init_database()
    print("Database initialized.")
    if migrate_from_v2():
        print("Migration from v2 complete.")
    elif seed_slots():
        print("Slots seeded (fresh install).")
    else:
        print("Slots already exist — nothing to do.")
