#!/usr/bin/env python3
"""Database schema and operations — v3 (simplified)."""
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

    # Slots — one row per physical machine slot
    c.execute('''CREATE TABLE IF NOT EXISTS slots (
        item_num  TEXT PRIMARY KEY,
        name      TEXT NOT NULL,
        capacity  INTEGER NOT NULL,
        home_stock INTEGER NOT NULL DEFAULT 0,
        active    INTEGER DEFAULT 1
    )''')

    # Restocks — one header row per restock visit
    c.execute('''CREATE TABLE IF NOT EXISTS restocks (
        id    INTEGER PRIMARY KEY AUTOINCREMENT,
        date  DATE NOT NULL,
        notes TEXT
    )''')

    # Restock line items — what each slot was filled to
    c.execute('''CREATE TABLE IF NOT EXISTS restock_items (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        restock_id INTEGER NOT NULL,
        item_num   TEXT NOT NULL,
        qty_filled INTEGER NOT NULL,
        FOREIGN KEY (restock_id) REFERENCES restocks(id),
        FOREIGN KEY (item_num)   REFERENCES slots(item_num)
    )''')

    # Daily sales — written by collect_data.py (unchanged)
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

    conn.commit()
    conn.close()


def migrate_from_v2():
    """
    One-time migration: copy data from the old products/items schema into slots.
    Safe to run multiple times — skips if slots already populated.
    """
    conn = get_connection()
    c = conn.cursor()

    # Check if we already migrated
    c.execute("SELECT COUNT(*) FROM slots")
    if c.fetchone()[0] > 0:
        conn.close()
        return False

    # Check if old tables exist
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'")
    if not c.fetchone():
        conn.close()
        return False

    print("Migrating v2 → v3 schema...")

    # Pull old items + home_qty from products if linked
    c.execute('''
        SELECT i.item_num, i.item_name, i.capacity, i.unit_cost,
               COALESCE(p.home_qty, 0) as home_qty
        FROM items i
        LEFT JOIN products p ON i.product_id = p.id
        WHERE i.active = 1
        ORDER BY i.item_num
    ''')
    rows = c.fetchall()

    for row in rows:
        c.execute('''INSERT OR IGNORE INTO slots (item_num, name, capacity, home_stock)
                     VALUES (?, ?, ?, ?)''',
                  (row['item_num'], row['item_name'], row['capacity'], row['home_qty']))

    # Migrate last_restock_date from settings (already in same table, no action needed)

    conn.commit()
    conn.close()
    print(f"  Migrated {len(rows)} slots.")
    return True


