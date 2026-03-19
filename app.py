#!/usr/bin/env python3
"""Flask web dashboard for vending machine management."""
from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime, timedelta
import database as db

app = Flask(__name__)

@app.route('/')
def index():
    """Dashboard home page."""
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Show yesterday's summary (today is usually 0 until 4pm)
    yesterday_summary = db.get_sales_summary(yesterday, yesterday)
    
    # Latest inventory
    inventory = db.get_latest_inventory()
    low_stock_threshold = int(db.get_setting('low_stock_threshold') or 3)
    low_stock_count = sum(1 for item in inventory if item['current_level'] < low_stock_threshold)
    
    # Sales since last restock (replaces "last 7 days")
    last_restock = db.get_setting('last_restock_date')
    restock_summary = None
    if last_restock:
        restock_summary = db.get_sales_summary(last_restock, today)
        restock_summary['start_date'] = last_restock
    
    return render_template('index.html',
                         today=today,
                         yesterday=yesterday,
                         yesterday_summary=yesterday_summary,
                         restock_summary=restock_summary,
                         low_stock_count=low_stock_count,
                         inventory_count=len(inventory))

@app.route('/inventory')
def inventory():
    """Inventory management page."""
    inventory_data = db.get_latest_inventory()
    low_stock_threshold = int(db.get_setting('low_stock_threshold') or 3)
    
    # Get last restock date
    last_restock = db.get_setting('last_restock_date')
    
    # Get sales since last restock
    sales_since_restock = None
    if last_restock:
        today = datetime.now().strftime('%Y-%m-%d')
        sales_since_restock = db.get_sales_summary(last_restock, today)
        sales_since_restock['start_date'] = last_restock
        sales_since_restock['end_date'] = today
    
    # Get home inventory
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT i.item_num, i.item_name, COALESCE(h.quantity, 0) as quantity
        FROM items i
        LEFT JOIN home_inventory h ON i.item_num = h.item_num
        WHERE i.active = 1
        ORDER BY i.item_num
    ''')
    home_inventory = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return render_template('inventory.html',
                         machine_inventory=inventory_data,
                         home_inventory=home_inventory,
                         low_stock_threshold=low_stock_threshold,
                         sales_since_restock=sales_since_restock)

@app.route('/check-today', methods=['GET'])
def check_today():
    """Check today's sales live without saving."""
    from collect_data import get_vending_data
    
    today = datetime.now().strftime("%Y-%m-%d")
    
    try:
        sales_data = get_vending_data(today)
        
        if not sales_data:
            return render_template('check_today.html', error="No data available", today=today)
        
        # Calculate totals
        total_sales = sum(item['sales'] for item in sales_data)
        total_profit = sum(item['profit'] for item in sales_data)
        total_items = sum(item['sold'] for item in sales_data)
        
        summary = {
            'total_revenue': total_sales,
            'total_profit': total_profit,
            'total_items': total_items
        }
        
        # Items sold
        items_sold = [item for item in sales_data if item['sold'] > 0]
        
        # Low stock
        low_stock_threshold = int(db.get_setting('low_stock_threshold') or 3)
        low_stock = [item for item in sales_data if item['inventory'] < low_stock_threshold]
        
        return render_template('check_today.html',
                             today=today,
                             summary=summary,
                             items_sold=items_sold,
                             low_stock=low_stock,
                             low_stock_threshold=low_stock_threshold,
                             current_time=datetime.now().strftime('%I:%M %p'))
        
    except Exception as e:
        return render_template('check_today.html', error=str(e), today=today)

@app.route('/restock', methods=['GET', 'POST'])
def restock():
    """Restock management page."""
    if request.method == 'POST':
        action = request.form.get('action')
        date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        conn = db.get_connection()
        cursor = conn.cursor()
        
        if action == 'restock_machine':
            # Update machine inventory and deduct from home inventory
            for key, value in request.form.items():
                if key.startswith('machine_'):
                    item_num = key.replace('machine_', '')
                    quantity = int(value) if value else 0
                    
                    if quantity > 0:
                        # Get current capacity
                        cursor.execute('SELECT capacity FROM items WHERE item_num = ?', (item_num,))
                        capacity = cursor.fetchone()['capacity']
                        
                        # Update machine inventory snapshot
                        cursor.execute('''
                            INSERT OR REPLACE INTO inventory_snapshots (date, item_num, current_level, capacity)
                            VALUES (?, ?, ?, ?)
                        ''', (date, item_num, quantity, capacity))
                        
                        # Deduct from home inventory
                        cursor.execute('''
                            INSERT OR REPLACE INTO home_inventory (item_num, quantity, last_updated)
                            VALUES (?, 
                                    COALESCE((SELECT quantity FROM home_inventory WHERE item_num = ?), 0) - ?,
                                    CURRENT_TIMESTAMP)
                        ''', (item_num, item_num, quantity))
        
        elif action == 'add_home_inventory':
            # Add items to home inventory (shopping run)
            for key, value in request.form.items():
                if key.startswith('home_'):
                    item_num = key.replace('home_', '')
                    quantity = int(value) if value else 0
                    
                    if quantity > 0:
                        cursor.execute('''
                            INSERT OR REPLACE INTO home_inventory (item_num, quantity, last_updated)
                            VALUES (?, 
                                    COALESCE((SELECT quantity FROM home_inventory WHERE item_num = ?), 0) + ?,
                                    CURRENT_TIMESTAMP)
                        ''', (item_num, item_num, quantity))
        
        conn.commit()
        conn.close()
        
        return redirect(url_for('restock'))
    
    # GET request - show restock form
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Get current machine inventory
    cursor.execute('''
        SELECT i.item_num, i.item_name, i.capacity,
               COALESCE(inv.current_level, i.capacity) as current_level
        FROM items i
        LEFT JOIN inventory_snapshots inv ON i.item_num = inv.item_num
        WHERE i.active = 1 AND (inv.date = (
            SELECT MAX(date) FROM inventory_snapshots WHERE item_num = i.item_num
        ) OR inv.date IS NULL)
        ORDER BY i.item_num
    ''')
    machine_inventory = [dict(row) for row in cursor.fetchall()]
    
    # Get home inventory
    cursor.execute('''
        SELECT i.item_num, i.item_name, COALESCE(h.quantity, 0) as quantity
        FROM items i
        LEFT JOIN home_inventory h ON i.item_num = h.item_num
        WHERE i.active = 1
        ORDER BY i.item_num
    ''')
    home_inventory = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('restock.html',
                         machine_inventory=machine_inventory,
                         home_inventory=home_inventory,
                         today=datetime.now().strftime('%Y-%m-%d'))

@app.route('/sales')
def sales():
    """Sales history page."""
    # Get date range from query params
    end_date = request.args.get('end_date', datetime.now().strftime("%Y-%m-%d"))
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    
    # Get sales data
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT date, 
               SUM(quantity_sold) as items_sold,
               SUM(revenue) as revenue,
               SUM(profit) as profit
        FROM daily_sales
        WHERE date BETWEEN ? AND ?
        GROUP BY date
        ORDER BY date DESC
    ''', (start_date, end_date))
    daily_sales = [dict(row) for row in cursor.fetchall()]
    
    # Get summary
    summary = db.get_sales_summary(start_date, end_date)
    
    # Get top sellers
    cursor.execute('''
        SELECT i.item_name, 
               SUM(ds.quantity_sold) as total_sold,
               SUM(ds.revenue) as total_revenue,
               SUM(ds.profit) as total_profit
        FROM daily_sales ds
        JOIN items i ON ds.item_num = i.item_num
        WHERE ds.date BETWEEN ? AND ?
        GROUP BY ds.item_num
        ORDER BY total_sold DESC
        LIMIT 10
    ''', (start_date, end_date))
    top_sellers = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('sales.html',
                         daily_sales=daily_sales,
                         summary=summary,
                         top_sellers=top_sellers,
                         start_date=start_date,
                         end_date=end_date)

