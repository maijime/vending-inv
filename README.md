# Muscle Fuel Vending — Inventory & Sales Tracker

A lightweight inventory management and sales analytics system for vending machine operators. Built with Flask, SQLite, and Selenium.

Designed to run on a Raspberry Pi with [Tailscale](https://tailscale.com) for remote access.

## Features

- **Automated data collection** from Seedlive portal (daily at 4:15 PM via cron)
- **Mobile-first web dashboard** with iOS-style UI
- **Email reports** via Gmail with sales summary and low stock alerts
- **Inventory tracking** for machine and stock
- **Restock workflow** — enter new levels, auto-deducts from stock
- **Historical import** — bulk load past sales data in one shot
- **CSV export** for accounting and tax prep
- **Live sales check** — pull real-time data without saving to history

## Screenshots

Dashboard shows since-last-restock performance, revenue chart, today's sales, and week-over-week comparison.

## Getting Started

### Prerequisites

- Python 3.9+
- Chrome/Chromium + chromedriver
- A [Seedlive](https://seedlive.com) account with vending machine data

On Raspberry Pi:
```bash
sudo apt install chromium-chromedriver
```

### Install

```bash
git clone https://github.com/maijime/vending-inv.git
cd vending-inv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configure

Create a `.env` file:

```
SEED_USERNAME=your_seedlive_email
SEED_PASSWORD=your_seedlive_password
GMAIL_USER=your_email@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password
```

Gmail app password setup: [Google Account → Security → App Passwords](https://myaccount.google.com/apppasswords)

### Initialize

```bash
python3 database.py
```

This creates the SQLite database, seeds default items, and runs any pending migrations (products table, etc.).

Set your last restock date (used as the default date range across the dashboard):

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('vending.db')
conn.execute(\"INSERT OR REPLACE INTO settings (key, value) VALUES ('last_restock_date', '2026-03-02');\")
conn.commit()
conn.close()
"
```

Or set it later through the Settings page in the dashboard.

### Run

```bash
python3 app.py
```

Open `http://localhost:5001` on your phone or browser.

## Usage

### Daily Automation

Set up a cron job to collect data and send email reports:

```bash
crontab -e
# Add:
15 16 * * 1-5 cd /path/to/vending-inv && .venv/bin/python3 daily_automation.py
```

Runs at 4:15 PM, Monday–Friday. Skips email if no sales.

### Load Historical Data

```bash
python3 load_historical.py 2024-07-01 2026-03-19
```

Uses Seedlive's "Entire Range" report — one login, all data at once. Handles pagination automatically.

### Dashboard on Raspberry Pi

1. Clone repo and set up `.env` on the Pi
2. Run `python3 database.py` to initialize (or SCP your existing `vending.db`)
3. Set up a systemd service for the dashboard
4. Set up cron for daily automation
5. Install [Tailscale](https://tailscale.com) for remote access outside your network

## Project Structure

```
├── app.py                 # Flask dashboard (port 5001)
├── database.py            # SQLite schema and queries
├── collect_data.py        # Seedlive scraper
├── daily_automation.py    # Cron entry point (collect + email)
├── email_report.py        # HTML email reports via Gmail
├── load_historical.py     # Bulk historical data import
├── check_today.py         # CLI live sales check
├── templates/             # Jinja2 templates (iOS-style UI)
├── requirements.txt
├── .env                   # Credentials (not committed)
├── vending.db             # SQLite database (not committed)
└── legacy/                # Original v1 scripts (preserved)
```

## Configuration

All settings are managed through the dashboard at `/settings`:

- **Low stock threshold** — alert when inventory drops below this number
- **Last restock date** — tracks when you last restocked the machine
- **Email reports** — status and schedule info

## Tech Stack

- **Backend:** Flask, SQLite, Selenium
- **Frontend:** Vanilla HTML/CSS (iOS-style), Chart.js
- **Automation:** cron (data collection), systemd (dashboard)
- **Deployment:** Raspberry Pi + Tailscale

## License

MIT