def seed_slots():
    """Seed slots for a fresh install (no old DB to migrate from)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM slots")
    if c.fetchone()[0] > 0:
        conn.close()
        return False

    default_slots = [
        # Big snacks row 1 (cap 7)
        ("0111", "Kettle",      7,  0),
        ("0113", "Kettle",      7,  0),
        ("0115", "Pretzels",    7,  0),
        ("0117", "Gold Fish",   7,  0),
        # Big snacks row 2 (cap 7)
        ("0121", "Lays",        7,  0),
        ("0123", "Lays",        7,  0),
        ("0125", "Lays",        7,  0),
        ("0127", "Choc Chips",  7,  0),
        # Small snacks (cap 14)
        ("0130", "Vanil Wafer", 14, 0),
        ("0131", "Choc Wafer",  14, 0),
        ("0132", "Oreo",        14, 0),
        ("0133", "Mars Bar",    14, 0),
        ("0134", "Kinder",      14, 0),
        ("0135", "Trail Mix",   14, 0),
        ("0136", "Peanuts",     14, 0),
        ("0137", "M&M's",       14, 0),
        # Drinks (cap 15 or 10)
        ("0140", "Coca Cola",   15, 0),
        ("0141", "Sprite",      15, 0),
        ("0142", "Materva",     15, 0),
        ("0143", "Jupina",      15, 0),
        ("0144", "Iron Beer",   15, 0),
        ("0145", "Monster",     10, 0),
        ("0146", "Water",       10, 0),
    ]
    c.executemany('INSERT INTO slots (item_num, name, capacity, home_stock) VALUES (?,?,?,?)',
                  default_slots)
    conn.commit()
    conn.close()
    return True


# ---------------------------------------------------------------------------
# Slot helpers
# ---------------------------------------------------------------------------

def get_slots_with_levels() -> List[Dict]:
    """
    Return all active slots with current_level calculated dynamically:
      current_level = qty_filled_at_last_restock - sold_since_that_restock
    """
    conn = get_connection()
    c = conn.cursor()

    last_restock_date = get_setting('last_restock_date') or '2000-01-01'

    # Get last qty_filled per slot from restock_items
    c.execute('''
        SELECT ri.item_num, ri.qty_filled
        FROM restock_items ri
        JOIN restocks r ON ri.restock_id = r.id
        WHERE r.date = (
            SELECT MAX(r2.date) FROM restocks r2
            JOIN restock_items ri2 ON ri2.restock_id = r2.id
            WHERE ri2.item_num = ri.item_num
        )
    ''')
    restock_levels = {row['item_num']: row['qty_filled'] for row in c.fetchall()}

    # Sales since last restock
    c.execute('''SELECT item_num, SUM(quantity_sold) as sold
                 FROM daily_sales WHERE date > ?
                 GROUP BY item_num''', (last_restock_date,))
    sold_since = {row['item_num']: row['sold'] for row in c.fetchall()}

    c.execute('SELECT * FROM slots WHERE active = 1 ORDER BY item_num')
    slots = []
    for row in c.fetchall():
        s = dict(row)
        restock_qty = restock_levels.get(s['item_num'], s['capacity'])
        sold = sold_since.get(s['item_num'], 0)
        s['current_level'] = max(0, restock_qty - sold)
        slots.append(s)

    conn.close()
    return slots


def get_slot(item_num: str) -> Optional[Dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM slots WHERE item_num = ?', (item_num,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_slot(item_num: str, name: str, capacity: int, home_stock: int):
    """Update a slot. home_stock is shared — synced to all slots with the same name."""
    conn = get_connection()
    c = conn.cursor()
    # Get old name to know if we're renaming
    c.execute('SELECT name FROM slots WHERE item_num=?', (item_num,))
    old = c.fetchone()
    old_name = old['name'] if old else None

    # Update this slot
    c.execute('UPDATE slots SET name=?, capacity=?, home_stock=? WHERE item_num=?',
              (name, capacity, home_stock, item_num))

    # Sync home_stock to all slots sharing the new name
    c.execute('UPDATE slots SET home_stock=? WHERE name=?', (home_stock, name))

    conn.commit()
    conn.close()


def update_home_stock(item_num: str, home_stock: int):
    """Update home_stock for all slots sharing the same product name."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT name FROM slots WHERE item_num=?', (item_num,))
    row = c.fetchone()
    if row:
        c.execute('UPDATE slots SET home_stock=? WHERE name=?', (home_stock, row['name']))
    conn.commit()
    conn.close()


def get_products() -> List[Dict]:
    """Return unique products (grouped by name) with total home_stock and slot list."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT name, home_stock,
                        COUNT(*) as slot_count,
                        GROUP_CONCAT(item_num, ', ') as slots,
                        MAX(capacity) as capacity
                 FROM slots WHERE active=1
                 GROUP BY name ORDER BY name''')
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results


def update_product(name: str, new_name: str, home_stock: int):
    """Rename a product and update home_stock across all its slots."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE slots SET name=?, home_stock=? WHERE name=?',
              (new_name, home_stock, name))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Restock helpers
# ---------------------------------------------------------------------------

def save_restock(date: str, filled: Dict[str, int], notes: str = '') -> int:
    """
    Save a restock event. filled = {item_num: qty_filled}.
    Deducts qty_filled from home_stock for each slot.
    Returns the restock id.
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT INTO restocks (date, notes) VALUES (?, ?)', (date, notes))
    restock_id = c.lastrowid

    for item_num, qty in filled.items():
        if qty is None:
            continue
        c.execute('INSERT INTO restock_items (restock_id, item_num, qty_filled) VALUES (?,?,?)',
                  (restock_id, item_num, qty))
        # Deduct from home stock (floor at 0)
        c.execute('UPDATE slots SET home_stock = MAX(home_stock - ?, 0) WHERE item_num = ?',
                  (qty, item_num))

    # Update last_restock_date setting
    c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
              ('last_restock_date', date))

    conn.commit()
    conn.close()
    return restock_id


def get_last_restock() -> Optional[Dict]:
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT r.id, r.date, r.notes, COUNT(ri.id) as slot_count
                 FROM restocks r LEFT JOIN restock_items ri ON ri.restock_id = r.id
                 GROUP BY r.id ORDER BY r.date DESC LIMIT 1''')
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


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
    """For CSV export — uses current slot name, not stale item_name."""
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
    c.execute('SELECT value FROM settings WHERE key = ?', (key,))
    row = c.fetchone()
    conn.close()
    return row['value'] if row else None


def set_setting(key: str, value: str):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
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
