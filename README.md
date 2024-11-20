# Vending Machine Inventory Management

This script automates the process of tracking vending machine inventory and sales data. It logs into the vending machine management system, extracts sales data, and generates reports.

## Setup

### 1. Environment Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate

# Install required packages
pip install -r requirements.txt
```

### 2. Configuration
Create a .env file in the root directory:

```text
USERNAME=your_email@example.com
PASSWORD=your_password
```

## Project Structure
```text
vending-inv/
├── in/                  # Input files directory
│   └── items.csv       # Item data
├── out/                # Generated reports
├── .env               
├── .gitignore
├── requirements.txt
└── vending-inv.py
```

## Input File Format

### items.csv Requirements

The `in/items.csv` requires the following columns:

- `iName:` Item name
- `iNum:` Item number
- `Cap:` Maximum capacity
- `Cost:` Item price

### Example Format

```csv
iName,iNum,Cap,Cost
Cape Cod Chips BBQ,0111,7,1.25
Coca Cola,0141,15,1.50
```

## Usage
1. Make sure your `in/items.csv` is up to date with current inventory items

2. Run the script:

```bash
python3 run_all.py
```

## Generated Reports

### Output Directory

The script generates the following in the `out/` directory:
- Current inventory levels
- Daily sales report
- Revenue summary

### Dependencies
- selenium
- pandas
- python-dotenv
- webdriver_manager

### Important Notes
- Keep `.env` file secure and never commit to git
- `out/` directory is git-ignored
- Update `items.csv` when inventory changes