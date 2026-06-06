#!/usr/bin/env python3
"""Daily email report — HTML format."""
import os, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from dotenv import load_dotenv
import database as db

load_dotenv()

MACHINE_ORDER = [
    ('Row 1 — Snacks',       ['0111','0113','0115','0117']),
    ('Row 2 — Snacks',       ['0121','0123','0125','0127']),
    ('Row 3 — Small Snacks', ['0130','0131','0132','0133','0134','0135','0136','0137']),
    ('Drinks',               ['0140','0141','0142','0143','0144','0145','0146']),
]


def build_report():
    today        = datetime.now().strftime('%Y-%m-%d')
    yesterday    = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    last_restock = db.get_setting('last_restock_date') or '2000-01-01'
    threshold    = int(db.get_setting('low_stock_threshold') or 3)

    slots        = db.get_slots_with_levels()
    slots_by_num = {s['item_num']: s for s in slots}

    today_sum     = db.get_sales_summary(today, today)
    yesterday_sum = db.get_sales_summary(yesterday, yesterday)
    restock_sum   = db.get_sales_summary(last_restock, today)

    low_slots = [s for s in slots if s['current_level'] < threshold]

    # Subject
    if low_slots:
        subject = f"⚠️ Vending {today} — {len(low_slots)} slot{'s' if len(low_slots)!=1 else ''} low"
    else:
        subject = f"✅ Vending {today} — All good"

    # ── HTML ─────────────────────────────────────────────────────────────────
    def stat_card(label, revenue, profit, items):
        return f"""
        <td style="width:33%;padding:0 6px;text-align:center">
          <div style="background:#1a1d27;border:1px solid #2a2d3a;border-radius:10px;padding:14px 8px">
            <div style="font-size:11px;color:#64748b;margin-bottom:6px;text-transform:uppercase;letter-spacing:.05em">{label}</div>
            <div style="font-size:20px;font-weight:700;color:#22c55e">${revenue:.2f}</div>
            <div style="font-size:12px;color:#94a3b8;margin-top:2px">profit ${profit:.2f}</div>
            <div style="font-size:12px;color:#94a3b8">{items} items</div>
          </div>
        </td>"""

    def slot_row(s, threshold):
        level = s['current_level']
        cap   = s['capacity']
        pct   = int(level / cap * 100) if cap else 0
        if level < threshold:
            dot = '#ef4444'
        elif pct <= 50:
            dot = '#eab308'
        else:
            dot = '#22c55e'
        bar_color = dot
        return f"""
        <tr>
          <td style="padding:7px 8px;white-space:nowrap">
            <span style="display:inline-block;width:10px;height:10px;border-radius:50%;
                         background:{dot};margin-right:6px;vertical-align:middle"></span>
            <span style="color:#e2e8f0;font-size:13px">{s['name']}</span>
          </td>
          <td style="padding:7px 8px;width:120px">
            <div style="background:#2a2d3a;border-radius:4px;height:6px;overflow:hidden">
              <div style="background:{bar_color};height:100%;width:{pct}%;border-radius:4px"></div>
            </div>
          </td>
          <td style="padding:7px 8px;text-align:right;font-size:13px;
                     color:{'#ef4444' if level < threshold else '#94a3b8'};
                     white-space:nowrap;font-weight:{'700' if level < threshold else '400'}">
            {level}/{cap}
          </td>
        </tr>"""

    # Build machine section rows
    machine_html = ''
    for row_label, item_nums in MACHINE_ORDER:
        row_slots = [slots_by_num[n] for n in item_nums if n in slots_by_num]
        if not row_slots:
            continue
        machine_html += f"""
        <tr>
          <td colspan="3" style="padding:14px 8px 4px;font-size:11px;
              color:#64748b;text-transform:uppercase;letter-spacing:.06em;
              font-weight:600;border-top:1px solid #2a2d3a">
            {row_label}
          </td>
        </tr>"""
        for s in row_slots:
            machine_html += slot_row(s, threshold)

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#0f1117;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<div style="max-width:520px;margin:0 auto;padding:24px 16px">

  <!-- Header -->
  <div style="margin-bottom:20px">
    <div style="font-size:18px;font-weight:700;color:#e2e8f0">Vending Report</div>
    <div style="font-size:13px;color:#64748b;margin-top:2px">{datetime.now().strftime('%A, %B %d %Y · %I:%M %p')}</div>
  </div>

  <!-- Stats -->
  <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:20px;table-layout:fixed">
    <tr>
      {stat_card('Today',            today_sum['total_revenue'] or 0,     today_sum['total_profit'] or 0,     today_sum['total_items'] or 0)}
      {stat_card('Yesterday',        yesterday_sum['total_revenue'] or 0, yesterday_sum['total_profit'] or 0, yesterday_sum['total_items'] or 0)}
      {stat_card(f'Since {last_restock}', restock_sum['total_revenue'] or 0,  restock_sum['total_profit'] or 0,  restock_sum['total_items'] or 0)}
    </tr>
  </table>

  <!-- Machine status -->
  <div style="background:#1a1d27;border:1px solid #2a2d3a;border-radius:12px;
              padding:4px 8px 8px;margin-bottom:20px">
    <div style="font-size:11px;color:#64748b;text-transform:uppercase;
                letter-spacing:.06em;font-weight:600;padding:12px 8px 0">
      Machine Status
    </div>
    <table width="100%" cellpadding="0" cellspacing="0">
      {machine_html}
    </table>
  </div>

  <!-- Footer -->
  <div style="text-align:center;font-size:11px;color:#475569">
    <a href="https://vending.maitek.dev" style="color:#3b82f6;text-decoration:none">vending.maitek.dev</a>
  </div>

</div>
</body>
</html>"""

    return subject, html


def send_report():
    gmail_user = os.getenv('GMAIL_USER')
    gmail_pass = os.getenv('GMAIL_APP_PASSWORD')

    if not gmail_user or not gmail_pass:
        print("Email not configured — set GMAIL_USER and GMAIL_APP_PASSWORD in .env")
        return False

    subject, html = build_report()

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = gmail_user
    msg['To']      = gmail_user
    msg.attach(MIMEText(html, 'html'))

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
