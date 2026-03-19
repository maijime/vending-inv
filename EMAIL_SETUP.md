# Email Setup Guide - Simple & Free

## What You Need

✅ Gmail account: `musclefuelvending@gmail.com` (you already have this)  
✅ 5 minutes  
✅ **Cost: $0 (completely free!)**

---

## Step-by-Step Setup

### Step 1: Enable 2-Step Verification

1. Go to: https://myaccount.google.com/security
2. Sign in with `musclefuelvending@gmail.com`
3. Scroll to "2-Step Verification"
4. Click "Get Started" or "Turn On"
5. Follow prompts (usually verify with phone number)

### Step 2: Create App Password

1. Go to: https://myaccount.google.com/apppasswords
2. Sign in with `musclefuelvending@gmail.com`
3. Under "Select app" → Choose **"Mail"**
4. Under "Select device" → Choose **"Other"** → Type **"Vending System"**
5. Click **"Generate"**
6. **Copy the 16-character password** (looks like: `abcd efgh ijkl mnop`)

### Step 3: Add to .env File

```bash
# Open terminal
cd /Users/e150302/code/py/vending-inv

# Edit .env file
nano .env

# Find this line:
GMAIL_APP_PASSWORD=your_app_password_here

# Replace with your password (remove spaces):
GMAIL_APP_PASSWORD=abcdefghijklmnop

# Save: Ctrl+O, Enter, Ctrl+X
```

### Step 4: Test Email

```bash
cd /Users/e150302/code/py/vending-inv
source .venv/bin/activate
python3 email_report.py
```

**You should receive a test email at musclefuelvending@gmail.com!**

---

## What You'll Receive

### Daily Email (4:15 PM, if sales > 0)

**Subject:** Vending Report - Mar 10, 2026 - $45.50

**Contains:**
- 📊 Today's sales summary (revenue, profit, items sold)
- 🏆 Top 3 sellers
- 🔴 Low stock alerts (items < 3)
- 📦 Current inventory levels

---

## Troubleshooting

### "Authentication failed"
- Double-check app password in `.env` (no spaces)
- Make sure 2-Step Verification is enabled
- Try generating a new app password

### "No email received"
- Check spam folder
- Verify email sent successfully (check terminal output)
- Test with: `python3 email_report.py`

### "GMAIL_APP_PASSWORD not set"
- Make sure `.env` file is saved
- Restart dashboard: `pkill -f app.py && python3 app.py`

---

## Running Locally vs Raspberry Pi

### Both work the same!

**On Mac (Local):**
```bash
# Run manually anytime
python3 daily_automation.py

# Or schedule with launchd (see LOCAL_VS_PI.md)
```

**On Raspberry Pi:**
```bash
# Runs automatically at 4:15 PM via cron
# See SETUP_GUIDE.md for Pi setup
```

---

## Summary

✅ **Free** - No costs, ever  
✅ **Simple** - Just need Gmail app password  
✅ **Automatic** - Sends daily at 4:15 PM  
✅ **Smart** - Only sends if there were sales  
✅ **Informative** - Sales, inventory, and alerts in one email  

**Total setup time: 5 minutes**

---

## Next Steps

1. ✅ Setup Gmail app password (above)
2. ✅ Test email: `python3 email_report.py`
3. ✅ Run automation: `python3 daily_automation.py`
4. ✅ Start dashboard: `python3 app.py`
5. Optional: Deploy to Raspberry Pi for 24/7 automation

Done! 🎉
