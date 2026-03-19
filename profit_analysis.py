#!/usr/bin/env python3
import os
import csv
from datetime import datetime
import re

def parse_date_from_filename(filename):
    """Extract date range from filename like '20241206_to_20241230.csv'"""
    match = re.search(r'(\d{8})_to_(\d{8})\.csv', filename)
    if match:
        start_date = datetime.strptime(match.group(1), '%Y%m%d')
        end_date = datetime.strptime(match.group(2), '%Y%m%d')
        return start_date, end_date
    return None, None

def calculate_profit_from_file(filepath):
    """Calculate total profit from a CSV file"""
    total_sales = 0
    total_cost = 0
    total_profit = 0
    
    try:
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('Sales') and row.get('Cost') and row.get('Profit'):
                    try:
                        sales = float(row['Sales'])
                        cost = float(row['Cost'])
                        profit = float(row['Profit'])
                        
                        total_sales += sales
                        total_cost += cost
                        total_profit += profit
                    except ValueError:
                        continue
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return 0, 0, 0
    
    return total_sales, total_cost, total_profit

def main():
    out_dir = '/Users/e150302/code/py/vending-inv/out'
    
    total_profit_all = 0
    total_sales_all = 0
    total_cost_all = 0
    monthly_data = {}
    
    # Process all CSV files
    for filename in os.listdir(out_dir):
        if filename.endswith('.csv') and '_to_' in filename:
            filepath = os.path.join(out_dir, filename)
            start_date, end_date = parse_date_from_filename(filename)
            
            if start_date and end_date:
                sales, cost, profit = calculate_profit_from_file(filepath)
                
                if profit > 0:  # Only count files with actual data
                    total_sales_all += sales
                    total_cost_all += cost
                    total_profit_all += profit
                    
                    # Group by month
                    month_key = start_date.strftime('%Y-%m')
                    if month_key not in monthly_data:
                        monthly_data[month_key] = {'sales': 0, 'cost': 0, 'profit': 0, 'days': 0}
                    
                    monthly_data[month_key]['sales'] += sales
                    monthly_data[month_key]['cost'] += cost
                    monthly_data[month_key]['profit'] += profit
                    
                    days = (end_date - start_date).days + 1
                    monthly_data[month_key]['days'] += days
                    
                    print(f"{filename}: Sales=${sales:.2f}, Cost=${cost:.2f}, Profit=${profit:.2f}")
    
    print(f"\n=== TOTAL ANALYSIS ===")
    print(f"Total Sales: ${total_sales_all:.2f}")
    print(f"Total Cost: ${total_cost_all:.2f}")
    print(f"Total Profit: ${total_profit_all:.2f}")
    print(f"Profit Margin: {(total_profit_all/total_sales_all)*100:.1f}%")
    
    print(f"\n=== MONTHLY BREAKDOWN ===")
    monthly_profits = []
    for month in sorted(monthly_data.keys()):
        data = monthly_data[month]
        monthly_profits.append(data['profit'])
        print(f"{month}: Sales=${data['sales']:.2f}, Profit=${data['profit']:.2f}, Days={data['days']}")
    
    if monthly_profits:
        avg_monthly = sum(monthly_profits) / len(monthly_profits)
        print(f"\nAverage Monthly Profit: ${avg_monthly:.2f}")
        print(f"Number of months with data: {len(monthly_profits)}")

if __name__ == "__main__":
    main()
