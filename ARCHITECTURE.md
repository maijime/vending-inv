# System Architecture

## Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    VENDING SYSTEM v2.0                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                   DATA COLLECTION LAYER                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  collect_data.py                                            │
│  ├─ Selenium WebDriver                                      │
│  ├─ Logs into seedlive.com                                  │
│  ├─ Extracts sales data                                     │
│  └─ Returns structured data                                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    DATABASE LAYER                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  database.py → vending.db (SQLite)                          │
│                                                              │
│  Tables:                                                     │
│  ├─ items              (product catalog)                    │
│  ├─ daily_sales        (sales records)                      │
│  ├─ inventory_snapshots (stock levels)                      │
│  ├─ home_inventory     (backup supplies)                    │
│  └─ settings           (configuration)                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   AUTOMATION LAYER                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  daily_automation.py                                        │
│  ├─ Runs at 4:15 PM (cron)                                  │
│  ├─ Calls collect_data.py                                   │
│  ├─ Saves to database                                       │
│  └─ Triggers email report                                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   REPORTING LAYER                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  email_report.py                                            │
│  ├─ Generates HTML email                                    │
│  ├─ Includes sales summary                                  │
│  ├─ Shows inventory levels                                  │
│  ├─ Highlights low stock                                    │
│  └─ Sends via Gmail SMTP                                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  PRESENTATION LAYER                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  app.py (Flask Web Server)                                  │
│                                                              │
│  Routes:                                                     │
│  ├─ /              → Dashboard home                         │
│  ├─ /inventory     → Machine & home inventory               │
│  ├─ /sales         → Sales history & analytics              │
│  ├─ /items         → Item management                        │
│  └─ /settings      → System configuration                   │
│                                                              │
│  Templates:                                                  │
│  ├─ base.html      → Layout & navigation                    │
│  ├─ index.html     → Dashboard overview                     │
│  ├─ inventory.html → Inventory management                   │
│  ├─ sales.html     → Sales reports                          │
│  ├─ items.html     → Item CRUD                              │
│  └─ settings.html  → Configuration                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    UTILITY SCRIPTS                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  load_historical.py  → Import historical data               │
│  test_setup.py       → Verify system configuration          │
│  quickstart.sh       → Quick start helper                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### Daily Automation Flow
```
┌──────────────┐
│  4:15 PM     │
│  Cron Job    │
└──────┬───────┘
       ↓
┌──────────────────────┐
│ daily_automation.py  │
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  collect_data.py     │
│  ├─ Login to portal  │
│  ├─ Extract data     │
│  └─ Return results   │
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│   database.py        │
│   ├─ Save sales      │
│   ├─ Save inventory  │
│   └─ Prevent dupes   │
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│  email_report.py     │
│  ├─ Generate HTML    │
│  ├─ Check sales > 0  │
│  └─ Send email       │
└──────────────────────┘
```

### User Interaction Flow
```
┌──────────────┐
│   Browser    │
└──────┬───────┘
       ↓
┌──────────────────────┐
│   app.py (Flask)     │
│   Port 5000          │
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│   database.py        │
│   ├─ Query data      │
│   ├─ Update records  │
│   └─ Return results  │
└──────┬───────────────┘
       ↓
┌──────────────────────┐
│   HTML Templates     │
│   ├─ Render data     │
│   └─ Display UI      │
└──────────────────────┘
```

## Deployment Options

### Option 1: Raspberry Pi (Recommended)
```
┌─────────────────────────────────────┐
│        Raspberry Pi                 │
│  ┌───────────────────────────────┐ │
│  │  Cron (4:15 PM daily)         │ │
│  │  └─ daily_automation.py       │ │
│  └───────────────────────────────┘ │
│  ┌───────────────────────────────┐ │
│  │  Systemd Service              │ │
│  │  └─ app.py (Flask)            │ │
│  │     Port 5000                 │ │
│  └───────────────────────────────┘ │
│  ┌───────────────────────────────┐ │
│  │  vending.db (SQLite)          │ │
│  └───────────────────────────────┘ │
└─────────────────────────────────────┘
         ↓                    ↓
    [Email]            [Local Network]
  mikejc96@gmail.com   http://raspberrypi.local:5000
```

