# Email Setup

The system sends daily sales reports via Gmail SMTP.

## Setup

1. Enable [2-Step Verification](https://myaccount.google.com/security) on your Google account
2. Go to [App Passwords](https://myaccount.google.com/apppasswords)
3. Create a new app password (select "Mail")
4. Add to your `.env` file:

```
GMAIL_USER=your_email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

## How It Works

- `daily_automation.py` runs at 4:15 PM via cron
- Collects sales data from Seedlive
- Sends an HTML email with: sales summary, top sellers, low stock alerts, inventory levels
- Skips email if no sales that day (weekends/holidays)

## Test

```bash
python3 email_report.py
```
