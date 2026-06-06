#!/usr/bin/env python3
"""Daily email report — sends machine status snapshot."""
import os, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from dotenv import load_dotenv
import database as db

load_dotenv()

MACHINE_ORDER = [
    ('Row 1 — Snacks',      ['0111','0113','0115','0117']),
    ('Row 2 — Snacks',      ['0121','0123','0125','0127']),
    ('Row 3 — Small Snacks',['0130','0131','0132','0133','0134','0135','0136','0137']),
    ('Drinks',              ['0140','0141','0142','0143','0144','0145','0146']),
]


def build_report():
    today      = datetime.now().strftime('%Y-%m-%d')
    yesterday  = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    last_restock = db.get_setting('last_restock_date') or '2000-01-01'
    threshold  = int(db.get_setting('low_stock_threshold') or 3)

    slots       = db.get_slots_with_levels()
    slots_by_num = {s['item_num']: s for s in slots}

    today_summary     = db.get_sales_summary(today, today)
    yesterday_summary = db.get_sales_summary(yesterday, yesterday)
    since_restock     = db.get_sales_summary(last_restock, today)

    low_slots = [s for s in slots if s['current_level'] < threshold]

    # ── Subject ──────────────────────────────────────────────────────────────
    if low_slots:
        subject = f"⚠️ Vending Report {today} — {len(low_slots)} slot{'s' if len(low_slots)!=1 else ''} low"
    else:
        subject = f"✅ Vending Report {today} — All good"

    # ── Plain-text body ───────────────────────────────────────────────────────
    lines = []

    def section(title):
        lines.append('')
        lines.append(title)
        lines.append('─' * len(title))

    # Today's summary
    section(f"TODAY — {today}")
    lines.append(f"  Revenue : ${today_summary['total_revenue'] or 0:.2f}")
    lines.append(f"  Profit  : ${today_summary['total_profit'] or 0:.2f}")
    lines.append(f"  Items   : {today_summary['total_items'] or 0}")

    # Yesterday
    section(f"YESTERDAY — {yesterday}")
    lines.append(f"  Revenue : ${yesterday_summary['total_revenue'] or 0:.2f}")
    lines.append(f"  Profit  : ${yesterday_summary['total_profit'] or 0:.2f}")
    lines.append(f"  Items   : {yesterday_summary['total_items'] or 0}")

    # Since last restock
    section(f"SINCE LAST RESTOCK ({last_restock})")
    lines.append(f"  Revenue : ${since_restock['total_revenue'] or 0:.2f}")
    lines.append(f"  Profit  : ${since_restock['total_profit'] or 0:.2f}")
    lines.append(f"  Items   : {since_restock['total_items'] or 0}")

    # Machine status
    section("MACHINE STATUS")
    for row_label, item_nums in MACHINE_ORDER:
        lines.append(f"\n  {row_label}")
        for num in item_nums:
            s = slots_by_num.get(num)
            if not s:
                continue
            level = s['current_level']
            cap   = s['capacity']
            pct   = int(level / cap * 100) if cap else 0
            if level < threshold:
                icon = '🔴'
            elif pct <= 50:
                icon = '🟡'
            else:
                icon = '🟢'
            bar_filled = int(pct / 10)
            bar = '█' * bar_filled + '░' * (10 - bar_filled)
            lines.append(f"    {icon} {s['name']:<14} {bar}  {level}/{cap}")

    # Low stock callout
    if low_slots:
        section("⚠️  LOW STOCK — NEEDS ATTENTION")
        for s in low_slots:
            lines.append(f"  • {s['name']} ({s['item_num']}) — {s['current_level']}/{s['capacity']} left")

    lines.append('')
    lines.append('─' * 40)
    lines.append(f"Sent {datetime.now().strftime('%Y-%m-%d %I:%M %p')} · vending.maitek.dev")

    return subject, '\n'.join(lines)


def send_report():
    gmail_user = os.getenv('GMAIL_USER')
    gmail_pass = os.getenv('GMAIL_APP_PASSWORD')

    if not gmail_user or not gmail_pass:
        print("Email not configured — set GMAIL_USER and GMAIL_APP_PASSWORD in .env")
        return False

    subject, body = build_report()

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = gmail_user
    msg['To']      = gmail_user
    msg.attach(MIMEText(body, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_user, gmail_pass)
            server.send_message(msg)
        print(f"✓ Report sent: {subject}")
        return True
    except Exception as e:
        print(f"✗ Failed to send: {e}")
        return False


if __name__ == '__main__':
    send_report()
