from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
from datetime import datetime
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv
import os
import sys

load_dotenv()

# User input for start and end days
start_date_str = sys.argv[1]
end_date_str = sys.argv[2]

# Convert the date strings to datetime objects
start_date = datetime.strptime(start_date_str, "%Y%m%d")
end_date = datetime.strptime(end_date_str, "%Y%m%d")

# Step 1: Set up Selenium in headless mode
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_options
)
driver.get("https://seedlive.com/login.i")

# Step 2: Log into the website
time.sleep(2)  # wait for the page to load
username = driver.find_element(By.NAME, "username")
password = driver.find_element(By.NAME, "password")

username_env = os.getenv('SEED_USERNAME')
password_env = os.getenv('SEED_PASSWORD')

username.send_keys(username_env)
password.send_keys(password_env)
login_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Sign In']")
login_button.click()

# Step 3: Navigate to the report page
time.sleep(2)  # wait for the page to load
reports_link = driver.find_element(By.XPATH, "//a[img[@src='/images/reports.png']]")
reports_link.click()

# Step 4: Build a report
time.sleep(2)  # wait for the page to load
build_report_link = driver.find_element(By.XPATH, "//a[@title='Build and run custom reports']")
build_report_link.click()

# Step 5: Set the start date
time.sleep(2)  # wait for the page to load
start_year = start_date.strftime("%Y")
start_month = start_date.strftime("%B")
start_day = start_date.day

start_year_select = Select(driver.find_element(By.ID, "beginYear"))
start_year_select.select_by_value(start_year)

start_month_select = Select(driver.find_element(By.ID, "beginMonth"))
start_month_select.select_by_value(start_month)

start_day_select = Select(driver.find_element(By.ID, "beginDay"))
start_day_select.select_by_value(str(start_day))

if end_date != datetime.now().strftime("%m/%d/%Y"):
    end_year = end_date.strftime("%Y")
    end_month = end_date.strftime("%B")
    end_day = end_date.day
    
    end_year_select = Select(driver.find_element(By.ID, "endYear"))
    end_year_select.select_by_value(end_year)
    
    end_month_select = Select(driver.find_element(By.ID, "endMonth"))
    end_month_select.select_by_value(end_month)
    
    end_day_select = Select(driver.find_element(By.ID, "endDay"))
    end_day_select.select_by_value(str(end_day))

# Step 6: Run the report
run_report_button = driver.find_element(By.CSS_SELECTOR, "input[type='submit'][value='Run Report']")
run_report_button.click()

# Add a space after inputting dates
print("\n")
# Step 7: Extract and process data
print("Loading report... Please wait.")
for _ in tqdm(range(40), desc="Generating report"):
    time.sleep(0.1)  # Simulate waiting for the report to generate
# Add a space before displaying the table
print("\n")

time.sleep(2)
totals_row = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, "tr.groupFooterRow0"))
)
totals_link = totals_row.find_element(By.CSS_SELECTOR, "td.colId_8 a")
totals_link.click()

# Step 8: Extract item data from the next page
time.sleep(2)  # wait for the page to load
items = driver.find_elements(By.CSS_SELECTOR, "td.colId_12 span")

# Initialize inventory tracking dictionary
inventory = {
    "0111": {"capacity": 7, "sold": 0, "total_amount": 0.00},
    "0113": {"capacity": 7, "sold": 0, "total_amount": 0.00},
    "0115": {"capacity": 7, "sold": 0, "total_amount": 0.00},
    "0117": {"capacity": 7, "sold": 0, "total_amount": 0.00},
    "0121": {"capacity": 7, "sold": 0, "total_amount": 0.00},
    "0123": {"capacity": 7, "sold": 0, "total_amount": 0.00},
    "0125": {"capacity": 7, "sold": 0, "total_amount": 0.00},
    "0127": {"capacity": 7, "sold": 0, "total_amount": 0.00},
    "0130": {"capacity": 14, "sold": 0, "total_amount": 0.00},
    "0131": {"capacity": 14, "sold": 0, "total_amount": 0.00},
    "0132": {"capacity": 14, "sold": 0, "total_amount": 0.00},
    "0133": {"capacity": 14, "sold": 0, "total_amount": 0.00},
    "0134": {"capacity": 14, "sold": 0, "total_amount": 0.00},
    "0135": {"capacity": 14, "sold": 0, "total_amount": 0.00},
    "0136": {"capacity": 14, "sold": 0, "total_amount": 0.00},
    "0137": {"capacity": 14, "sold": 0, "total_amount": 0.00},
    "0140": {"capacity": 15, "sold": 0, "total_amount": 0.00},
    "0141": {"capacity": 15, "sold": 0, "total_amount": 0.00},
    "0142": {"capacity": 15, "sold": 0, "total_amount": 0.00},
    "0143": {"capacity": 15, "sold": 0, "total_amount": 0.00},
    "0144": {"capacity": 15, "sold": 0, "total_amount": 0.00},
    "0145": {"capacity": 15, "sold": 0, "total_amount": 0.00},
    "0146": {"capacity": 15, "sold": 0, "total_amount": 0.00},
}

