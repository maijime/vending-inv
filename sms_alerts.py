#!/usr/bin/env python3
"""SMS alert system using Twilio."""
import os
from dotenv import load_dotenv

load_dotenv()

def send_sms(message: str, to_number: str = None):
    """Send SMS alert via Twilio."""
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_number = os.getenv('TWILIO_PHONE_NUMBER')
    to_number = to_number or os.getenv('ALERT_PHONE_NUMBER')
    
    # Check if Twilio is configured
    if not all([account_sid, auth_token, from_number, to_number]):
        print("⚠️  SMS not configured. Set Twilio credentials in .env")
        return False
    
    try:
        from twilio.rest import Client
        
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=message,
            from_=from_number,
            to=to_number
        )
        
        print(f"✓ SMS sent: {message.sid}")
        return True
        
    except ImportError:
        print("⚠️  Twilio not installed. Run: pip install twilio")
        return False
    except Exception as e:
        print(f"✗ Failed to send SMS: {e}")
        return False

def send_low_stock_alert(low_stock_items: list):
    """Send SMS alert for low stock items."""
    if not low_stock_items:
        return
    
    items_text = ", ".join([f"{item['item_name']} ({item['current_level']})" 
                            for item in low_stock_items[:5]])
    
    message = f"🔴 Vending Alert: {len(low_stock_items)} items low on stock: {items_text}"
    
    if len(low_stock_items) > 5:
        message += f" +{len(low_stock_items) - 5} more"
    
    send_sms(message)

def send_daily_summary_sms(summary: dict):
    """Send daily sales summary via SMS."""
    revenue = summary.get('total_revenue', 0)
    profit = summary.get('total_profit', 0)
    items = summary.get('total_items', 0)
    
    if revenue == 0:
        return  # Skip if no sales
    
    message = f"📊 Today's Sales: ${revenue:.2f} | Profit: ${profit:.2f} | Items: {items}"
    send_sms(message)

def send_critical_alert(message: str):
    """Send critical alert SMS."""
    send_sms(f"🚨 CRITICAL: {message}")

if __name__ == '__main__':
    # Test SMS
    send_sms("Test message from Vending System")
