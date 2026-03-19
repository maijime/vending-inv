import pandas as pd
from datetime import datetime
import os
import sys

# Get date range from command-line arguments
start_date_str = sys.argv[1]
end_date_str = sys.argv[2]

# Convert the date strings to datetime objects
start_date = datetime.strptime(start_date_str, "%Y%m%d")
end_date = datetime.strptime(end_date_str, "%Y%m%d")


# Construct the filename based on the date range
filename = f"out/{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.csv"

print(f"\nLoading file: {filename}")

# Check if the file exists
if not os.path.exists(filename):
    print(f"File {filename} does not exist.")
    exit()

# Load the CSV file
df = pd.read_csv(filename)

# Ensure the 'Inv' and 'Cap' columns are interpreted as numeric
df["Inv"] = pd.to_numeric(df["Inv"], errors='coerce').astype('Int64')
df["Cap"] = pd.to_numeric(df["Cap"], errors='coerce').astype('Int64')

# Calculate the restock quantity
df["Restock"] = df["Cap"] - df["Inv"]

# Determine which items need to be restocked
restock_items = df[df["Restock"] > 0]

# Print the items that need to be restocked
print("\nItems that need to be restocked:\n")
print(restock_items[["iName", "Restock"]].to_string(index=False))

output_dir = "out/restock/"
os.makedirs(output_dir, exist_ok=True)

output_path = os.path.join(output_dir, "restock_items.csv")

# Save the restock items to a new CSV file
restock_items.to_csv(output_path, index=False)