# Process each item
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
                # Assuming electronic payment fees apply to the last item in the list
                last_item_code = item_parts[-2].split("(")[0]
                inventory[last_item_code]["total_amount"] += fee_amount
        else:
            # Handle regular items
            item_code, item_price = part.split("(")
            item_price = float(item_price.strip(")$"))
            if item_code in inventory:
                inventory[item_code]["sold"] += 1
                inventory[item_code]["total_amount"] += item_price

item_name = pd.read_csv("in/items.csv")
item_names = dict(zip(item_name["iNum"].astype(str).str.zfill(4), item_name["iName"]))
item_costs = dict(zip(item_name["iNum"].astype(str).str.zfill(4), item_name["cost"]))

# Prepare data for table
data = {
    "iName": [item_names.get(item, "Unknown") for item in inventory],
    "iNum": list(inventory.keys()),
    "Cap": [inventory[item]["capacity"] for item in inventory],
    "Inv": [inventory[item]["capacity"] - inventory[item]["sold"] for item in inventory],
    "Sold": [inventory[item]["sold"] for item in inventory],
    "Price": [
        round(inventory[item]["total_amount"] / inventory[item]["sold"], 2)
        if inventory[item]["sold"] > 0 
        else 0.00
        for item in inventory
    ],
    "Sales": [round(inventory[item]["total_amount"], 2) for item in inventory],
    "Cost": [round(item_costs.get(item, 0.0), 2) for item in inventory],
    "Profit": [
        round(inventory[item]["total_amount"] - (item_costs.get(item, 0.0) * inventory[item]["sold"]), 2)
        if not pd.isna(item_costs.get(item)) else 0.00
        for item in inventory
    ]
}

# Create DataFrame
df = pd.DataFrame(data)

total_profit = sum(data['Profit'])

# Format the numeric columns for display
for col in ['Price', 'Sales', 'Cost', 'Profit']:
    df[col] = df[col].map('{:.2f}'.format)

# Create a display version with selected columns
display_columns =  ["iName", "iNum", "Cap", "Inv", "Sold", "Price", "Sales", "Cost", "Profit"]
df_display = df[display_columns]

# Add section headers
sections = ["011", "012", "013", "014"]
section_rows = []

for section in sections:
    section_data = df_display[df_display["iNum"].str.startswith(section)]
    section_rows.append(pd.DataFrame([{col: "" for col in display_columns}]))
    section_rows.append(section_data)

# Concatenate all sections
df_display_with_sections = pd.concat(section_rows, ignore_index=True)

# Display the table without index (only showing selected columns)
print(df_display_with_sections.to_string(index=False))

# Extract total amount of all items sold
totals_row = driver.find_element(By.CSS_SELECTOR, "tr.groupFooterRow0")
total_amount = float(totals_row.find_element(By.CSS_SELECTOR, "td.colId_10 span").text.strip("$"))
total_items_sold = int(totals_row.find_element(By.CSS_SELECTOR, "td.colId_13 span").text)

# Print total items sold and total amount
print(f"Total items sold: {total_items_sold}")
print(f"Total amount sold: ${total_amount:.2f}")
print(f"Total profit: ${total_profit:.2f}")

# Create the output directory if it doesn't exist
output_dir = "out"
os.makedirs(output_dir, exist_ok=True)

# Construct the filename based on the date range
filename = f"{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"
output_path = os.path.join(output_dir, filename)

# But still save the full DataFrame with all columns to CSV
df_display_with_sections.to_csv(output_path, index=False)

# Step 9: Close the driver
driver.quit()