#!/usr/bin/env python3
"""Quick test script to verify system setup."""
import os
import sys
from dotenv import load_dotenv

def check_env():
    """Check environment variables."""
    load_dotenv()
    
    print("🔍 Checking environment variables...")
    
    required = {
        'SEED_USERNAME': os.getenv('SEED_USERNAME'),
        'SEED_PASSWORD': os.getenv('SEED_PASSWORD'),
        'GMAIL_USER': os.getenv('GMAIL_USER'),
        'GMAIL_APP_PASSWORD': os.getenv('GMAIL_APP_PASSWORD')
    }
    
    all_set = True
    for key, value in required.items():
        if value and value != 'your_app_password_here':
            print(f"  ✓ {key} is set")
        else:
            print(f"  ✗ {key} is NOT set")
            all_set = False
    
    return all_set

def check_database():
    """Check database exists and has data."""
    print("\n🗄️  Checking database...")
    
    if not os.path.exists('vending.db'):
        print("  ✗ Database not found. Run: python3 database.py")
        return False
    
    import database as db
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM items')
    item_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM daily_sales')
    sales_count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"  ✓ Database exists")
    print(f"  ✓ {item_count} items configured")
    print(f"  ✓ {sales_count} sales records")
    
    return True

def check_dependencies():
    """Check required packages."""
    print("\n📦 Checking dependencies...")
    
    required = ['selenium', 'pandas', 'flask', 'dotenv']
    all_installed = True
    
    for package in required:
        try:
            __import__(package)
            print(f"  ✓ {package} installed")
        except ImportError:
            print(f"  ✗ {package} NOT installed")
            all_installed = False
    
    return all_installed

def main():
    """Run all checks."""
    print("="*60)
    print("Vending System - Setup Verification")
    print("="*60 + "\n")
    
    env_ok = check_env()
    deps_ok = check_dependencies()
    db_ok = check_database()
    
    print("\n" + "="*60)
    
    if env_ok and deps_ok and db_ok:
        print("✅ All checks passed! System is ready.")
        print("\nNext steps:")
        print("  1. Test data collection: python3 collect_data.py")
        print("  2. Start dashboard: python3 app.py")
        print("  3. Test email: python3 email_report.py")
    else:
        print("⚠️  Some checks failed. Please fix the issues above.")
        
        if not env_ok:
            print("\n📝 Setup Gmail app password:")
            print("  1. Visit https://myaccount.google.com/apppasswords")
            print("  2. Create app password")
            print("  3. Add to .env file")
        
        if not deps_ok:
            print("\n📦 Install dependencies:")
            print("  pip install -r requirements.txt")
        
        if not db_ok:
            print("\n🗄️  Initialize database:")
            print("  python3 database.py")
    
    print("="*60 + "\n")

if __name__ == '__main__':
    main()
