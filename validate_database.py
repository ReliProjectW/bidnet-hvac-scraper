#!/usr/bin/env python3
"""
Database Validation and Status Check with Audio Alerts
"""

import sqlite3
import pandas as pd
import subprocess
from datetime import datetime

def play_alert(message="Database check complete"):
    """Play terminal bell and system notification"""
    print("\a", end="", flush=True)  # Terminal bell
    try:
        subprocess.run(['osascript', '-e', f'display notification "{message}" with title "HVAC Scraper Database"'], 
                      capture_output=True, check=False)
    except:
        pass

def check_database_status(db_path="data/bidnet_scraper.db"):
    """Comprehensive database status check"""
    print("🔍 DATABASE STATUS CHECK")
    print("=" * 60)
    print(f"🕐 Check Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"📊 Tables Found: {len(tables)}")
        print(f"   {', '.join(tables)}")
        
        # Check each table
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"   📋 {table}: {count} records")
            except Exception as e:
                print(f"   ❌ {table}: Error - {e}")
        
        print("\n" + "=" * 60)
        
        # Detailed contract analysis
        if 'contracts' in tables:
            print("🏢 CONTRACT ANALYSIS")
            print("-" * 40)
            
            # Get contracts with details
            contracts_query = """
            SELECT 
                id, title, agency, location, source_url, 
                processing_status, created_at
            FROM contracts 
            ORDER BY created_at DESC
            """
            df = pd.read_sql_query(contracts_query, conn)
            
            if not df.empty:
                print(f"📊 Total Contracts: {len(df)}")
                print(f"🕐 Latest: {df['created_at'].iloc[0]}")
                print(f"🕐 Oldest: {df['created_at'].iloc[-1]}")
                
                # Status breakdown
                status_counts = df['processing_status'].value_counts()
                print("\n📈 Status Breakdown:")
                for status, count in status_counts.items():
                    print(f"   {status}: {count}")
                
                print("\n📋 Contract Details:")
                for idx, row in df.iterrows():
                    print(f"   {row['id']:2d}. {row['title'][:50]}...")
                    print(f"       Agency: {row['agency']}")
                    print(f"       Location: {row['location']}")
                    print(f"       Status: {row['processing_status']}")
                    print(f"       Source: {row['source_url']}")
                    print()
            else:
                print("📭 No contracts found")
        
        # Check extraction attempts
        if 'extraction_attempts' in tables:
            print("🚩 EXTRACTION ATTEMPTS")
            print("-" * 40)
            
            attempts_query = """
            SELECT 
                extraction_flag_type, 
                COUNT(*) as count 
            FROM extraction_attempts 
            GROUP BY extraction_flag_type
            """
            attempts_df = pd.read_sql_query(attempts_query, conn)
            
            if not attempts_df.empty:
                for idx, row in attempts_df.iterrows():
                    print(f"   {row['extraction_flag_type']}: {row['count']}")
            else:
                print("   📭 No extraction attempts found")
        
        conn.close()
        
        print("\n" + "=" * 60)
        print("✅ Database validation complete!")
        play_alert("Database validation complete")
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        play_alert("Database validation failed")

def main():
    """Run database validation"""
    check_database_status()
    
    # Offer to watch for changes
    response = input("\n🔄 Start live monitoring? (y/n): ").strip().lower()
    if response == 'y':
        print("🚀 Starting live monitoring (Ctrl+C to stop)...")
        play_alert("Live monitoring started")
        
        import time
        last_count = 0
        
        try:
            while True:
                conn = sqlite3.connect("data/bidnet_scraper.db")
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM contracts")
                current_count = cursor.fetchone()[0]
                conn.close()
                
                if current_count != last_count:
                    print(f"🔔 Contract count changed: {last_count} → {current_count}")
                    play_alert(f"New contracts detected: {current_count} total")
                    last_count = current_count
                
                time.sleep(5)  # Check every 5 seconds
                
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped")
            play_alert("Monitoring stopped")

if __name__ == "__main__":
    main()