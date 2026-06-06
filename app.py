#!/usr/bin/env python3
"""Vending machine dashboard — v3 (simplified, mobile-first)."""
from flask import (Flask, render_template, request, redirect, url_for,
                   jsonify, Response, session, flash)
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from datetime import datetime, timedelta
from functools import wraps
import csv, io, os, random, smtplib
from email.mime.text import MIMEText
import bcrypt
import database as db
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# App + auth setup
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24).hex())

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

db.init_database()
db.migrate_from_v2()
db.seed_slots()


class User(UserMixin):
    def __init__(self, username):
        self.id = username


@login_manager.user_loader
def load_user(username):
    stored = db.get_setting('admin_user')
    if stored and username == stored:
        return User(username)
    return None


def _init_admin():
    if not db.get_setting('admin_user'):
        hashed = bcrypt.hashpw(b'admin', bcrypt.gensalt()).decode()
        db.set_setting('admin_user', 'admin')
        db.set_setting('admin_password', hashed)

_init_admin()


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        stored_user = db.get_setting('admin_user')
        stored_hash = db.get_setting('admin_password')
        if stored_user and username == stored_user and stored_hash:
            if bcrypt.checkpw(password.encode(), stored_hash.encode()):
                login_user(User(username), remember=True)
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
            code = str(random.randint(100000, 999999))
            session['reset_code'] = code
            session['reset_expires'] = (datetime.now() + timedelta(minutes=10)).isoformat()
            gmail_user = os.getenv('GMAIL_USER')
            gmail_pass = os.getenv('GMAIL_APP_PASSWORD')
            if gmail_user and gmail_pass:
                try:
                    msg = MIMEText(f'Your password reset code is: {code}\n\nExpires in 10 minutes.')
                    msg['Subject'] = 'Vending — Password Reset'
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


# ---------------------------------------------------------------------------
# Machine layout helper
# ---------------------------------------------------------------------------

MACHINE_LAYOUT = {
    'snacks': [
        {'label': 'Row 1 — Snacks',        'slots': ['0111','0113','0115','0117']},
        {'label': 'Row 2 — Snacks',        'slots': ['0121','0123','0125','0127']},
        {'label': 'Row 3 — Small Snacks', 'slots': ['0130','0131','0132','0133',
                                                     '0134','0135','0136','0137']},
    ],
    'drinks': ['0140','0141','0142','0143','0144','0145','0146'],
}


def _build_machine(slots_by_num):
    """Build the structured machine layout from a flat slot dict."""
    machine = {'snacks': [], 'drinks': []}
    for row in MACHINE_LAYOUT['snacks']:
        machine['snacks'].append({
            'label': row['label'],
            'slots': [slots_by_num.get(n) for n in row['slots']
                      if slots_by_num.get(n)],
        })
    machine['drinks'] = [slots_by_num.get(n) for n in MACHINE_LAYOUT['drinks']
                         if slots_by_num.get(n)]
    return machine


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------

