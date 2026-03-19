# Running Locally vs Raspberry Pi

## TL;DR: You can run it ANYWHERE! 🎉

The system works identically on:
- ✅ Your Mac (locally)
- ✅ Raspberry Pi
- ✅ Any Linux server
- ✅ Windows (with minor tweaks)

## Comparison

| Feature | Local (Mac) | Raspberry Pi |
|---------|-------------|--------------|
| **Dashboard** | ✅ Works | ✅ Works |
| **Data Collection** | ✅ Works | ✅ Works |
| **Email Reports** | ✅ Works | ✅ Works |
| **SMS Alerts** | ✅ Works | ✅ Works |
| **Automation** | ⚠️ Manual/Scheduled | ✅ Automatic (cron) |
| **Always On** | ❌ Only when Mac is on | ✅ 24/7 |
| **Power Usage** | ~50W | ~2W |
| **Cost** | $0 (you have it) | $0 (you have it) |
| **Access** | localhost only | Network accessible |

## Option 1: Run Locally on Mac

### Pros:
- ✅ No setup needed (already working)
- ✅ Faster for testing/development
- ✅ Easy to modify and debug
- ✅ Full access to all features

### Cons:
- ❌ Mac must be on and awake
- ❌ Manual scheduling (or launchd setup)
- ❌ Dashboard only accessible on Mac

### How to Use:

**Manual Execution:**
```bash
cd /Users/e150302/code/py/vending-inv
source .venv/bin/activate

# Run automation anytime
python3 daily_automation.py

# Start dashboard
python3 app.py
# Visit: http://localhost:5000
```

**Scheduled Automation (macOS launchd):**

Create: `~/Library/LaunchAgents/com.vending.daily.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.vending.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/e150302/code/py/vending-inv/.venv/bin/python3</string>
        <string>/Users/e150302/code/py/vending-inv/daily_automation.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>16</integer>
        <key>Minute</key>
        <integer>15</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/Users/e150302/code/py/vending-inv/logs/daily.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/e150302/code/py/vending-inv/logs/error.log</string>
</dict>
</plist>
```

Load it:
```bash
mkdir -p ~/code/py/vending-inv/logs
launchctl load ~/Library/LaunchAgents/com.vending.daily.plist
```

## Option 2: Run on Raspberry Pi

### Pros:
- ✅ Always on (24/7)
- ✅ Low power consumption
- ✅ Automatic scheduling (cron)
- ✅ Network accessible dashboard
- ✅ Set it and forget it

### Cons:
- ⚠️ Initial setup required (~30 min)
- ⚠️ Need to configure Pi

### How to Use:

See `SETUP_GUIDE.md` for complete Pi setup.

**Quick summary:**
```bash
# 1. Transfer to Pi
scp -r vending-inv pi@raspberrypi.local:~/

# 2. Setup on Pi
ssh pi@raspberrypi.local
cd ~/vending-inv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Setup cron (4:15 PM daily)
crontab -e
# Add: 15 16 * * * cd ~/vending-inv && .venv/bin/python3 daily_automation.py >> logs/daily.log 2>&1

# 4. Setup dashboard auto-start
# (see SETUP_GUIDE.md for systemd service)
```

Access dashboard: http://raspberrypi.local:5000

## Option 3: Hybrid Approach (Recommended for Testing)

**Best of both worlds:**

1. **Develop/Test on Mac:**
   - Make changes locally
   - Test features
   - View dashboard at localhost:5000

2. **Deploy to Pi for Production:**
   - Transfer when ready
   - Let Pi handle automation
   - Access dashboard from anywhere on network

### Workflow:
```bash
# On Mac: Test changes
python3 daily_automation.py
python3 app.py

# When ready: Deploy to Pi
rsync -av --exclude='.venv' --exclude='*.db' \
  /Users/e150302/code/py/vending-inv/ \
  pi@raspberrypi.local:~/vending-inv/
```

## Which Should You Choose?

### Choose Mac if:
- 🏠 Mac is always on anyway
- 🧪 You want to test/modify frequently
- 💻 You prefer working locally
- 🎯 You'll manually run it daily

### Choose Raspberry Pi if:
- 🔌 You want true automation
- 🌐 You want network access to dashboard
- ⚡ You want low power consumption
- 🎯 You want "set and forget"

### Choose Hybrid if:
- 🧪 You want to develop locally
- 🚀 But deploy for production
- 🎯 Best for long-term use

## My Recommendation

**Start Local, Deploy to Pi Later:**

1. **Week 1-2: Run on Mac**
   - Test everything works
   - Get comfortable with system
   - Verify email/SMS work
   - Load historical data

2. **Week 3+: Deploy to Pi**
   - Once you're confident it works
   - Transfer to Pi
   - Enable automation
   - Enjoy hands-free operation

## Network Access

### Mac (Local Only):
```
Dashboard: http://localhost:5000
Access: Only from your Mac
```

### Mac (Network Accessible):
```bash
# Run with network access
python3 app.py --host=0.0.0.0

# Access from other devices
http://your-mac-ip:5000
# Example: http://192.168.1.100:5000
```

### Raspberry Pi:
```
Dashboard: http://raspberrypi.local:5000
Access: Any device on your network
```

## Data Portability

**Database is portable!**

```bash
# Copy database from Mac to Pi
scp vending.db pi@raspberrypi.local:~/vending-inv/

# Copy database from Pi to Mac
scp pi@raspberrypi.local:~/vending-inv/vending.db .
```

You can switch between Mac and Pi anytime without losing data.

## Summary

**You asked: "Can we run it locally or does it have to run on the raspberry pi?"**

**Answer: You can run it ANYWHERE!**

- ✅ Mac works perfectly
- ✅ Pi works perfectly
- ✅ Both work the same
- ✅ Database is portable
- ✅ Your choice!

**For automation:**
- Mac: Use launchd (see above)
- Pi: Use cron (see SETUP_GUIDE.md)
- Both: Work great!

**My suggestion:** Start on Mac, move to Pi when ready. No rush!
