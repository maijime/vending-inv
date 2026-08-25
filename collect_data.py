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
import time, os, sys
from dotenv import load_dotenv
import database as db

load_dotenv()


def get_vending_data(date_str: str):
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    chromedriver_path = shutil.which('chromedriver') or '/usr/bin/chromedriver'
    driver = webdriver.Chrome(service=Service(chromedriver_path), options=chrome_options)
    wait = WebDriverWait(driver, 20)

    try:
        # ── Login ────────────────────────────────────────────────────────────
        print(f"  Logging in...")
        driver.get("https://seedlive.com/login.i")
        wait.until(EC.presence_of_element_located((By.NAME, "username")))
        driver.find_element(By.NAME, "username").send_keys(os.getenv('SEED_USERNAME'))
        driver.find_element(By.NAME, "password").send_keys(os.getenv('SEED_PASSWORD'))
        driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Sign In']").click()

        # Wait for post-login redirect to settle before navigating
        time.sleep(5)
        driver.get("https://seedlive.com/activity_parameters.i?usage=B&selectedTab=10&selectedMenuItem=130&profileId=192860")

        # ── Set date range ───────────────────────────────────────────────────
        print(f"  Setting date to {date_str}...")
        year  = date_obj.strftime("%Y")
        month = date_obj.strftime("%B")
        day   = str(date_obj.day)

        wait.until(EC.presence_of_element_located((By.ID, "beginYear")))
        for dt in ["begin", "end"]:
            Select(driver.find_element(By.ID, f"{dt}Year")).select_by_value(year)
            Select(driver.find_element(By.ID, f"{dt}Month")).select_by_value(month)
            Select(driver.find_element(By.ID, f"{dt}Day")).select_by_value(day)

        # ── Run report ───────────────────────────────────────────────────────
        driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Run Report']").click()

        totals_row = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "tr.groupFooterRow0"))
        )
        totals_row.find_element(By.CSS_SELECTOR, "td.colId_8 a").click()

        # ── Wait for ALL items to fully render ───────────────────────────────
        # Wait for first span, then give JS extra time to finish loading the rest
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "td.colId_12 span")))
        time.sleep(4)  # let remaining rows render

        items = driver.find_elements(By.CSS_SELECTOR, "td.colId_12 span")
        print(f"  Found {len(items)} item rows")

        # ── Load slots from DB ───────────────────────────────────────────────
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT item_num, name, capacity FROM slots WHERE active = 1')
        db_items = {row['item_num']: dict(row) for row in cursor.fetchall()}
        conn.close()

        inventory = {
            num: {'item_num': num, 'item_name': d['name'], 'capacity': d['capacity'],
                  'sold': 0, 'total_amount': 0.0, 'unit_cost': 0.0}
            for num, d in db_items.items()
        }

        # ── Parse sales ──────────────────────────────────────────────────────
        for item in items:
            item_text = item.text.strip()
            if not item_text or "(" not in item_text:
                continue
            parts = item_text.split(", ")
            for part in parts:
                part = part.strip()
                if not part or "(" not in part:
                    continue
                try:
                    if "Two-Tier Pricing" in part:
                        fee_info = part.split("(")[1].strip(")")
                        if " * $" in fee_info:
                            fee_count, fee_amt = fee_info.split(" * $")
                            fee_total = int(fee_count) * float(fee_amt)
                        else:
                            fee_total = float(fee_info.strip("$"))
                        # Attribute fee to last real item in this row
                        last_code = next(
                            (p.split("(")[0].strip() for p in reversed(parts)
                             if "Two-Tier" not in p and "(" in p), None)
                        if last_code and last_code in inventory:
                            inventory[last_code]['total_amount'] += fee_total
                    else:
                        code, price_str = part.split("(", 1)
                        code  = code.strip()
                        price = float(price_str.strip(")$"))
                        if code in inventory:
                            inventory[code]['sold'] += 1
                            inventory[code]['total_amount'] += price
                except Exception:
                    continue

        # ── Build result ─────────────────────────────────────────────────────
        sales_data = []
        for num, d in inventory.items():
            sales_data.append({
                'item_num':  num,
                'item_name': d['item_name'],
                'capacity':  d['capacity'],
                'sold':      d['sold'],
                'price':     round(d['total_amount'] / d['sold'], 2) if d['sold'] else 0.0,
                'sales':     round(d['total_amount'], 2),
                'cost':      0.0,
                'profit':    round(d['total_amount'], 2),
            })

        total = sum(x['sales'] for x in sales_data)
        print(f"  Parsed ${total:.2f} across {sum(x['sold'] for x in sales_data)} items")
        return sales_data

    finally:
        driver.quit()


def collect_daily_data(date_str: str = None):
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"Collecting {date_str}...")
    try:
        sales_data = get_vending_data(date_str)
        if not sales_data:
            print(f"  ⚠ No data returned")
            return None, False
        db.save_daily_data(date_str, sales_data)
        total = sum(x['sales'] for x in sales_data)
        print(f"  ✓ Saved ${total:.2f}")
        return sales_data, True
    except Exception as e:
        import traceback
        print(f"  ✗ {e}")
        traceback.print_exc()
        return None, False


def backfill(start_str: str, end_str: str):
    """Collect data for every weekday between start and end dates inclusive."""
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end   = datetime.strptime(end_str,   "%Y-%m-%d")
    cur   = start
    while cur <= end:
        if cur.weekday() < 5:  # weekdays only
            collect_daily_data(cur.strftime("%Y-%m-%d"))
        else:
            print(f"Skipping {cur.strftime('%Y-%m-%d')} (weekend)")
        cur += timedelta(days=1)


if __name__ == '__main__':
    if len(sys.argv) == 3:
        # backfill mode: python3 collect_data.py 2026-08-15 2026-08-20
        backfill(sys.argv[1], sys.argv[2])
    elif len(sys.argv) == 2:
        collect_daily_data(sys.argv[1])
    else:
        collect_daily_data()
