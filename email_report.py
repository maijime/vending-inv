#!/usr/bin/env python3
"""Email reporting system."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import os
from dotenv import load_dotenv
import database as db

load_dotenv()

def generate_html_report(date: str, sales_data: list, summary: dict) -> str:
    """Generate HTML email report."""
    low_stock_threshold = int(db.get_setting('low_stock_threshold') or 3)
    
    # Get stock from products
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT i.item_num, COALESCE(p.home_qty, 0) as stock_qty
        FROM items i
        LEFT JOIN products p ON i.product_id = p.id
        WHERE i.active = 1
    ''')
    stock = {row['item_num']: row['stock_qty'] for row in cursor.fetchall()}
    
    # Get last restock date and sales since then
    last_restock = db.get_setting('last_restock_date')
    sales_since_restock = None
    if last_restock:
        cursor.execute('''
            SELECT 
                SUM(quantity_sold) as total_items,
                SUM(revenue) as total_revenue,
                SUM(cost) as total_cost,
                SUM(profit) as total_profit
            FROM daily_sales
            WHERE date BETWEEN ? AND ?
        ''', (last_restock, date))
        sales_since_restock = dict(cursor.fetchone())
    
    conn.close()
    
    # Filter items with sales or low stock
    items_with_sales = [item for item in sales_data if item.get('sold', 0) > 0]
    low_stock_items = [item for item in sales_data if item.get('inventory', 0) < low_stock_threshold]
    
    # Top sellers
    top_sellers = sorted(items_with_sales, key=lambda x: x.get('sold', 0), reverse=True)[:3]
    
    html = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h2 {{ color: #2c3e50; }}
            .summary {{ background: #ecf0f1; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .restock-summary {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
            .metric-label {{ font-size: 12px; color: #7f8c8d; }}
            .metric-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
            table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
            th {{ background: #34495e; color: white; padding: 10px; text-align: left; }}
            td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
            .low-stock {{ color: #e74c3c; font-weight: bold; }}
            .good-stock {{ color: #27ae60; }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #7f8c8d; }}
        </style>
    </head>
    <body>
        <h2>📊 Daily Vending Report - {datetime.strptime(date, '%Y-%m-%d').strftime('%B %d, %Y')}</h2>
        
        <div class="summary">
            <div class="metric">
                <div class="metric-label">Total Sales</div>
                <div class="metric-value">${summary.get('total_revenue', 0):.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Profit</div>
                <div class="metric-value">${summary.get('total_profit', 0):.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Items Sold</div>
                <div class="metric-value">{summary.get('total_items', 0)}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Profit Margin</div>
                <div class="metric-value">{(summary.get('total_profit', 0) / summary.get('total_revenue', 1) * 100):.1f}%</div>
            </div>
        </div>
    """
    
    if sales_since_restock and last_restock:
        html += f"""
        <div class="restock-summary">
            <h3>📈 Sales Since Last Restock ({last_restock})</h3>
            <div class="metric">
                <div class="metric-label">Total Sales</div>
                <div class="metric-value">${sales_since_restock.get('total_revenue', 0):.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Total Profit</div>
                <div class="metric-value">${sales_since_restock.get('total_profit', 0):.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Items Sold</div>
                <div class="metric-value">{sales_since_restock.get('total_items', 0)}</div>
            </div>
        </div>
        """
    
    if top_sellers:
        html += """
        <h3>🏆 Top Sellers Today</h3>
        <table>
            <tr><th>Item</th><th>Sold</th><th>Revenue</th></tr>
        """
        for item in top_sellers:
            html += f"""
            <tr>
                <td>{item['item_name']}</td>
                <td>{item['sold']}</td>
                <td>${item['sales']:.2f}</td>
            </tr>
            """
        html += "</table>"
    
    if low_stock_items:
        html += f"""
        <h3>🔴 Low Stock Alerts (< {low_stock_threshold} items)</h3>
        <table>
            <tr><th>Item</th><th>Current</th><th>Capacity</th><th>Status</th></tr>
        """
        for item in low_stock_items:
            html += f"""
            <tr>
                <td>{item['item_name']}</td>
                <td class="low-stock">{item['inventory']}</td>
                <td>{item['capacity']}</td>
                <td>⚠️ Restock needed</td>
            </tr>
            """
        html += "</table>"
    
    html += """
        <h3>📦 Current Inventory</h3>
        <table>
            <tr><th>Item</th><th>Machine</th><th>Stock</th><th>Total</th></tr>
    """
    
    for item in sorted(sales_data, key=lambda x: x['item_num']):
        stock_class = 'low-stock' if item['inventory'] < low_stock_threshold else 'good-stock'
        wh_qty = stock.get(item['item_num'], 0)
        total_qty = item['inventory'] + wh_qty
        
        html += f"""
        <tr>
            <td>{item['item_name']}</td>
            <td class="{stock_class}">{item['inventory']}/{item['capacity']}</td>
            <td>{wh_qty}</td>
            <td><strong>{total_qty}</strong></td>
        </tr>
        """
    
    html += f"""
        </table>
        <div class="footer">
            Generated automatically by Vending Inventory System<br>
            Report Date: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}
        </div>
    </body>
    </html>
    """
    
    return html

def send_email_report(to_email: str, date: str, sales_data: list, summary: dict):
    """Send email report via Gmail SMTP."""
    from_email = os.getenv('GMAIL_USER')
    app_password = os.getenv('GMAIL_APP_PASSWORD')
    
    if not from_email or not app_password:
        print("⚠️  Gmail credentials not configured. Set GMAIL_USER and GMAIL_APP_PASSWORD in .env")
        return False
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Vending Report - {datetime.strptime(date, '%Y-%m-%d').strftime('%b %d, %Y')} - ${summary.get('total_revenue', 0):.2f}"
    msg['From'] = from_email
    msg['To'] = to_email
    
    html_content = generate_html_report(date, sales_data, summary)
    msg.attach(MIMEText(html_content, 'html'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(from_email, app_password)
            server.send_message(msg)
        print(f"✓ Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"✗ Failed to send email: {e}")
        return False

if __name__ == '__main__':
    # Test email with today's data
    date = datetime.now().strftime("%Y-%m-%d")
    inventory = db.get_latest_inventory()
    summary = db.get_sales_summary(date, date)
    
    # Mock sales data for testing
    sales_data = []
    for item in inventory:
        sales_data.append({
            'item_num': item['item_num'],
            'item_name': item['item_name'],
            'capacity': item['capacity'],
            'inventory': item['current_level'],
            'sold': 0,
            'sales': 0,
            'profit': 0
        })
    
    send_email_report(os.getenv('GMAIL_USER'), date, sales_data, summary)
