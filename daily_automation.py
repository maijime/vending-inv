#!/usr/bin/env python3
"""Main daily automation script - runs at 4:15pm daily."""
from datetime import datetime
import database as db
import os
from dotenv import load_dotenv

load_dotenv()
from collect_data import collect_daily_data
from email_report import send_email_report

def run_daily_automation():
    """Run daily data collection and reporting."""
    date = datetime.now().strftime("%Y-%m-%d")
    
    print(f"\n{'='*50}")
    print(f"Daily Automation - {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print(f"{'='*50}\n")
    
    # Collect data
    sales_data, has_sales = collect_daily_data(date)
    
    if not sales_data:
        print("✗ Failed to collect data. Exiting.")
        return
    
    # Get summary
    summary = db.get_sales_summary(date, date)
    
    # Check for low stock
    low_stock_threshold = int(db.get_setting('low_stock_threshold') or 3)
    low_stock_items = [item for item in sales_data if item['inventory'] < low_stock_threshold]
    
    if low_stock_items:
        print(f"⚠️  {len(low_stock_items)} items low on stock")
    
    # Send email if there were sales
    if has_sales:
        send_email_report(os.getenv('GMAIL_USER'), date, sales_data, summary)
    else:
        print("ℹ️  No sales today. Skipping email report.")
    
    print(f"\n{'='*50}")
    print("Daily automation complete!")
    print(f"{'='*50}\n")

if __name__ == '__main__':
    run_daily_automation()