@app.route('/items')
def items():
    """Items management page."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM items WHERE active = 1 ORDER BY item_num')
    items_list = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return render_template('items.html', items=items_list)

@app.route('/items/add', methods=['POST'])
def add_item():
    """Add new item."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO items (item_num, item_name, capacity, unit_cost)
        VALUES (?, ?, ?, ?)
    ''', (
        request.form['item_num'].zfill(4),
        request.form['item_name'],
        int(request.form['capacity']),
        float(request.form['unit_cost'])
    ))
    conn.commit()
    conn.close()
    
    return redirect(url_for('items'))

@app.route('/items/update/<item_num>', methods=['POST'])
def update_item(item_num):
    """Update item."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE items 
        SET item_name = ?, capacity = ?, unit_cost = ?
        WHERE item_num = ?
    ''', (
        request.form['item_name'],
        int(request.form['capacity']),
        float(request.form['unit_cost']),
        item_num
    ))
    conn.commit()
    conn.close()
    
    return redirect(url_for('items'))

@app.route('/items/delete/<item_num>', methods=['POST'])
def delete_item(item_num):
    """Soft delete item."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE items SET active = 0 WHERE item_num = ?', (item_num,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('items'))

@app.route('/home-inventory/update', methods=['POST'])
def update_home_inventory():
    """Update home inventory."""
    item_num = request.form['item_num']
    quantity = int(request.form['quantity'])
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO home_inventory (item_num, quantity, last_updated)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (item_num, quantity))
    conn.commit()
    conn.close()
    
    return redirect(url_for('inventory'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """Settings page."""
    if request.method == 'POST':
        db.set_setting('low_stock_threshold', request.form['low_stock_threshold'])
        return redirect(url_for('settings'))
    
    low_stock_threshold = db.get_setting('low_stock_threshold')
    
    # Check if Gmail is configured
    gmail_configured = all([
        os.getenv('GMAIL_USER'),
        os.getenv('GMAIL_APP_PASSWORD') and os.getenv('GMAIL_APP_PASSWORD') != 'your_app_password_here'
    ])
    
    return render_template('settings.html', 
                         low_stock_threshold=low_stock_threshold,
                         gmail_configured=gmail_configured)

@app.route('/api/sales-chart')
def sales_chart_data():
    """API endpoint for sales chart data."""
    days = int(request.args.get('days', 30))
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT date, SUM(revenue) as revenue, SUM(profit) as profit
        FROM daily_sales
        WHERE date BETWEEN ? AND ?
        GROUP BY date
        ORDER BY date
    ''', (start_date, end_date))
    
    data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(data)

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    print(f"\n🏪 Vending Dashboard starting on http://localhost:{port}\n")
    app.run(host='0.0.0.0', port=port, debug=True)
