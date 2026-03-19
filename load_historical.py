#!/usr/bin/env python3
"""Load historical data for a date range."""
from datetime import datetime, timedelta
import sys
import time
import os
import database as db
from collect_data import collect_daily_data

def load_historical_data(start_date_str: str, end_date_str: str):
    """Load data for each day in the date range."""
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
    
    current_date = start_date
    success_count = 0
    skip_count = 0
    
    # Suppress selenium errors
    os.environ['WDM_LOG'] = '0'
    
    print(f"\n{'='*60}")
    print(f"Loading historical data from {start_date_str} to {end_date_str}")
    print(f"{'='*60}\n")
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        
        # Check if data already exists
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM daily_sales WHERE date = ?', (date_str,))
        exists = cursor.fetchone()[0] > 0
        
        # Check if previously marked as no-data
        cursor.execute('SELECT COUNT(*) FROM settings WHERE key = ? AND value = ?', 
                      (f'no_data_{date_str}', '1'))
        no_data_marked = cursor.fetchone()[0] > 0
        conn.close()
        
        if exists:
            skip_count += 1
            print(f"⊘ {date_str} - Already exists, skipping")
            current_date += timedelta(days=1)
            continue
        
        if no_data_marked:
            skip_count += 1
            print(f"○ {date_str} - Previously marked as no data, skipping")
            current_date += timedelta(days=1)
            continue
        
        try:
            # Suppress stderr temporarily
            import sys
            from io import StringIO
            old_stderr = sys.stderr
            sys.stderr = StringIO()
            
            sales_data, has_sales = collect_daily_data(date_str)
            
            # Restore stderr
            sys.stderr = old_stderr
            
            if sales_data:
                success_count += 1
                status = "✓" if has_sales else "○"
                print(f"{status} {date_str} - {'Sales recorded' if has_sales else 'No sales (weekend/holiday)'}")
                
                # If no sales, mark as no-data to skip in future
                if not has_sales:
                    conn = db.get_connection()
                    cursor = conn.cursor()
                    cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
                                 (f'no_data_{date_str}', '1'))
                    conn.commit()
                    conn.close()
            else:
                skip_count += 1
                print(f"○ {date_str} - No data available")
                
                # Mark as no-data
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
                             (f'no_data_{date_str}', '1'))
                conn.commit()
                conn.close()
                
        except KeyboardInterrupt:
            print("\n\nStopped by user.")
            break
        except Exception as e:
            # Restore stderr if error
            sys.stderr = old_stderr
            
            # Likely weekend/holiday with no data
            skip_count += 1
            print(f"○ {date_str} - Skipped (weekend/holiday)")
            
            # Mark as no-data to skip in future
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
                         (f'no_data_{date_str}', '1'))
            conn.commit()
            conn.close()
        
        current_date += timedelta(days=1)
        time.sleep(2)  # Delay to prevent crashes
    
    print(f"\n{'='*60}")
    print(f"Complete: {success_count} successful, {skip_count} skipped")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python3 load_historical.py START_DATE END_DATE")
        print("Example: python3 load_historical.py 2025-01-01 2025-12-31")
        sys.exit(1)
    
    load_historical_data(sys.argv[1], sys.argv[2])
