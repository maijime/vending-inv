#!/usr/bin/env python3
"""Flask web dashboard for vending machine management. v2.2"""
from flask import Flask, render_template, request, redirect, url_for, jsonify, Response
from datetime import datetime, timedelta
import csv, io, os
import database as db

app = Flask(__name__)


def get_products_with_slots():
    """Get products grouped with their slot assignments."""
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT p.id, p.name, p.unit_cost, p.category, p.home_qty,
               i.item_num, i.capacity,
               COALESCE(inv.current_level, i.capacity) as current_level
        FROM products p
        JOIN items i ON i.product_id = p.id AND i.active = 1
        LEFT JOIN inventory_snapshots inv ON i.item_num = inv.item_num
            AND inv.date = (SELECT MAX(date) FROM inventory_snapshots WHERE item_num = i.item_num)
        WHERE p.active = 1
        ORDER BY p.category, p.name, i.item_num
    ''')
    rows = c.fetchall()
    conn.close()

    products = {}
    for row in rows:
        pid = row['id']
        if pid not in products:
            products[pid] = {
                'id': pid, 'name': row['name'], 'unit_cost': row['unit_cost'],
                'category': row['category'], 'home_qty': row['home_qty'], 'slots': []
            }
        products[pid]['slots'].append({
            'item_num': row['item_num'], 'capacity': row['capacity'],
            'current_level': row['current_level'],
            'need': row['capacity'] - row['current_level']
        })
    return products


@app.route('/')
def index():
    today = datetime.now().strftime("%Y-%m-%d")

    inventory = db.get_latest_inventory()
    low_stock_threshold = int(db.get_setting('low_stock_threshold') or 3)
    low_stock_count = sum(1 for item in inventory if item['current_level'] < low_stock_threshold)

    last_restock = db.get_setting('last_restock_date')
    restock_summary = None
    if last_restock:
        restock_summary = db.get_sales_summary(last_restock, today)
        restock_summary['start_date'] = last_restock

    now = datetime.now()
    week_start = now - timedelta(days=now.weekday())
    this_week = db.get_sales_summary(week_start.strftime("%Y-%m-%d"), today)
    last_week_start = week_start - timedelta(days=7)
    last_week_end = week_start - timedelta(days=1)
    last_week = db.get_sales_summary(last_week_start.strftime("%Y-%m-%d"), last_week_end.strftime("%Y-%m-%d"))
    week_comparison = {
        'this_week': this_week.get('total_revenue') or 0,
        'last_week': last_week.get('total_revenue') or 0,
    }

    conn = db.get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT CASE CAST(strftime('%w', date) AS INTEGER)
            WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday' WHEN 2 THEN 'Tuesday'
            WHEN 3 THEN 'Wednesday' WHEN 4 THEN 'Thursday' WHEN 5 THEN 'Friday'
            WHEN 6 THEN 'Saturday' END as day_name,
            ROUND(AVG(daily_total), 2) as avg_revenue
        FROM (SELECT date, SUM(revenue) as daily_total FROM daily_sales GROUP BY date)
        GROUP BY strftime('%w', date) ORDER BY avg_revenue DESC LIMIT 1
    ''')
    best_day_row = c.fetchone()
    best_day = dict(best_day_row) if best_day_row else None
    conn.close()

    hour = now.hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"

    return render_template('index.html', today=today,
                           restock_summary=restock_summary,
                           low_stock_count=low_stock_count,
                           week_comparison=week_comparison, best_day=best_day, greeting=greeting)


