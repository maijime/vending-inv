#!/usr/bin/env python3
"""Flask web dashboard for vending machine management. v2.1"""
from flask import Flask, render_template, request, redirect, url_for, jsonify, Response
from datetime import datetime, timedelta
import csv
import io
import os
import database as db

app = Flask(__name__)


@app.route('/')
def index():
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_summary = db.get_sales_summary(yesterday, yesterday)

    inventory = db.get_latest_inventory()
    low_stock_threshold = int(db.get_setting('low_stock_threshold') or 3)
    low_stock_count = sum(1 for item in inventory if item['current_level'] < low_stock_threshold)

    last_restock = db.get_setting('last_restock_date')
    restock_summary = None
    if last_restock:
        restock_summary = db.get_sales_summary(last_restock, today)
        restock_summary['start_date'] = last_restock

    # Week-over-week comparison
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

    return render_template('index.html',
                           today=today, yesterday=yesterday,
                           yesterday_summary=yesterday_summary,
                           restock_summary=restock_summary,
                           low_stock_count=low_stock_count,
                           inventory_count=len(inventory),
                           week_comparison=week_comparison)


@app.route('/inventory')
def inventory():
    inventory_data = db.get_latest_inventory()
    low_stock_threshold = int(db.get_setting('low_stock_threshold') or 3)
    last_restock = db.get_setting('last_restock_date')

    sales_since_restock = None
    if last_restock:
        today = datetime.now().strftime('%Y-%m-%d')
        sales_since_restock = db.get_sales_summary(last_restock, today)
        sales_since_restock['start_date'] = last_restock

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT i.item_num, i.item_name, COALESCE(h.quantity, 0) as quantity
        FROM items i LEFT JOIN home_inventory h ON i.item_num = h.item_num
        WHERE i.active = 1 ORDER BY i.item_num
    ''')
    home_inventory = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return render_template('inventory.html',
                           machine_inventory=inventory_data,
                           home_inventory=home_inventory,
                           low_stock_threshold=low_stock_threshold,
                           sales_since_restock=sales_since_restock)


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
        cursor = conn.cursor()

        if action == 'restock_machine':
            for key, value in request.form.items():
                if key.startswith('machine_') and value:
                    item_num = key.replace('machine_', '')
                    quantity = int(value)
                    if quantity > 0:
                        cursor.execute('SELECT capacity FROM items WHERE item_num = ?', (item_num,))
                        capacity = cursor.fetchone()['capacity']
                        cursor.execute('INSERT OR REPLACE INTO inventory_snapshots (date, item_num, current_level, capacity) VALUES (?, ?, ?, ?)',
                                       (date, item_num, quantity, capacity))
                        cursor.execute('''INSERT OR REPLACE INTO home_inventory (item_num, quantity, last_updated)
                                          VALUES (?, COALESCE((SELECT quantity FROM home_inventory WHERE item_num = ?), 0) - ?, CURRENT_TIMESTAMP)''',
                                       (item_num, item_num, quantity))
            # Auto-update last restock date
            db.set_setting('last_restock_date', date)

        elif action == 'add_home_inventory':
            for key, value in request.form.items():
                if key.startswith('home_') and value:
                    item_num = key.replace('home_', '')
                    quantity = int(value)
                    if quantity > 0:
                        cursor.execute('''INSERT OR REPLACE INTO home_inventory (item_num, quantity, last_updated)
                                          VALUES (?, COALESCE((SELECT quantity FROM home_inventory WHERE item_num = ?), 0) + ?, CURRENT_TIMESTAMP)''',
                                       (item_num, item_num, quantity))
        conn.commit()
        conn.close()
        return redirect(url_for('restock'))

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT i.item_num, i.item_name, i.capacity,
               COALESCE(inv.current_level, i.capacity) as current_level
        FROM items i LEFT JOIN inventory_snapshots inv ON i.item_num = inv.item_num
        WHERE i.active = 1 AND (inv.date = (SELECT MAX(date) FROM inventory_snapshots WHERE item_num = i.item_num) OR inv.date IS NULL)
        ORDER BY i.item_num
    ''')
    machine_inventory = [dict(row) for row in cursor.fetchall()]
    cursor.execute('''
        SELECT i.item_num, i.item_name, COALESCE(h.quantity, 0) as quantity
        FROM items i LEFT JOIN home_inventory h ON i.item_num = h.item_num
        WHERE i.active = 1 ORDER BY i.item_num
    ''')
    home_inventory = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return render_template('restock.html', machine_inventory=machine_inventory,
                           home_inventory=home_inventory, today=datetime.now().strftime('%Y-%m-%d'))


