#!/usr/bin/env python3
"""Automated daily data collection script."""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import shutil
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv
import database as db

load_dotenv()

def get_vending_data(date_str: str):
    """Scrape vending machine data for a specific date."""
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    chromedriver_path = shutil.which('chromedriver') or '/usr/bin/chromedriver'
    driver = webdriver.Chrome(service=Service(chromedriver_path), options=chrome_options)
    
    try:
        # Login
        driver.get("https://seedlive.com/login.i")
        time.sleep(2)
        
        username = driver.find_element(By.NAME, "username")
        password = driver.find_element(By.NAME, "password")
        username.send_keys(os.getenv('SEED_USERNAME'))
        password.send_keys(os.getenv('SEED_PASSWORD'))
        
        login_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Sign In']")
        login_button.click()
        time.sleep(2)
        
        # Navigate to reports
        reports_link = driver.find_element(By.XPATH, "//a[img[@src='/images/reports.png']]")
        reports_link.click()
        time.sleep(2)
        
        build_report_link = driver.find_element(By.XPATH, "//a[@title='Build and run custom reports']")
        build_report_link.click()
        time.sleep(2)
        
        # Set date range (same day for daily report)
        year = date_obj.strftime("%Y")
        month = date_obj.strftime("%B")
        day = date_obj.day
        
        for date_type in ["begin", "end"]:
            year_select = Select(driver.find_element(By.ID, f"{date_type}Year"))
            year_select.select_by_value(year)
            
            month_select = Select(driver.find_element(By.ID, f"{date_type}Month"))
            month_select.select_by_value(month)
            
            day_select = Select(driver.find_element(By.ID, f"{date_type}Day"))
            day_select.select_by_value(str(day))
        
        # Run report
        run_report_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Run Report']")
        run_report_button.click()
        time.sleep(4)
        
        # Get totals
        totals_row = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "tr.groupFooterRow0"))
        )
        totals_link = totals_row.find_element(By.CSS_SELECTOR, "td.colId_8 a")
        totals_link.click()
        
        # Extract item data
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "td.colId_12 span"))
        )
        
        items = driver.find_elements(By.CSS_SELECTOR, "td.colId_12 span")
        
        # Get items from database
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT item_num, item_name, capacity, unit_cost FROM items WHERE active = 1')
        db_items = {row['item_num']: dict(row) for row in cursor.fetchall()}
        conn.close()
        
        # Initialize inventory tracking
        inventory = {}
        for item_num, item_data in db_items.items():
            inventory[item_num] = {
                'item_num': item_num,
                'item_name': item_data['item_name'],
                'capacity': item_data['capacity'],
                'sold': 0,
                'total_amount': 0.00,
                'unit_cost': item_data['unit_cost']
            }
        
        # Process sales
        for item in items:
            item_text = item.text
            item_parts = item_text.split(", ")
            for part in item_parts:
                if "Two-Tier Pricing" in part:
                    # Handle electronic payment fees
                    fee_info = part.split("(")[1].strip(")")
                    if " * $" in fee_info:
                        fee_count, fee_amount = fee_info.split(" * $")
                        fee_count = int(fee_count)
                        fee_amount = float(fee_amount)
                    else:
                        fee_count = 1
                        fee_amount = float(fee_info.strip("$"))
                    for _ in range(fee_count):
                        # Add fee to the last item in the list
                        last_item_code = item_parts[-2].split("(")[0]
                        if last_item_code in inventory:
                            inventory[last_item_code]['total_amount'] += fee_amount
                else:
                    # Handle regular items
                    item_code, item_price = part.split("(")
                    item_price = float(item_price.strip(")$"))
                    if item_code in inventory:
                        inventory[item_code]['sold'] += 1
                        inventory[item_code]['total_amount'] += item_price
        
        # Calculate final data
        sales_data = []
        for item_num, data in inventory.items():
            sales_data.append({
                'item_num': item_num,
                'item_name': data['item_name'],
                'capacity': data['capacity'],
                'inventory': data['capacity'] - data['sold'],
                'sold': data['sold'],
                'price': round(data['total_amount'] / data['sold'], 2) if data['sold'] > 0 else 0.00,
                'sales': round(data['total_amount'], 2),
                'cost': data['unit_cost'],
                'profit': round(data['total_amount'] - (data['unit_cost'] * data['sold']), 2)
            })
        
        return sales_data
        
    finally:
        driver.quit()

def collect_daily_data(date_str: str = None):
    """Collect and store daily data."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    
    print(f"Collecting data for {date_str}...")
    
    try:
        sales_data = get_vending_data(date_str)
        db.save_daily_data(date_str, sales_data)
        
        total_sales = sum(item['sales'] for item in sales_data)
        total_profit = sum(item['profit'] for item in sales_data)
        
        print(f"✓ Data collected: ${total_sales:.2f} sales, ${total_profit:.2f} profit")
        return sales_data, total_sales > 0
        
    except Exception as e:
        print(f"✗ Error collecting data: {e}")
        return None, False

if __name__ == '__main__':
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else None
    collect_daily_data(date)
