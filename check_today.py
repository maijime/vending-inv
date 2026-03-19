#!/usr/bin/env python3
"""Check today's sales in real-time without saving to database."""
from datetime import datetime
from collect_data import get_vending_data
import database as db

def check_today_live():
    """Get today's sales data without saving."""
    today = datetime.now().strftime("%Y-%m-%d")
    
    print(f"\n{'='*60}")
    print(f"Live Sales Check - {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print(f"{'='*60}\n")
    print("Fetching live data from portal...")
    
    try:
        sales_data = get_vending_data(today)
        
        if not sales_data:
            print("✗ No data available")
            return
        
        # Calculate totals
        total_sales = sum(item['sales'] for item in sales_data)
        total_profit = sum(item['profit'] for item in sales_data)
        total_items = sum(item['sold'] for item in sales_data)
        
        print(f"\n{'='*60}")
        print(f"TODAY'S SALES (Live - Not Saved)")
        print(f"{'='*60}\n")
        print(f"Total Sales:    ${total_sales:.2f}")
        print(f"Total Profit:   ${total_profit:.2f}")
        print(f"Items Sold:     {total_items}")
        print(f"Profit Margin:  {(total_profit/total_sales*100):.1f}%")
        
        # Show items sold
        items_sold = [item for item in sales_data if item['sold'] > 0]
        if items_sold:
            print(f"\n{'='*60}")
            print("Items Sold Today:")
            print(f"{'='*60}\n")
            for item in sorted(items_sold, key=lambda x: x['sold'], reverse=True):
                print(f"  {item['item_name']:20} {item['sold']:2} sold  ${item['sales']:6.2f}")
        
        # Show low stock
        low_stock_threshold = int(db.get_setting('low_stock_threshold') or 3)
        low_stock = [item for item in sales_data if item['inventory'] < low_stock_threshold]
        if low_stock:
            print(f"\n{'='*60}")
            print(f"Low Stock Alerts (< {low_stock_threshold}):")
            print(f"{'='*60}\n")
            for item in low_stock:
                print(f"  🔴 {item['item_name']:20} {item['inventory']}/{item['capacity']}")
        
        print(f"\n{'='*60}")
        print("Note: This data is NOT saved to database.")
        print("Run 'python3 daily_automation.py' to save today's data.")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == '__main__':
    check_today_live()
