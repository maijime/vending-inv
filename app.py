#!/usr/bin/env python3
"""Flask web dashboard for vending machine management. v2.3"""
from flask import Flask, render_template, request, redirect, url_for, jsonify, Response, session, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
from functools import wraps
import csv, io, os, random, smtplib
from email.mime.text import MIMEText
import bcrypt
import database as db
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24).hex())

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Auth ---

class User(UserMixin):
    def __init__(self, username, role='admin'):
        self.id = username
        self.role = role

@login_manager.user_loader
def load_user(username):
    if username == 'demo':
        return User('demo', 'demo')
    stored = db.get_setting('admin_user')
    if stored and username == stored:
        return User(username, 'admin')
    return None

def admin_required(f):
    """Block demo users from write operations."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role == 'demo':
            flash('Demo mode — changes are disabled.', 'warning')
            return redirect(request.referrer or url_for('index'))
        return f(*args, **kwargs)
    return decorated

def _init_admin():
    """Set default admin/admin if no admin exists."""
    if not db.get_setting('admin_user'):
        hashed = bcrypt.hashpw(b'admin', bcrypt.gensalt()).decode()
        db.set_setting('admin_user', 'admin')
        db.set_setting('admin_password', hashed)

_init_admin()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        # Demo login
        if username == 'demo' and password == 'demo':
            login_user(User('demo', 'demo'))
            return redirect(url_for('index'))
        # Admin login
        stored_user = db.get_setting('admin_user')
        stored_hash = db.get_setting('admin_password')
        if stored_user and username == stored_user and stored_hash:
            if bcrypt.checkpw(password.encode(), stored_hash.encode()):
                login_user(User(username, 'admin'), remember=True)
                return redirect(request.args.get('next') or url_for('index'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        step = request.form.get('step')
        if step == 'send_code':
            # Generate and email a 6-digit code
            code = str(random.randint(100000, 999999))
            session['reset_code'] = code
            session['reset_expires'] = (datetime.now() + timedelta(minutes=10)).isoformat()
            gmail_user = os.getenv('GMAIL_USER')
            gmail_pass = os.getenv('GMAIL_APP_PASSWORD')
            if gmail_user and gmail_pass:
                try:
                    msg = MIMEText(f'Your Muscle Fuel password reset code is: {code}\n\nExpires in 10 minutes.')
                    msg['Subject'] = 'Muscle Fuel — Password Reset Code'
                    msg['From'] = gmail_user
                    msg['To'] = gmail_user
                    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                        server.login(gmail_user, gmail_pass)
                        server.send_message(msg)
                    flash('Code sent to your email.', 'success')
                except Exception:
                    flash('Failed to send email. Check SMTP settings.', 'error')
            else:
                flash('Email not configured.', 'error')
            return render_template('reset_password.html', step='verify')

        elif step == 'verify':
            code = request.form.get('code', '').strip()
            expires = session.get('reset_expires', '')
            if expires and datetime.now() < datetime.fromisoformat(expires) and code == session.get('reset_code'):
                session['reset_verified'] = True
                return render_template('reset_password.html', step='new_password')
            flash('Invalid or expired code.', 'error')
            return render_template('reset_password.html', step='verify')

        elif step == 'new_password':
            if not session.get('reset_verified'):
                return redirect(url_for('reset_password'))
            new_user = request.form.get('username', '').strip()
            new_pass = request.form.get('password', '').strip()
            if new_user and new_pass:
                hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()
                db.set_setting('admin_user', new_user)
                db.set_setting('admin_password', hashed)
                session.pop('reset_code', None)
                session.pop('reset_verified', None)
                flash('Password updated. Please log in.', 'success')
                return redirect(url_for('login'))
            flash('Username and password required.', 'error')
            return render_template('reset_password.html', step='new_password')

    return render_template('reset_password.html', step='send_code')


def get_products_with_slots():
    """Get products grouped with their slot assignments.
    Current level = restock level - total sold since last restock.
    Falls back to capacity if no restock snapshot exists."""
    conn = db.get_connection()
    c = conn.cursor()
    last_restock = db.get_setting('last_restock_date') or '2000-01-01'
    c.execute('''
        SELECT p.id, p.name, p.unit_cost, p.category, p.home_qty,
               i.item_num, i.capacity,
               COALESCE(snap.current_level, i.capacity) as restock_level,
               COALESCE(
                   (SELECT SUM(ds.quantity_sold) FROM daily_sales ds
                    WHERE ds.item_num = i.item_num AND ds.date > ?), 0
               ) as sold_since
        FROM products p
        JOIN items i ON i.product_id = p.id AND i.active = 1
        LEFT JOIN inventory_snapshots snap ON snap.item_num = i.item_num AND snap.date = ?
        WHERE p.active = 1
        ORDER BY p.category, p.name, i.item_num
    ''', (last_restock, last_restock))
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
        level = max(0, row['restock_level'] - row['sold_since'])
        cap = row['capacity']
        products[pid]['slots'].append({
            'item_num': row['item_num'], 'capacity': cap,
            'current_level': min(level, cap),
            'need': max(0, cap - level)
        })
    return products


def _build_machine_stock():
    """Flat slot list sorted by item_num with revenue since restock."""
    products = get_products_with_slots()
    last_restock = db.get_setting('last_restock_date') or '2000-01-01'
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('SELECT item_num, SUM(revenue) as rev FROM daily_sales WHERE date >= ? GROUP BY item_num', (last_restock,))
    rev_map = {row['item_num']: row['rev'] for row in c.fetchall()}
    conn.close()
    slots = []
    for p in products.values():
        for s in p['slots']:
            s['product_name'] = p['name']
            s['revenue'] = rev_map.get(s['item_num'], 0)
            slots.append(s)
    slots.sort(key=lambda s: s['item_num'])
    return slots


@app.route('/')
@login_required
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
                           low_stock_threshold=low_stock_threshold,
                           machine_slots=_build_machine_stock(),
                           week_comparison=week_comparison, best_day=best_day, greeting=greeting)


@app.route('/inventory')
@login_required
def inventory():
    products = get_products_with_slots()

    # Group by category
    categories = {}
    for p in products.values():
        categories.setdefault(p['category'], []).append(p)

    # Get slots for machine slots section
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('''SELECT i.item_num, i.item_name, i.capacity, i.unit_cost, i.product_id,
                        p.name as product_name
                 FROM items i LEFT JOIN products p ON i.product_id = p.id
                 WHERE i.active = 1 ORDER BY i.item_num''')
    slots = [dict(row) for row in c.fetchall()]
    conn.close()

    return render_template('inventory.html', categories=categories,
                           slots=slots, slot_count=len(slots))


@app.route('/inventory/update-stock', methods=['POST'])
@admin_required
def update_stock():
    """Update stock for a product."""
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
@admin_required
def add_stock():
    """Add to stock (shopping run)."""
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
@login_required
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
@login_required
def restock():
    if request.method == 'POST':
        if current_user.role == 'demo':
            flash('Demo mode — changes are disabled.', 'warning')
            return redirect(url_for('restock'))
    if request.method == 'POST':
        action = request.form.get('action')
        date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        conn = db.get_connection()
        c = conn.cursor()

        if action == 'restock_machine':
            last_restock = db.get_setting('last_restock_date') or '2000-01-01'
            product_deductions = {}
            for key, value in request.form.items():
                if key.startswith('slot_') and value:
                    item_num = key.replace('slot_', '')
                    new_level = int(value)
                    c.execute('''SELECT i.capacity, i.product_id,
                                        COALESCE(snap.current_level, i.capacity) as restock_level,
                                        COALESCE(
                                            (SELECT SUM(ds.quantity_sold) FROM daily_sales ds
                                             WHERE ds.item_num = i.item_num AND ds.date > ?), 0
                                        ) as sold_since
                                 FROM items i
                                 LEFT JOIN inventory_snapshots snap ON snap.item_num = i.item_num AND snap.date = ?
                                 WHERE i.item_num = ?''', (last_restock, last_restock, item_num))
                    row = c.fetchone()
                    if row:
                        current = max(0, row['restock_level'] - row['sold_since'])
                        if new_level > current:
                            added = new_level - current
                            pid = row['product_id']
                            if pid:
                                product_deductions[pid] = product_deductions.get(pid, 0) + added
                        c.execute('INSERT OR REPLACE INTO inventory_snapshots (date, item_num, current_level, capacity) VALUES (?, ?, ?, ?)',
                                  (date, item_num, new_level, row['capacity']))

            # Deduct from product stock
            for pid, qty in product_deductions.items():
                c.execute('UPDATE products SET home_qty = MAX(home_qty - ?, 0) WHERE id = ?', (qty, pid))

            # Set restock date on same connection
            c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('last_restock_date', date))

        conn.commit()
        conn.close()
        return redirect(url_for('restock'))

    products = get_products_with_slots()
    # Flat list of slots sorted by item_num for physical machine order
    slots = []
    product_stock = {p['id']: p['home_qty'] for p in products.values()}
    for p in products.values():
        for s in p['slots']:
            s['product_name'] = p['name']
            s['home_qty'] = p['home_qty']
            slots.append(s)
    slots.sort(key=lambda s: s['item_num'])

    return render_template('restock.html', slots=slots,
                           today=datetime.now().strftime('%Y-%m-%d'))


@app.route('/sales')
@login_required
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
    c.execute('''SELECT COALESCE(p.name, i.item_name) as item_name,
                        SUM(ds.quantity_sold) as total_sold,
                        SUM(ds.revenue) as total_revenue, SUM(ds.profit) as total_profit
                 FROM daily_sales ds
                 JOIN items i ON ds.item_num = i.item_num
                 LEFT JOIN products p ON COALESCE(ds.product_id, i.product_id) = p.id
                 WHERE ds.date BETWEEN ? AND ?
                 GROUP BY COALESCE(p.name, i.item_name) ORDER BY total_sold DESC LIMIT 10''',
              (start_date, end_date))
    top_sellers = [dict(row) for row in c.fetchall()]
    conn.close()
    return render_template('sales.html', daily_sales=daily_sales, summary=summary,
                           top_sellers=top_sellers, start_date=start_date, end_date=end_date)


@app.route('/items')
def items():
    return redirect(url_for('inventory'))


@app.route('/items/add', methods=['POST'])
@admin_required
def add_item():
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('INSERT INTO items (item_num, item_name, capacity, unit_cost, product_id) VALUES (?, ?, ?, ?, ?)',
              (request.form['item_num'].zfill(4), request.form['item_name'],
               int(request.form['capacity']), float(request.form['unit_cost']),
               int(request.form['product_id']) if request.form.get('product_id') else None))
    conn.commit()
    conn.close()
    return redirect(url_for('inventory'))


@app.route('/items/edit/<item_num>', methods=['POST'])
@admin_required
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
@admin_required
def update_item(item_num):
    conn = db.get_connection()
    c = conn.cursor()
    pid = int(request.form['product_id']) if request.form.get('product_id') else None
    capacity = int(request.form['capacity'])
    # Sync item_name and unit_cost from product
    if pid:
        c.execute('SELECT name, unit_cost FROM products WHERE id = ?', (pid,))
        p = c.fetchone()
        c.execute('UPDATE items SET item_name = ?, capacity = ?, unit_cost = ?, product_id = ? WHERE item_num = ?',
                  (p['name'], capacity, p['unit_cost'], pid, item_num))
    else:
        c.execute('UPDATE items SET capacity = ?, product_id = NULL WHERE item_num = ?',
                  (capacity, item_num))
    conn.commit()
    conn.close()
    return redirect(url_for('inventory'))


@app.route('/items/delete/<item_num>', methods=['POST'])
@admin_required
def delete_item(item_num):
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('UPDATE items SET active = 0 WHERE item_num = ?', (item_num,))
    conn.commit()
    conn.close()
    return redirect(url_for('inventory'))


@app.route('/products')
def products_page():
    return redirect(url_for('inventory'))


@app.route('/products/add', methods=['POST'])
@admin_required
def add_product():
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('INSERT INTO products (name, unit_cost, category) VALUES (?, ?, ?)',
              (request.form['name'], float(request.form['unit_cost']), request.form['category']))
    conn.commit()
    conn.close()
    return redirect(url_for('inventory'))


@app.route('/products/update/<int:pid>', methods=['POST'])
@admin_required
def update_product(pid):
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('UPDATE products SET name = ?, unit_cost = ?, category = ? WHERE id = ?',
              (request.form['name'], float(request.form['unit_cost']), request.form['category'], pid))
    conn.commit()
    conn.close()
    return redirect(url_for('inventory'))


@app.route('/products/delete/<int:pid>', methods=['POST'])
@admin_required
def delete_product(pid):
    conn = db.get_connection()
    c = conn.cursor()
    c.execute('UPDATE products SET active = 0 WHERE id = ?', (pid,))
    conn.commit()
    conn.close()
    return redirect(url_for('inventory'))


@app.route('/settings', methods=['GET', 'POST'])
@admin_required
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
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    print(f"\n💪 Muscle Fuel Dashboard v2.3 on http://localhost:{port}\n")
    app.run(host='0.0.0.0', port=port, debug=True)
