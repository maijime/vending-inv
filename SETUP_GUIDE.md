# Vending Machine Management System - Setup Guide

## 🎯 Overview

This upgraded system provides:
- **Automated daily data collection** (no manual date entry)
- **SQLite database** (no duplicate files)
- **Daily email reports** at 4:15 PM
- **Web dashboard** for inventory, sales, and analytics
- **Home inventory tracking**

---

## 📋 Prerequisites

- Python 3.8+
- Chrome browser
- Gmail account (for email reports)
- Raspberry Pi (optional, for automation)

---

## 🚀 Quick Start (Local Testing)

### 1. Install Dependencies

```bash
cd /Users/e150302/code/py/vending-inv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Setup Gmail App Password

To send email reports, you need a Gmail App Password:

1. Go to https://myaccount.google.com/security
2. Enable 2-Step Verification (if not already enabled)
3. Go to https://myaccount.google.com/apppasswords
4. Create a new app password for "Mail"
5. Copy the 16-character password

### 3. Configure Environment

Edit `.env` file and add your Gmail app password:

```bash
GMAIL_USER=your_email@gmail.com
GMAIL_APP_PASSWORD=your_16_char_password_here
```

### 4. Initialize Database

```bash
python3 database.py
```

This will:
- Create `vending.db` SQLite database
- Migrate items from `in/items.csv`
- Set default settings

### 5. Test Data Collection

```bash
# Collect today's data
python3 collect_data.py

# Or collect specific date
python3 collect_data.py 2026-03-10
```

### 6. Test Email Report

```bash
python3 email_report.py
```

### 7. Start Web Dashboard

```bash
python3 app.py
```

Visit: http://localhost:5000

---

## 🍓 Raspberry Pi Setup

### 1. Initial Pi Setup

```bash
# SSH into your Pi
ssh pi@raspberrypi.local

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install python3-pip chromium-chromedriver -y
```

### 2. Transfer Project

```bash
# From your Mac
scp -r /Users/e150302/code/py/vending-inv pi@raspberrypi.local:~/
```

### 3. Install Python Packages on Pi

```bash
cd ~/vending-inv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Setup Daily Automation (Cron)

```bash
crontab -e
```

Add this line (runs at 4:15 PM daily):

```
15 16 * * * cd /home/pi/vending-inv && /home/pi/vending-inv/.venv/bin/python3 daily_automation.py >> /home/pi/vending-inv/logs/daily.log 2>&1
```

Create logs directory:

```bash
mkdir -p ~/vending-inv/logs
```

### 5. Setup Dashboard Auto-Start

Create systemd service:

```bash
sudo nano /etc/systemd/system/vending-dashboard.service
```

Add:

```ini
[Unit]
Description=Vending Dashboard
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/vending-inv
Environment="PATH=/home/pi/vending-inv/.venv/bin"
ExecStart=/home/pi/vending-inv/.venv/bin/python3 app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable vending-dashboard
sudo systemctl start vending-dashboard
```

Access dashboard at: http://raspberrypi.local:5000

---

## 📊 Usage Guide

### Daily Workflow

1. **Automatic** - System collects data at 4:15 PM daily
2. **Email** - You receive report if there were sales
3. **Dashboard** - Check http://raspberrypi.local:5000 anytime

### Managing Items

1. Go to **Items** page in dashboard
2. Add/edit/delete items directly (no CSV editing!)
3. Changes take effect immediately

### Tracking Home Inventory

1. Go to **Inventory** page
2. Update quantities for items you have at home
3. Get alerts when running low

### Viewing Sales History

1. Go to **Sales** page
2. Select date range
3. View daily breakdown and top sellers

### Loading Historical Data

To import data from previous years:

```bash
# Collect data for a date range (one day at a time)
python3 collect_data.py 2025-01-15
python3 collect_data.py 2025-01-16
# etc...
```

Or create a script to loop through dates.

---

## 🔧 Configuration

### Low Stock Threshold

Change in **Settings** page or directly:

```bash
sqlite3 vending.db "UPDATE settings SET value='5' WHERE key='low_stock_threshold'"
```

### Email Recipients

Edit `.env` file to change email address.

---

## 📁 File Structure

```
vending-inv/
├── database.py              # Database operations
├── collect_data.py          # Data collection script
├── email_report.py          # Email reporting
├── daily_automation.py      # Main automation script
├── app.py                   # Flask web dashboard
├── templates/               # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── inventory.html
│   ├── sales.html
│   ├── items.html
│   └── settings.html
├── vending.db              # SQLite database (created)
├── .env                    # Environment variables
├── requirements.txt        # Python dependencies
└── in/items.csv           # Legacy (migrated to DB)
```

---

## 🐛 Troubleshooting

### Email not sending

- Check Gmail app password is correct
- Verify 2-Step Verification is enabled
- Check `.env` file has correct credentials

### Dashboard not accessible

```bash
# Check if running
sudo systemctl status vending-dashboard

# View logs
sudo journalctl -u vending-dashboard -f
```

### Data collection fails

- Check Chrome/Chromium is installed
- Verify seedlive.com credentials
- Run manually to see errors: `python3 collect_data.py`

### Database issues

```bash
# Backup database
cp vending.db vending.db.backup

# Reinitialize (WARNING: deletes data)
rm vending.db
python3 database.py
```

---

## 🎨 Customization

### Add New Metrics

Edit `app.py` to add new routes and queries.

### Modify Email Template

Edit `email_report.py` `generate_html_report()` function.

### Change Automation Time

Edit crontab: `crontab -e`

---

## 📝 Notes

- Database automatically prevents duplicate entries for same date
- Old CSV files in `out/` can be deleted (data is in database)
- Dashboard is local network only (not exposed to internet)
- System skips email if zero sales that day

---

## 🆘 Support

For issues or questions, check:
1. Log files in `logs/` directory
2. Database with: `sqlite3 vending.db`
3. Manual test scripts to isolate problems

---

**Version:** 2.0  
**Last Updated:** March 2026
