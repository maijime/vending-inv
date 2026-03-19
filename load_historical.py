#!/usr/bin/env python3
"""Fast historical data loader using Seedlive's Entire Range report.
One login, one report, all transactions parsed at once."""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from datetime import datetime
from collections import defaultdict
import shutil, time, sys, os
from dotenv import load_dotenv
import database as db

load_dotenv()


def load_historical_data(start_date_str: str, end_date_str: str):
    start = datetime.strptime(start_date_str, "%Y-%m-%d")
    end = datetime.strptime(end_date_str, "%Y-%m-%d")

    print(f"\n{'='*50}")
    print(f"Loading {start_date_str} to {end_date_str} (Entire Range)")
    print(f"{'='*50}\n")

    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    chromedriver_path = shutil.which('chromedriver') or '/usr/bin/chromedriver'
    driver = webdriver.Chrome(service=Service(chromedriver_path), options=opts)

    try:
        # Login
        print("Logging in...", flush=True)
        driver.get("https://seedlive.com/login.i")
        time.sleep(3)
        driver.find_element(By.NAME, "username").send_keys(os.getenv('SEED_USERNAME'))
        driver.find_element(By.NAME, "password").send_keys(os.getenv('SEED_PASSWORD'))
        driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Sign In']").click()
        time.sleep(4)

        # Navigate to report builder
        print("Opening report builder...", flush=True)
        driver.find_element(By.XPATH, "//a[img[@src='/images/reports.png']]").click()
        time.sleep(2)
        driver.find_element(By.XPATH, "//a[@title='Build and run custom reports']").click()
        time.sleep(3)

        # Set Entire Range mode
        Select(driver.find_element(By.ID, "rangeType")).select_by_value("ALL")
        time.sleep(1)

        # Set date range
        Select(driver.find_element(By.ID, "beginYear")).select_by_value(str(start.year))
        Select(driver.find_element(By.ID, "beginMonth")).select_by_value(start.strftime("%B"))
        Select(driver.find_element(By.ID, "beginDay")).select_by_value(str(start.day))
        Select(driver.find_element(By.ID, "beginTime")).select_by_value("0:00")
        Select(driver.find_element(By.ID, "endYear")).select_by_value(str(end.year))
        Select(driver.find_element(By.ID, "endMonth")).select_by_value(end.strftime("%B"))
        Select(driver.find_element(By.ID, "endDay")).select_by_value(str(end.day))
        Select(driver.find_element(By.ID, "endTime")).select_by_value("23:00")

        # Dismiss any date alert
        try:
            driver.switch_to.alert.accept()
        except:
            pass

        # Run report
        print("Running report...", flush=True)
        driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Run Report']").click()

        # Wait for summary page
        for i in range(30):
            time.sleep(2)
            try:
                driver.switch_to.alert.accept()
                continue
            except:
                pass
            links = [a for a in driver.find_elements(By.TAG_NAME, "a") if "$" in a.text]
            if links:
                break
        else:
            print("ERROR: Report didn't load in 60s")
            return

        # Click the total to get detail page
        total_link = max(links, key=lambda a: float(a.text.replace("$", "").replace(",", "")))
        print(f"Total: {total_link.text} — clicking for detail...", flush=True)
        total_link.click()

        # Wait for detail page
        for i in range(30):
            time.sleep(2)
            try:
                driver.switch_to.alert.accept()
                continue
            except:
                pass
            items = driver.find_elements(By.CSS_SELECTOR, "td.colId_12")
            if items:
                break
        else:
            print("ERROR: Detail page didn't load in 60s")
            return

        # Get items from DB
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT item_num, item_name, capacity, unit_cost FROM items WHERE active = 1')
        db_items = {row['item_num']: dict(row) for row in cursor.fetchall()}
        conn.close()

        # Parse all transaction rows
        print("Parsing transactions...", flush=True)
        rows = driver.find_elements(By.CSS_SELECTOR, "td.colId_12")
        # daily_data[date][item_num] = {sold, total_amount}
        daily_data = defaultdict(lambda: defaultdict(lambda: {'sold': 0, 'total_amount': 0.0}))
        parsed = 0

        for cell in rows:
            row = cell.find_element(By.XPATH, "..")
            # Get date from colId_6
            try:
                date_cell = row.find_element(By.CSS_SELECTOR, "td.colId_6")
                date_text = date_cell.text.strip()  # "03/18/2026 12:09 PM"
                date_str = datetime.strptime(date_text, "%m/%d/%Y %I:%M %p").strftime("%Y-%m-%d")
            except:
                continue

            # Get items from colId_12 span
            try:
                items_span = cell.find_element(By.TAG_NAME, "span")
                items_text = items_span.text  # "0142($1.75), Two-Tier Pricing($0.10)"
            except:
                continue

            parts = items_text.split(", ")
            for part in parts:
                if "Two-Tier Pricing" in part:
                    # Add fee to the preceding item
                    fee_str = part.split("(")[1].strip(")$")
                    fee = float(fee_str)
                    # Find the last real item in this transaction
                    for prev in reversed(parts):
                        if "Two-Tier Pricing" not in prev:
                            item_code = prev.split("(")[0]
                            if item_code in db_items:
                                daily_data[date_str][item_code]['total_amount'] += fee
                            break
                else:
                    item_code = part.split("(")[0]
                    price_str = part.split("(")[1].strip(")$")
                    price = float(price_str)
                    if item_code in db_items:
                        daily_data[date_str][item_code]['sold'] += 1
                        daily_data[date_str][item_code]['total_amount'] += price
            parsed += 1

        print(f"Parsed {parsed} transactions across {len(daily_data)} days", flush=True)

        # Save to database
        saved = 0
        for date_str in sorted(daily_data.keys()):
            sales_data = []
            for item_num, data in daily_data[date_str].items():
                item = db_items[item_num]
                sold = data['sold']
                total = data['total_amount']
                sales_data.append({
                    'item_num': item_num,
                    'item_name': item['item_name'],
                    'capacity': item['capacity'],
                    'inventory': item['capacity'] - sold,
                    'sold': sold,
                    'price': round(total / sold, 2) if sold > 0 else 0,
                    'sales': round(total, 2),
                    'cost': item['unit_cost'],
                    'profit': round(total - (item['unit_cost'] * sold), 2)
                })

            # Add zero-sold items
            for item_num, item in db_items.items():
                if item_num not in daily_data[date_str]:
                    sales_data.append({
                        'item_num': item_num, 'item_name': item['item_name'],
                        'capacity': item['capacity'], 'inventory': item['capacity'],
                        'sold': 0, 'price': 0, 'sales': 0,
                        'cost': item['unit_cost'], 'profit': 0
                    })

            db.save_daily_data(date_str, sales_data)
            total_rev = sum(d['sales'] for d in sales_data)
            print(f"  ✓ {date_str}: ${total_rev:.2f}", flush=True)
            saved += 1

        print(f"\n{'='*50}")
        print(f"Done! {saved} days saved to database.")
        print(f"{'='*50}\n")

    finally:
        driver.quit()


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python3 load_historical.py START_DATE END_DATE")
        print("Example: python3 load_historical.py 2024-07-01 2026-03-19")
        sys.exit(1)
    load_historical_data(sys.argv[1], sys.argv[2])
