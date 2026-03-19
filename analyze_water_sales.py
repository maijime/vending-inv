import pandas as pd
import os
from datetime import datetime

# Water bottle item number
WATER_ITEM = "0146"

# Date range
start_date = datetime(2022, 7, 1)
end_date = datetime(2025, 9, 30)

total_water_sold = 0
total_water_sales = 0.0
files_with_water = []

# Get all CSV files in out directory
out_dir = "out"
csv_files = [f for f in os.listdir(out_dir) if f.endswith('.csv')]

for filename in csv_files:
    try:
        # Parse date from filename
        date_parts = filename.replace('.csv', '').split('_to_')
        if len(date_parts) != 2:
            continue
            
        file_start = datetime.strptime(date_parts[0], '%Y%m%d')
        file_end = datetime.strptime(date_parts[1], '%Y%m%d')
        
        # Check if file date range overlaps with our target range
        if file_end < start_date or file_start > end_date:
            continue
            
        # Read the CSV file
        df = pd.read_csv(os.path.join(out_dir, filename))
        
        # Find water bottle row
        water_row = df[df['iNum'] == WATER_ITEM]
        
        if not water_row.empty:
            sold = pd.to_numeric(water_row['Sold'].iloc[0], errors='coerce')
            sales = pd.to_numeric(water_row['Sales'].iloc[0], errors='coerce')
            
            if pd.notna(sold) and sold > 0:
                total_water_sold += int(sold)
                total_water_sales += float(sales)
                files_with_water.append((filename, int(sold), float(sales)))
                
    except Exception as e:
        print(f"Error processing {filename}: {e}")

print(f"Water bottle sales analysis (July 1, 2022 - September 31, 2025):")
print(f"Total water bottles sold: {total_water_sold}")
print(f"Total water sales revenue: ${total_water_sales:.2f}")
print(f"Files with water sales: {len(files_with_water)}")

if files_with_water:
    print("\nDetailed breakdown:")
    for filename, sold, sales in files_with_water:
        print(f"  {filename}: {sold} bottles, ${sales:.2f}")