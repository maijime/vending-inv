import subprocess
from datetime import datetime

def get_valid_date(prompt, default_date):
    date_str = input(prompt)
    if date_str:
        try:
            # Try to parse the date string to ensure it's in the correct format
            valid_date = datetime.strptime(date_str, "%m/%d/%Y")
            return valid_date.strftime("%m/%d/%Y") 
        except ValueError:
            print("Invalid date format. Please enter the date in mm/dd/yyyy format.")
            exit()
    else:
        if default_date == datetime.now().strftime("%m/%d/%Y"):
            return default_date
        use_default = input("No date entered, hit enter for Todays date. Use original date (O) 10/15/2024? ").strip().upper()
        if use_default == '':
            return datetime.now().strftime("%m/%d/%Y")
        elif use_default == 'O':
            return default_date
        else:
            print("Invalid choice. Please hit enter for todays date or 'O' for original date.")
            exit()
            
# Original date
orig_date = "10/15/2024"

# User input for start and end days
print("Please enter the start and end day range for the report.")
start_date = get_valid_date("Enter the start day (mm/dd/yyyy, default is today): ", orig_date)
end_date = get_valid_date("Enter the end day (mm/dd/yyyy, default is today): ", datetime.now().strftime("%m/%d/%Y"))

# Convert the date strings to datetime objects
start_date_str = datetime.strptime(start_date, "%m/%d/%Y").strftime("%Y%m%d")
end_date_str = datetime.strptime(end_date, "%m/%d/%Y").strftime("%Y%m%d")

# Run vending-inv.py script
print("Running vending-inv.py script...")
subprocess.run(["python3", "vending-inv.py", start_date_str, end_date_str])

# Run restock-inv.py script
print("Running restock-inv.py script...")
subprocess.run(["python3", "restock-inv.py", start_date_str, end_date_str])