@app.route('/inventory')
def inventory():
    products = get_products_with_slots()
    low_stock_threshold = int(db.get_setting('low_stock_threshold') or 3)
    last_restock = db.get_setting('last_restock_date')
    sales_since_restock = None
    if last_restock:
        today = datetime.now().strftime('%Y-%m-%d')
        sales_since_restock = db.get_sales_summary(last_restock, today)
        sales_since_restock['start_date'] = last_restock

    # Group by category
    categories = {}
    for p in products.values():
        cat = p['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(p)

    return render_template('inventory.html', categories=categories, products=products,
                           low_stock_threshold=low_stock_threshold,
                           sales_since_restock=sales_since_restock)


@app.route('/inventory/update-stock', methods=['POST'])
def update_stock():
    """Update warehouse stock for a product."""
    conn = db.get_connection()
    c = conn.cursor()
    for key, value in request.form.items():
        if key.startswith('qty_') and value:
            pid = key.replace('qty_', '')
            c.execute('UPDATE products SET home_qty = ? WHERE id = ?', (int(value), pid))
    conn.commit()
    conn.close()
    return redirect(url_for('inventory'))


@app.route('/inventory/add-stock', methods=['POST'])
def add_stock():
    """Add to warehouse stock (shopping run)."""
    conn = db.get_connection()
    c = conn.cursor()
    for key, value in request.form.items():
        if key.startswith('add_') and value and int(value) > 0:
            pid = key.replace('add_', '')
            c.execute('UPDATE products SET home_qty = home_qty + ? WHERE id = ?', (int(value), pid))
    conn.commit()
    conn.close()
    return redirect(url_for('inventory'))


@app.route('/check-today')
def check_today():
    from collect_data import get_vending_data
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        sales_data = get_vending_data(today)
        if not sales_data:
            return render_template('check_today.html', error="No data available", today=today)
        total_sales = sum(item['sales'] for item in sales_data)
        total_profit = sum(item['profit'] for item in sales_data)
        summary = {'total_revenue': total_sales, 'total_profit': total_profit,
                    'total_items': sum(item['sold'] for item in sales_data)}
        items_sold = [item for item in sales_data if item['sold'] > 0]
        low_stock_threshold = int(db.get_setting('low_stock_threshold') or 3)
        low_stock = [item for item in sales_data if item['inventory'] < low_stock_threshold]
        return render_template('check_today.html', today=today, summary=summary,
                               items_sold=items_sold, low_stock=low_stock,
                               low_stock_threshold=low_stock_threshold,
                               current_time=datetime.now().strftime('%I:%M %p'))
    except Exception as e:
        return render_template('check_today.html', error=str(e), today=today)


@app.route('/restock', methods=['GET', 'POST'])
def restock():
    if request.method == 'POST':
        action = request.form.get('action')
        date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        conn = db.get_connection()
        c = conn.cursor()

        if action == 'restock_machine':
            # Track how much each product was restocked
            product_deductions = {}
            for key, value in request.form.items():
                if key.startswith('slot_') and value:
                    item_num = key.replace('slot_', '')
                    new_level = int(value)
                    # Get current level and product_id
                    c.execute('''SELECT i.capacity, i.product_id,
                                        COALESCE(inv.current_level, i.capacity) as current_level
                                 FROM items i
                                 LEFT JOIN inventory_snapshots inv ON i.item_num = inv.item_num
                                     AND inv.date = (SELECT MAX(date) FROM inventory_snapshots WHERE item_num = i.item_num)
                                 WHERE i.item_num = ?''', (item_num,))
                    row = c.fetchone()
                    if row and new_level > row['current_level']:
                        added = new_level - row['current_level']
                        pid = row['product_id']
                        if pid:
                            product_deductions[pid] = product_deductions.get(pid, 0) + added
                        c.execute('INSERT OR REPLACE INTO inventory_snapshots (date, item_num, current_level, capacity) VALUES (?, ?, ?, ?)',
                                  (date, item_num, new_level, row['capacity']))

            # Deduct from product warehouse stock
            for pid, qty in product_deductions.items():
                c.execute('UPDATE products SET home_qty = MAX(home_qty - ?, 0) WHERE id = ?', (qty, pid))

            db.set_setting('last_restock_date', date)

        conn.commit()
        conn.close()
        return redirect(url_for('restock'))

    products = get_products_with_slots()
    # Group by category for display
    categories = {}
    for p in products.values():
        cat = p['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(p)

    return render_template('restock.html', categories=categories, products=products,
                           today=datetime.now().strftime('%Y-%m-%d'))


@app.route('/sales')
def sales():
    end_date = request.args.get('end_date', datetime.now().strftime("%Y-%m-%d"))
    last_restock = db.get_setting('last_restock_date')
    default_start = last_restock or (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    start_date = request.args.get('start_date', default_start)
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('''SELECT date, SUM(quantity_sold) as items_sold, SUM(revenue) as revenue, SUM(profit) as profit
                 FROM daily_sales WHERE date BETWEEN ? AND ? GROUP BY date ORDER BY date DESC''',
              (start_date, end_date))
    daily_sales = [dict(row) for row in c.fetchall()]
    summary = db.get_sales_summary(start_date, end_date)
    c.execute('''SELECT i.item_name, SUM(ds.quantity_sold) as total_sold,
                        SUM(ds.revenue) as total_revenue, SUM(ds.profit) as total_profit
                 FROM daily_sales ds JOIN items i ON ds.item_num = i.item_num
                 WHERE ds.date BETWEEN ? AND ? GROUP BY ds.item_num ORDER BY total_sold DESC LIMIT 10''',
              (start_date, end_date))
    top_sellers = [dict(row) for row in c.fetchall()]
    conn.close()
    return render_template('sales.html', daily_sales=daily_sales, summary=summary,
                           top_sellers=top_sellers, start_date=start_date, end_date=end_date)


@app.route('/items')
def items():
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('''SELECT i.item_num, i.item_name, i.capacity, i.unit_cost, i.product_id,
                        p.name as product_name
                 FROM items i LEFT JOIN products p ON i.product_id = p.id
                 WHERE i.active = 1 ORDER BY i.item_num''')
    slots = [dict(row) for row in c.fetchall()]
    c.execute('SELECT id, name, unit_cost, category, home_qty FROM products WHERE active = 1 ORDER BY category, name')
    products = [dict(row) for row in c.fetchall()]
    conn.close()
    categories = {}
    for p in products:
        categories.setdefault(p['category'], []).append(p)
    return render_template('items.html', slots=slots, categories=categories)


@app.route('/items/add', methods=['POST'])
def add_item():
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('INSERT INTO items (item_num, item_name, capacity, unit_cost, product_id) VALUES (?, ?, ?, ?, ?)',
              (request.form['item_num'].zfill(4), request.form['item_name'],
               int(request.form['capacity']), float(request.form['unit_cost']),
               int(request.form['product_id']) if request.form.get('product_id') else None))
    conn.commit()
    conn.close()
    return redirect(url_for('items'))


@app.route('/items/edit/<item_num>', methods=['POST'])
def edit_item(item_num):
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('SELECT * FROM items WHERE item_num = ?', (item_num,))
    item = dict(c.fetchone())
    c.execute('SELECT id, name FROM products WHERE active = 1 ORDER BY name')
    products = [dict(row) for row in c.fetchall()]
    conn.close()
    return render_template('edit_item.html', item=item, products=products)


@app.route('/items/update/<item_num>', methods=['POST'])
def update_item(item_num):
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('UPDATE items SET item_name = ?, capacity = ?, unit_cost = ?, product_id = ? WHERE item_num = ?',
              (request.form['item_name'], int(request.form['capacity']),
               float(request.form['unit_cost']),
               int(request.form['product_id']) if request.form.get('product_id') else None,
               item_num))
    conn.commit()
    conn.close()
    return redirect(url_for('items'))


@app.route('/items/delete/<item_num>', methods=['POST'])
def delete_item(item_num):
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('UPDATE items SET active = 0 WHERE item_num = ?', (item_num,))
    conn.commit()
    conn.close()
    return redirect(url_for('items'))


@app.route('/products')
def products_page():
    return redirect(url_for('items'))


@app.route('/products/add', methods=['POST'])
def add_product():
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('INSERT INTO products (name, unit_cost, category) VALUES (?, ?, ?)',
              (request.form['name'], float(request.form['unit_cost']), request.form['category']))
    conn.commit()
    conn.close()
    return redirect(url_for('items'))


@app.route('/products/update/<int:pid>', methods=['POST'])
def update_product(pid):
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('UPDATE products SET name = ?, unit_cost = ?, category = ? WHERE id = ?',
              (request.form['name'], float(request.form['unit_cost']), request.form['category'], pid))
    conn.commit()
    conn.close()
    return redirect(url_for('items'))


@app.route('/products/delete/<int:pid>', methods=['POST'])
def delete_product(pid):
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('UPDATE products SET active = 0 WHERE id = ?', (pid,))
    conn.commit()
    conn.close()
    return redirect(url_for('items'))


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        db.set_setting('low_stock_threshold', request.form['low_stock_threshold'])
        if request.form.get('last_restock_date'):
            db.set_setting('last_restock_date', request.form['last_restock_date'])
        return redirect(url_for('settings'))

    conn = db.get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) as cnt FROM items WHERE active = 1')
    item_count = c.fetchone()['cnt']
    c.execute('SELECT COUNT(*) as cnt FROM products WHERE active = 1')
    product_count = c.fetchone()['cnt']
    conn.close()

    gmail_configured = all([os.getenv('GMAIL_USER'),
                            os.getenv('GMAIL_APP_PASSWORD') and os.getenv('GMAIL_APP_PASSWORD') != 'your_app_password_here'])
    return render_template('settings.html',
                           low_stock_threshold=db.get_setting('low_stock_threshold'),
                           last_restock_date=db.get_setting('last_restock_date'),
                           gmail_configured=gmail_configured,
                           item_count=item_count, product_count=product_count)


@app.route('/api/today')
def today_data():
    """Today's sales from DB (updated by cron at 4:15 PM)."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('SELECT SUM(revenue) as rev, SUM(profit) as profit, SUM(quantity_sold) as items FROM daily_sales WHERE date = ?', (today,))
    row = c.fetchone()
    conn.close()
    return jsonify({
        'revenue': row['rev'] or 0,
        'profit': row['profit'] or 0,
        'items': row['items'] or 0,
        'as_of': datetime.now().strftime('%I:%M %p')
    })


@app.route('/api/sales-chart')
def sales_chart_data():
    days = int(request.args.get('days', 30))
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = request.args.get('start_date') or (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('SELECT date, SUM(revenue) as revenue, SUM(profit) as profit FROM daily_sales WHERE date BETWEEN ? AND ? GROUP BY date ORDER BY date',
              (start_date, end_date))
    data = [dict(row) for row in c.fetchall()]
    conn.close()
    return jsonify(data)


@app.route('/api/export-csv')
def export_csv():
    start_date = request.args.get('start_date', '2020-01-01')
    end_date = request.args.get('end_date', datetime.now().strftime("%Y-%m-%d"))
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('''SELECT ds.date, i.item_num, i.item_name, ds.quantity_sold, ds.price, ds.revenue, ds.cost, ds.profit
                 FROM daily_sales ds JOIN items i ON ds.item_num = i.item_num
                 WHERE ds.date BETWEEN ? AND ? ORDER BY ds.date DESC, i.item_num''',
              (start_date, end_date))
    rows = c.fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Item #', 'Item Name', 'Qty Sold', 'Price', 'Revenue', 'Cost', 'Profit'])
    for row in rows:
        writer.writerow(list(row))
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename=vending_sales_{start_date}_to_{end_date}.csv'})


@app.route('/health')
def health():
    try:
        conn = db.get_connection()
        c = conn.cursor()
        c.execute('SELECT COUNT(*) as cnt FROM items')
        items = c.fetchone()['cnt']
        c.execute('SELECT MAX(date) as last_date FROM daily_sales')
        last = c.fetchone()['last_date']
        conn.close()
        return jsonify({'status': 'ok', 'items': items, 'last_data': last})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    import sys
    from dotenv import load_dotenv
    load_dotenv()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    print(f"\n💪 Muscle Fuel Dashboard v2.2 on http://localhost:{port}\n")
    app.run(host='0.0.0.0', port=port, debug=True)