@app.route('/sales')
def sales():
    end_date = request.args.get('end_date', datetime.now().strftime("%Y-%m-%d"))
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT date, SUM(quantity_sold) as items_sold, SUM(revenue) as revenue, SUM(profit) as profit
        FROM daily_sales WHERE date BETWEEN ? AND ? GROUP BY date ORDER BY date DESC
    ''', (start_date, end_date))
    daily_sales = [dict(row) for row in cursor.fetchall()]
    summary = db.get_sales_summary(start_date, end_date)
    cursor.execute('''
        SELECT i.item_name, SUM(ds.quantity_sold) as total_sold, SUM(ds.revenue) as total_revenue, SUM(ds.profit) as total_profit
        FROM daily_sales ds JOIN items i ON ds.item_num = i.item_num
        WHERE ds.date BETWEEN ? AND ? GROUP BY ds.item_num ORDER BY total_sold DESC LIMIT 10
    ''', (start_date, end_date))
    top_sellers = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return render_template('sales.html', daily_sales=daily_sales, summary=summary,
                           top_sellers=top_sellers, start_date=start_date, end_date=end_date)


@app.route('/items')
def items():
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM items WHERE active = 1 ORDER BY item_num')
    items_list = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return render_template('items.html', items=items_list)


@app.route('/items/add', methods=['POST'])
def add_item():
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO items (item_num, item_name, capacity, unit_cost) VALUES (?, ?, ?, ?)',
                   (request.form['item_num'].zfill(4), request.form['item_name'],
                    int(request.form['capacity']), float(request.form['unit_cost'])))
    conn.commit()
    conn.close()
    return redirect(url_for('items'))


@app.route('/items/edit/<item_num>', methods=['POST'])
def edit_item(item_num):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM items WHERE item_num = ?', (item_num,))
    item = dict(cursor.fetchone())
    conn.close()
    return render_template('edit_item.html', item=item)


@app.route('/items/update/<item_num>', methods=['POST'])
def update_item(item_num):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE items SET item_name = ?, capacity = ?, unit_cost = ? WHERE item_num = ?',
                   (request.form['item_name'], int(request.form['capacity']),
                    float(request.form['unit_cost']), item_num))
    conn.commit()
    conn.close()
    return redirect(url_for('items'))


@app.route('/items/delete/<item_num>', methods=['POST'])
def delete_item(item_num):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE items SET active = 0 WHERE item_num = ?', (item_num,))
    conn.commit()
    conn.close()
    return redirect(url_for('items'))


@app.route('/home-inventory/update', methods=['POST'])
def update_home_inventory():
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO home_inventory (item_num, quantity, last_updated) VALUES (?, ?, CURRENT_TIMESTAMP)',
                   (request.form['item_num'], int(request.form['quantity'])))
    conn.commit()
    conn.close()
    return redirect(url_for('inventory'))


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        db.set_setting('low_stock_threshold', request.form['low_stock_threshold'])
        if request.form.get('last_restock_date'):
            db.set_setting('last_restock_date', request.form['last_restock_date'])
        return redirect(url_for('settings'))

    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as cnt FROM items WHERE active = 1')
    item_count = cursor.fetchone()['cnt']
    conn.close()

    gmail_configured = all([os.getenv('GMAIL_USER'),
                            os.getenv('GMAIL_APP_PASSWORD') and os.getenv('GMAIL_APP_PASSWORD') != 'your_app_password_here'])
    return render_template('settings.html',
                           low_stock_threshold=db.get_setting('low_stock_threshold'),
                           last_restock_date=db.get_setting('last_restock_date'),
                           gmail_configured=gmail_configured,
                           item_count=item_count)


@app.route('/api/sales-chart')
def sales_chart_data():
    days = int(request.args.get('days', 30))
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT date, SUM(revenue) as revenue, SUM(profit) as profit FROM daily_sales WHERE date BETWEEN ? AND ? GROUP BY date ORDER BY date',
                   (start_date, end_date))
    data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(data)


@app.route('/api/export-csv')
def export_csv():
    start_date = request.args.get('start_date', '2020-01-01')
    end_date = request.args.get('end_date', datetime.now().strftime("%Y-%m-%d"))
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ds.date, i.item_num, i.item_name, ds.quantity_sold, ds.price, ds.revenue, ds.cost, ds.profit
        FROM daily_sales ds JOIN items i ON ds.item_num = i.item_num
        WHERE ds.date BETWEEN ? AND ? ORDER BY ds.date DESC, i.item_num
    ''', (start_date, end_date))
    rows = cursor.fetchall()
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
    """Health check endpoint for monitoring."""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as cnt FROM items')
        items = cursor.fetchone()['cnt']
        cursor.execute('SELECT MAX(date) as last_date FROM daily_sales')
        last = cursor.fetchone()['last_date']
        conn.close()
        return jsonify({'status': 'ok', 'items': items, 'last_data': last})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    import sys
    from dotenv import load_dotenv
    load_dotenv()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    print(f"\n🏪 Vending Dashboard v2.1 on http://localhost:{port}\n")
    app.run(host='0.0.0.0', port=port, debug=True)
