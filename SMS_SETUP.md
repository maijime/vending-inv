# SMS Alerts Setup Guide

## Overview

SMS alerts notify you instantly about:
- 🔴 **Low stock warnings** (always sent when items < threshold)
- 📊 **Daily sales summary** (sent if sales > 0)

## Cost

Twilio pricing (as of 2026):
- **SMS:** $0.0079 per message
- **Monthly cost:** ~$0.50-$2 (2-3 messages/day max)
- **Free trial:** $15 credit to test

## Setup Steps

### 1. Create Twilio Account

1. Go to https://www.twilio.com/try-twilio
2. Sign up (free trial includes $15 credit)
3. Verify your phone number

### 2. Get Twilio Credentials

After signing up:

1. Go to Twilio Console: https://console.twilio.com/
2. Find your **Account SID** and **Auth Token**
3. Get a phone number:
   - Click "Get a Trial Number" or
   - Buy a number ($1/month): https://console.twilio.com/us1/develop/phone-numbers/manage/search

### 3. Configure .env File

Add to your `.env` file:

```bash
# SMS Alerts (Twilio)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+15551234567
ALERT_PHONE_NUMBER=+15559876543
```

**Where to find:**
- `TWILIO_ACCOUNT_SID`: Twilio Console dashboard
- `TWILIO_AUTH_TOKEN`: Twilio Console dashboard (click "Show")
- `TWILIO_PHONE_NUMBER`: Your Twilio phone number (with +1)
- `ALERT_PHONE_NUMBER`: Your personal phone number (with +1)

### 4. Install Twilio Package

```bash
cd /Users/e150302/code/py/vending-inv
source .venv/bin/activate
pip install twilio
```

### 5. Test SMS

```bash
python3 sms_alerts.py
```

You should receive a test message!

### 6. Enable in Dashboard

1. Go to http://localhost:5000/settings
2. Check "Enable SMS Alerts"
3. Click "Save Settings"

## SMS Message Examples

### Low Stock Alert
```
🔴 Vending Alert: 3 items low on stock: 
Coca Cola (2), Lays Orig (1), Sprite (2)
```

### Daily Summary
```
📊 Today's Sales: $45.50 | Profit: $32.15 | Items: 28
```

## Trial Account Limitations

With free trial:
- ✅ Can send SMS
- ⚠️ Can only send to verified phone numbers
- ⚠️ Messages include "Sent from your Twilio trial account"

To remove limitations:
- Upgrade account (no monthly fee)
- Only pay per message ($0.0079 each)

## Verify Phone Numbers (Trial Only)

If using trial account:

1. Go to: https://console.twilio.com/us1/develop/phone-numbers/manage/verified
2. Click "Add a new number"
3. Enter your phone number
4. Verify with code

## Disable SMS Alerts

**Option 1: Dashboard**
- Go to Settings
- Uncheck "Enable SMS Alerts"

**Option 2: Remove from .env**
- Comment out or remove Twilio credentials

**Option 3: Skip installation**
- Don't install `twilio` package
- System will skip SMS gracefully

## Troubleshooting

### "SMS not configured"
- Check all 4 Twilio variables are set in `.env`
- Verify no typos in credentials

### "Twilio not installed"
```bash
pip install twilio
```

### "Unable to create record"
- Trial account: verify recipient phone number
- Check phone numbers include country code (+1)
- Verify Twilio account has credit

### "Authentication failed"
- Double-check Account SID and Auth Token
- Make sure no extra spaces in `.env`

## Cost Optimization

To minimize costs:
- SMS only sent when needed (low stock or sales)
- No SMS on zero-sales days
- Typically 1-2 messages per day = $0.50/month

## Alternative: Email-to-SMS

Free alternative (no Twilio needed):
- Most carriers offer email-to-SMS gateways
- Example: `5551234567@txt.att.net` (AT&T)
- Add as second email recipient
- Limited to 160 characters

**Carrier gateways:**
- AT&T: `@txt.att.net`
- Verizon: `@vtext.com`
- T-Mobile: `@tmomail.net`
- Sprint: `@messaging.sprintpcs.com`

## Running Locally vs Raspberry Pi

**Both work the same!**

### Local (Mac)
```bash
# Run automation manually
python3 daily_automation.py

# Or schedule with launchd
# (see macOS scheduling guide)
```

### Raspberry Pi
```bash
# Runs automatically via cron at 4:15 PM
# No difference in functionality
```

**Recommendation:** 
- **Test locally first** to verify SMS works
- **Deploy to Pi** for 24/7 automation

## Privacy & Security

- Twilio credentials stored in `.env` (gitignored)
- Phone numbers not exposed in code
- Messages sent over encrypted connection
- No data stored by Twilio (just delivery logs)

## Support

**Twilio Support:**
- Docs: https://www.twilio.com/docs/sms
- Console: https://console.twilio.com/
- Help: https://support.twilio.com/

**System Issues:**
- Test: `python3 sms_alerts.py`
- Check logs: `logs/daily.log`
- Verify settings in dashboard

---

**Quick Start:**
1. Sign up at twilio.com (free trial)
2. Get credentials from console
3. Add to `.env` file
4. Run `pip install twilio`
5. Test with `python3 sms_alerts.py`
6. Enable in dashboard settings

**Monthly Cost:** ~$0.50-$2 (after free trial)