### Option 2: Local Mac (Development)
```
┌─────────────────────────────────────┐
│        MacBook                      │
│  ┌───────────────────────────────┐ │
│  │  Manual execution             │ │
│  │  └─ python3 app.py            │ │
│  └───────────────────────────────┘ │
│  ┌───────────────────────────────┐ │
│  │  vending.db (SQLite)          │ │
│  └───────────────────────────────┘ │
└─────────────────────────────────────┘
         ↓
   http://localhost:5000
```

## Technology Stack

```
┌─────────────────────────────────────┐
│  Frontend                           │
│  ├─ HTML5                           │
│  ├─ CSS3 (inline)                   │
│  └─ Jinja2 Templates                │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  Backend                            │
│  ├─ Python 3.11                     │
│  ├─ Flask 3.0 (web framework)       │
│  └─ SQLite 3 (database)             │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  Data Collection                    │
│  ├─ Selenium 4.10 (web scraping)    │
│  ├─ Chrome WebDriver                │
│  └─ Pandas 2.2 (data processing)    │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  Automation                         │
│  ├─ Cron (scheduling)               │
│  ├─ Systemd (service management)    │
│  └─ Gmail SMTP (email delivery)     │
└─────────────────────────────────────┘
```

## Security Considerations

```
┌─────────────────────────────────────┐
│  Credentials                        │
│  ├─ .env file (gitignored)          │
│  ├─ Gmail app password              │
│  └─ Seedlive.com credentials        │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  Network                            │
│  ├─ Local network only              │
│  ├─ No public exposure              │
│  └─ No authentication (single user) │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│  Data                               │
│  ├─ SQLite file permissions         │
│  ├─ Regular backups recommended     │
│  └─ No sensitive customer data      │
└─────────────────────────────────────┘
```

## File Organization

```
vending-inv/
├── Core Scripts
│   ├── database.py           # Database operations
│   ├── collect_data.py       # Data collection
│   ├── email_report.py       # Email reporting
│   ├── daily_automation.py   # Main automation
│   └── app.py                # Web dashboard
│
├── Utilities
│   ├── load_historical.py    # Historical import
│   ├── test_setup.py         # Setup verification
│   └── quickstart.sh         # Quick start helper
│
├── Templates
│   ├── base.html             # Base layout
│   ├── index.html            # Dashboard home
│   ├── inventory.html        # Inventory page
│   ├── sales.html            # Sales page
│   ├── items.html            # Items page
│   └── settings.html         # Settings page
│
├── Documentation
│   ├── README.md             # Main readme
│   ├── SETUP_GUIDE.md        # Setup instructions
│   ├── IMPLEMENTATION_SUMMARY.md  # Implementation details
│   └── ARCHITECTURE.md       # This file
│
├── Configuration
│   ├── .env                  # Environment variables
│   ├── requirements.txt      # Python dependencies
│   └── .gitignore            # Git ignore rules
│
├── Data
│   ├── vending.db            # SQLite database
│   ├── in/items.csv          # Legacy items (migrated)
│   └── logs/                 # Log files
│
└── Legacy (preserved)
    ├── vending-inv.py        # Original script
    ├── run_all.py            # Original runner
    ├── profit_analysis.py    # Analysis script
    └── out/                  # Old CSV files
```

## Performance Characteristics

- **Data Collection:** ~5-10 seconds per day
- **Database Queries:** < 100ms for most operations
- **Dashboard Load Time:** < 1 second
- **Email Generation:** < 1 second
- **Storage:** ~1MB per year of data

## Scalability

Current system handles:
- ✅ 1 vending machine
- ✅ ~25 product types
- ✅ ~500 transactions/year
- ✅ Years of historical data

To scale to multiple machines:
- Add `machine_id` column to tables
- Update collection script for multiple machines
- Add machine selector to dashboard
- Aggregate reports across machines
