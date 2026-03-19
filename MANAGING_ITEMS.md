# Managing Items - Simple Guide

## ✅ You Don't Need CSV Anymore!

Everything is now in the database. Use the **dashboard** or **SQL commands**.

---

## Option 1: Dashboard (Easiest)

### View Items
1. Go to http://localhost:5001
2. Click **"Items"** in navigation
3. See all your items

### Add New Item
1. Go to Items page
2. Fill in the form:
   - Item Number: `0147`
   - Item Name: `Red Bull`
   - Capacity: `15`
   - Unit Cost: `1.75`
3. Click **"Add Item"**

### Edit Item
1. Go to Items page
2. Change values directly in the table
3. Click **"Save"** for that row

### Delete Item
1. Go to Items page
2. Click **"Delete"** button
3. Confirm

---

## Option 2: SQL Commands (Advanced)

### View All Items
```bash
cd /Users/e150302/code/py/vending-inv
sqlite3 vending.db "SELECT * FROM items;"
```

### Add New Item
```bash
sqlite3 vending.db "INSERT INTO items (item_num, item_name, capacity, unit_cost) VALUES ('0147', 'Red Bull', 15, 1.75);"
```

### Update Item Price
```bash
sqlite3 vending.db "UPDATE items SET unit_cost = 1.85 WHERE item_num = '0147';"
```

### Update Item Name
```bash
sqlite3 vending.db "UPDATE items SET item_name = 'Monster Energy' WHERE item_num = '0145';"
```

### Update Capacity
```bash
sqlite3 vending.db "UPDATE items SET capacity = 20 WHERE item_num = '0140';"
```

### Delete Item
```bash
sqlite3 vending.db "UPDATE items SET active = 0 WHERE item_num = '0147';"
```

### View Only Active Items
```bash
sqlite3 vending.db "SELECT item_num, item_name, capacity, unit_cost FROM items WHERE active = 1;"
```

---

## Option 3: Python Script (Bulk Changes)

Create a file `update_items.py`:

```python
#!/usr/bin/env python3
import database as db

# Add multiple items
items = [
    ('0147', 'Red Bull', 15, 1.75),
    ('0148', 'Gatorade', 15, 1.50),
]

conn = db.get_connection()
cursor = conn.cursor()

for item_num, name, capacity, cost in items:
    cursor.execute('''
        INSERT OR REPLACE INTO items (item_num, item_name, capacity, unit_cost)
        VALUES (?, ?, ?, ?)
    ''', (item_num, name, capacity, cost))

conn.commit()
conn.close()
print("Items updated!")
```

Run it:
```bash
python3 update_items.py
```

---

## What About items.csv?

**You can delete it or keep it as backup.**

The database is now the source of truth. The CSV is no longer used.

If you want to keep CSV as backup:
```bash
# Export database to CSV
sqlite3 -header -csv vending.db "SELECT item_num, item_name, capacity, unit_cost FROM items WHERE active = 1;" > in/items_backup.csv
```

---

## Common Tasks

### Change All Prices by 10%
```bash
sqlite3 vending.db "UPDATE items SET unit_cost = unit_cost * 1.10;"
```

### See Items Low on Stock (from last report)
```bash
sqlite3 vending.db "
SELECT i.item_name, inv.current_level, i.capacity
FROM items i
JOIN inventory_snapshots inv ON i.item_num = inv.item_num
WHERE inv.date = (SELECT MAX(date) FROM inventory_snapshots)
  AND inv.current_level < 3
ORDER BY inv.current_level;
"
```

### See Best Sellers (Last 30 Days)
```bash
sqlite3 vending.db "
SELECT i.item_name, SUM(ds.quantity_sold) as total_sold
FROM daily_sales ds
JOIN items i ON ds.item_num = i.item_num
WHERE ds.date >= date('now', '-30 days')
GROUP BY ds.item_num
ORDER BY total_sold DESC
LIMIT 10;
"
```

---

## Quick Reference

| Task | Method |
|------|--------|
| View items | Dashboard → Items |
| Add item | Dashboard → Items → Fill form |
| Edit item | Dashboard → Items → Edit inline |
| Delete item | Dashboard → Items → Delete button |
| Bulk changes | SQL commands or Python script |
| Backup | Export to CSV (see above) |

---

## Pro Tips

1. **Use Dashboard for daily tasks** (easiest)
2. **Use SQL for bulk updates** (faster for many items)
3. **Backup database regularly:**
   ```bash
   cp vending.db vending_backup_$(date +%Y%m%d).db
   ```

4. **View database in GUI:**
   - Download: https://sqlitebrowser.org/
   - Open `vending.db`
   - Browse/edit visually

---

## Need Help?

**View database structure:**
```bash
sqlite3 vending.db ".schema items"
```

**Interactive SQL:**
```bash
sqlite3 vending.db
# Now you can type SQL commands
# Type .quit to exit
```

**Check what's in database:**
```bash
sqlite3 vending.db "SELECT COUNT(*) FROM items;"
sqlite3 vending.db "SELECT COUNT(*) FROM daily_sales;"
```

---

**Bottom line:** Use the dashboard for 99% of tasks. It's easier and safer!
