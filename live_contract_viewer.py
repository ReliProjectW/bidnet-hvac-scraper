#!/usr/bin/env python3
"""
Live SQLite Contract Viewer - Real-time contract monitoring
"""

import sqlite3
import pandas as pd
import time
import os
import sys
from datetime import datetime
import subprocess

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def play_alert():
    """Play terminal bell alert"""
    print("\a", end="", flush=True)
    # Alternative system notification (macOS)
    try:
        subprocess.run(['osascript', '-e', 'display notification "Contract viewer updated!" with title "HVAC Scraper"'], 
                      capture_output=True, check=False)
    except:
        pass

def get_contract_summary(db_path="data/bidnet_scraper.db"):
    """Get summary of contracts in database"""
    try:
        conn = sqlite3.connect(db_path)
        
        # Get total count
        total_query = "SELECT COUNT(*) FROM contracts"
        total_count = conn.execute(total_query).fetchone()[0]
        
        # Get contracts with details
        contracts_query = """
        SELECT 
            id,
            title,
            agency,
            location,
            estimated_value,
            bid_due_date,
            source_url,
            created_at,
            processing_status
        FROM contracts 
        ORDER BY created_at DESC
        """
        
        df = pd.read_sql_query(contracts_query, conn)
        conn.close()
        
        return total_count, df
    except Exception as e:
        print(f"❌ Error accessing database: {e}")
        return 0, pd.DataFrame()

def format_currency(value):
    """Format currency value"""
    if pd.isna(value) or value is None:
        return "N/A"
    try:
        return f"${float(value):,.2f}"
    except:
        return str(value)

def display_contracts(total_count, df):
    """Display contracts in a formatted table"""
    clear_screen()
    
    print("🏢 HVAC CONTRACT LIVE VIEWER")
    print("=" * 80)
    print(f"📊 Total Contracts: {total_count}")
    print(f"🕐 Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    if df.empty:
        print("📭 No contracts found in database")
        return
    
    for idx, row in df.iterrows():
        print(f"\n📋 Contract #{row['id']}")
        print(f"   Title: {row['title']}")
        print(f"   Agency: {row['agency']}")
        print(f"   Location: {row['location']}")
        print(f"   Value: {format_currency(row['estimated_value'])}")
        print(f"   Due Date: {row['bid_due_date'] or 'N/A'}")
        print(f"   Status: {row['processing_status']}")
        print(f"   Source: {row['source_url']}")
        print(f"   Created: {row['created_at']}")
        print("-" * 80)
    
    print(f"\n🔄 Refreshing every 10 seconds... (Ctrl+C to exit)")

def get_extraction_attempts(db_path="data/bidnet_scraper.db"):
    """Get recent extraction attempts"""
    try:
        conn = sqlite3.connect(db_path)
        attempts_query = """
        SELECT 
            extraction_flag_type,
            flag_reason,
            target_url,
            created_at
        FROM extraction_attempts 
        ORDER BY created_at DESC
        LIMIT 10
        """
        
        attempts_df = pd.read_sql_query(attempts_query, conn)
        conn.close()
        return attempts_df
    except Exception as e:
        return pd.DataFrame()

def display_extraction_status(attempts_df):
    """Display recent extraction attempts"""
    print("\n🚩 RECENT EXTRACTION ATTEMPTS")
    print("-" * 80)
    
    if attempts_df.empty:
        print("📭 No extraction attempts found")
        return
    
    for idx, row in attempts_df.iterrows():
        status_icon = "❌" if row['extraction_flag_type'] == 'no_rfp_found' else "✅"
        print(f"{status_icon} {row['extraction_flag_type']}: {row['flag_reason']}")
        print(f"   Target: {row['target_url']}")
        print(f"   Time: {row['created_at']}")

def main():
    """Main viewer loop"""
    print("🚀 Starting Live Contract Viewer...")
    play_alert()  # Alert on startup
    
    last_count = 0
    
    try:
        while True:
            total_count, contracts_df = get_contract_summary()
            attempts_df = get_extraction_attempts()
            
            display_contracts(total_count, contracts_df)
            display_extraction_status(attempts_df)
            
            # Alert if contract count changed
            if total_count != last_count:
                print(f"\n🔔 CONTRACT COUNT CHANGED: {last_count} → {total_count}")
                play_alert()
                last_count = total_count
            
            # Wait before next refresh
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n\n👋 Contract viewer stopped")
        play_alert()
    except Exception as e:
        print(f"\n❌ Viewer error: {e}")
        play_alert()

if __name__ == "__main__":
    main()