@app.route('/')
@login_required
def index():
    slots = db.get_slots_with_levels()
    slots_by_num = {s['item_num']: s for s in slots}
    machine = _build_machine(slots_by_num)

    low_threshold = int(db.get_setting('low_stock_threshold') or 3)
    low_count = sum(1 for s in slots if s['current_level'] < low_threshold)

    today = datetime.now().strftime('%Y-%m-%d')
    last_restock = db.get_setting('last_restock_date')
    since_start = last_restock or (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    summary = db.get_sales_summary(since_start, today)

    return render_template('index.html',
                           machine=machine,
                           low_count=low_count,
                           low_threshold=low_threshold,
                           summary=summary,
                           last_restock=last_restock)


# ---------------------------------------------------------------------------
# Slot detail (API — returns JSON for modal)
# ---------------------------------------------------------------------------

@app.route('/api/slot/<item_num>')
@login_required
def slot_detail(item_num):
    slots = db.get_slots_with_levels()
    slot = next((s for s in slots if s['item_num'] == item_num), None)
    if not slot:
        return jsonify({'error': 'Not found'}), 404

    last_restock = db.get_setting('last_restock_date') or '2000-01-01'
    today = datetime.now().strftime('%Y-%m-%d')
    sales = db.get_sales_summary(last_restock, today)

    # Per-slot sales since restock
    from database import get_connection
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT COALESCE(SUM(quantity_sold),0) as sold,
                        COALESCE(SUM(revenue),0)       as revenue,
                        COALESCE(SUM(profit),0)        as profit
                 FROM daily_sales WHERE item_num=? AND date > ?''',
              (item_num, last_restock))
    slot_sales = dict(c.fetchone())

    # Last 7 days
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    c.execute('''SELECT COALESCE(SUM(quantity_sold),0) as sold
                 FROM daily_sales WHERE item_num=? AND date >= ?''',
              (item_num, week_ago))
    week_sold = c.fetchone()['sold']
    conn.close()

    return jsonify({
        'item_num':      slot['item_num'],
        'name':          slot['name'],
        'capacity':      slot['capacity'],
        'current_level': slot['current_level'],
        'home_stock':    slot['home_stock'],
        'since_restock': slot_sales,
        'week_sold':     week_sold,
        'last_restock':  last_restock,
    })


@app.route('/api/slot/<item_num>/update', methods=['POST'])
@login_required
def slot_update(item_num):
    """Update slot name, capacity, or home_stock from the modal."""
    data = request.get_json()
    slot = db.get_slot(item_num)
    if not slot:
        return jsonify({'error': 'Not found'}), 404

    name       = data.get('name', slot['name'])
    capacity   = int(data.get('capacity', slot['capacity']))
    home_stock = int(data.get('home_stock', slot['home_stock']))
    db.update_slot(item_num, name, capacity, home_stock)
    return jsonify({'ok': True})


# ---------------------------------------------------------------------------
# Restock
# ---------------------------------------------------------------------------

@app.route('/restock', methods=['GET', 'POST'])
@login_required
def restock():
    if request.method == 'POST':
        date  = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        notes = request.form.get('notes', '')
        filled = {}
        for key, val in request.form.items():
            if key.startswith('slot_') and val.strip():
                item_num = key[5:]
                try:
                    filled[item_num] = int(val)
                except ValueError:
                    pass
        if filled:
            db.save_restock(date, filled, notes)
            flash('Restock saved!', 'success')
        else:
            flash('No quantities entered.', 'warning')
        return redirect(url_for('restock'))

    slots = db.get_slots_with_levels()
    slots_by_num = {s['item_num']: s for s in slots}
    machine = _build_machine(slots_by_num)
    last_restock = db.get_last_restock()
    today = datetime.now().strftime('%Y-%m-%d')

    return render_template('restock.html', machine=machine,
                           last_restock=last_restock, today=today)


# ---------------------------------------------------------------------------
# Sales
# ---------------------------------------------------------------------------

@app.route('/sales')
@login_required
def sales():
    today = datetime.now().strftime('%Y-%m-%d')
    last_restock = db.get_setting('last_restock_date')
    default_start = last_restock or (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    start_date = request.args.get('start_date', default_start)
    end_date   = request.args.get('end_date', today)

    summary     = db.get_sales_summary(start_date, end_date)
    by_item     = db.get_sales_by_item(start_date, end_date)
    daily_sales = db.get_daily_sales(start_date, end_date)

    return render_template('sales.html',
                           summary=summary, by_item=by_item,
                           daily_sales=daily_sales,
                           start_date=start_date, end_date=end_date)


@app.route('/api/export-csv')
@login_required
def export_csv():
    today = datetime.now().strftime('%Y-%m-%d')
    start_date = request.args.get('start_date', '2020-01-01')
    end_date   = request.args.get('end_date', today)
    rows = db.get_sales_export(start_date, end_date)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date','Item #','Item Name','Qty Sold','Price','Revenue','Cost','Profit'])
    for row in rows:
        writer.writerow([row['date'], row['item_num'], row['item_name'],
                         row['quantity_sold'], row['price'],
                         row['revenue'], row['cost'], row['profit']])
    filename = f'vending_sales_{start_date}_to_{end_date}.csv'
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename={filename}'})


# ---------------------------------------------------------------------------
# Products (manage unique product names + home stock)
# ---------------------------------------------------------------------------

@app.route('/products')
@login_required
def products():
    return render_template('products.html', products=db.get_products())


@app.route('/products/update', methods=['POST'])
@login_required
def update_product():
    original_name = request.form.get('original_name')
    new_name      = request.form.get('name', '').strip()
    home_stock    = int(request.form.get('home_stock', 0))
    if original_name and new_name:
        db.update_product(original_name, new_name, home_stock)
        flash(f'"{new_name}" updated.', 'success')
    return redirect(url_for('products'))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'threshold':
            db.set_setting('low_stock_threshold', request.form['low_stock_threshold'])
            flash('Threshold updated.', 'success')
        elif action == 'password':
            new_user = request.form.get('username', '').strip()
            new_pass = request.form.get('password', '').strip()
            if new_user and new_pass:
                hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()
                db.set_setting('admin_user', new_user)
                db.set_setting('admin_password', hashed)
                flash('Credentials updated.', 'success')
            else:
                flash('Username and password required.', 'error')
        return redirect(url_for('settings'))

    return render_template('settings.html',
                           low_stock_threshold=db.get_setting('low_stock_threshold'),
                           last_restock_date=db.get_setting('last_restock_date'),
                           admin_user=db.get_setting('admin_user'))


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.route('/health')
def health():
    try:
        from database import get_connection
        conn = get_connection()
        c = conn.cursor()
        c.execute('SELECT COUNT(*) as cnt FROM slots')
        slots = c.fetchone()['cnt']
        c.execute('SELECT MAX(date) as last_date FROM daily_sales')
        last = c.fetchone()['last_date']
        conn.close()
        return jsonify({'status': 'ok', 'slots': slots, 'last_data': last})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    print(f"\nVending Dashboard v3 — http://localhost:{port}\n")
    app.run(host='0.0.0.0', port=port, debug=True)
