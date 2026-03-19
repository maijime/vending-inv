# Vending Machine Inventory Management System

**Version 2.0** - Automated inventory tracking, sales analytics, and reporting system.

## ✨ Features

- 🤖 **Automated Daily Collection** - Runs at 4:15 PM, no manual input needed
- 📧 **Email Reports** - Daily sales summary sent to your inbox
- 📊 **Web Dashboard** - View sales, inventory, and analytics
- 🏠 **Home Inventory Tracking** - Track backup supplies
- 💾 **SQLite Database** - No duplicate files, easy querying
- 🔔 **Low Stock Alerts** - Get notified when items need restocking

## 🚀 Quick Start

### 1. Setup Gmail App Password

1. Visit https://myaccount.google.com/apppasswords
2. Create app password for "Mail"
3. Add to `.env`:
   ```
   GMAIL_USER=your_email@gmail.com
   GMAIL_APP_PASSWORD=your_16_char_password
   ```

### 2. Initialize Database

```bash
python3 database.py
```

### 3. Test Data Collection

```bash
python3 collect_data.py
```

### 4. Start Dashboard

```bash
python3 app.py
```

Visit: http://localhost:5000

## 📖 Full Documentation

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for:
- Raspberry Pi setup instructions
- Daily automation configuration
- Troubleshooting guide
- Advanced features

## 🎯 Daily Automation

The system automatically:
1. Collects sales data at 4:15 PM
2. Stores in database (prevents duplicates)
3. Sends email report if sales > 0
4. Updates inventory levels

## 📁 Key Files

- `database.py` - Database schema and operations
- `collect_data.py` - Data collection from seedlive.com
- `email_report.py` - Email reporting system
- `daily_automation.py` - Main automation script
- `app.py` - Web dashboard
- `load_historical.py` - Import historical data

## 🔧 Configuration

### Change Low Stock Threshold

Dashboard → Settings → Low Stock Threshold

### Load Historical Data

```bash
python3 load_historical.py 2025-01-01 2025-12-31
```

### Manual Data Collection

```bash
python3 collect_data.py 2026-03-10
```

## 📊 Dashboard Pages

- **Home** - Today's summary and quick stats
- **Inventory** - Machine and home inventory levels
- **Sales** - Historical sales with date filtering
- **Items** - Add/edit/delete items (replaces CSV editing)
- **Settings** - Configure thresholds and preferences

## 🍓 Raspberry Pi Deployment

See [SETUP_GUIDE.md](SETUP_GUIDE.md) for complete Pi setup instructions.

Quick summary:
1. Transfer project to Pi
2. Setup cron job for 4:15 PM daily
3. Enable dashboard auto-start
4. Access at http://raspberrypi.local:5000

## 🆕 What's New in v2.0

- ✅ SQLite database (no more duplicate CSV files)
- ✅ Automated daily collection (no manual date entry)
- ✅ Email reports with HTML formatting
- ✅ Web dashboard for all management tasks
- ✅ Home inventory tracking
- ✅ Configurable low stock alerts
- ✅ Historical data import tool

## 📝 Migration from v1.0

Your old CSV files in `out/` are preserved but no longer used. The system now uses `vending.db`.

To import historical data:
```bash
python3 load_historical.py 2025-01-01 2025-12-31
```

## 🐛 Troubleshooting

**Email not sending?**
- Check Gmail app password in `.env`
- Verify 2-Step Verification enabled

**Dashboard not loading?**
- Check Flask is installed: `pip install flask`
- Verify port 5000 is available

**Data collection fails?**
- Test manually: `python3 collect_data.py`
- Check seedlive.com credentials in `.env`

## 📞 Support

Check logs in `logs/` directory or run scripts manually to see detailed errors.

---

**Created:** November 2024  
**Updated:** March 2026  
**Author:** Mike JC