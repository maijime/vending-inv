#!/usr/bin/env python3
"""One-time script to set unit costs for all products."""
import sqlite3

DB_PATH = 'vending.db'

# Cost per unit ($) — adjust any before running
COSTS = {
    # Snacks
    'Kettle':      0.58,
    'Pretzels':    0.25,
    'Gold Fish':   0.35,
    'Lays':        0.26,
    'Choc Chips':  0.23,
    # Small Snacks
    'Vanil Wafer': 0.35,
    'Choc Wafer':  0.35,
    'Oreo':        0.23,
    'Mars Bar':    1.00,
    'Kinder':      0.60,
    'Trail Mix':   0.40,
    'Peanuts':     0.40,
    "M&M's":       0.70,
    # Drinks
    'Coca Cola':   0.42,
    'Sprite':      0.42,
    'Materva':     0.55,
    'Jupiña':      0.55,
    'Iron Beer':   0.55,
    'Monster':     1.42,
    'Water':       0.14,
    'Inca Kola':   0.55,
}

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

updated = []
skipped = []
for name, cost in COSTS.items():
    c.execute('UPDATE slots SET unit_cost=? WHERE name=?', (cost, name))
    if c.rowcount > 0:
        updated.append(f'  {name}: ${cost:.2f}')
    else:
        skipped.append(f'  {name} (not found in DB)')

conn.commit()
conn.close()

print(f"Updated {len(updated)} products:")
for line in updated:
    print(line)
if skipped:
    print(f"\nNot found (check spelling):")
    for line in skipped:
        print(line)
