#!/usr/bin/env python3
"""
Live Contract Table Viewer - Interactive Real-time Database Browser
View all 53 HVAC contracts with live updates, filtering, and detailed views
"""

import sqlite3
import pandas as pd
import time
import os
import sys
import subprocess
from datetime import datetime
import json
from urllib.parse import urlparse

def clear_screen():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def play_alert(message="Viewer updated"):
    """Play terminal bell and system notification"""
    print("\\a", end="", flush=True)  # Terminal bell
    try:
        subprocess.run(['osascript', '-e', f'display notification "{message}" with title "Contract Viewer"'], 
                      capture_output=True, check=False)
    except:
        pass

def get_all_contracts(db_path="data/bidnet_scraper.db"):
    """Get all contracts from database"""
    try:
        conn = sqlite3.connect(db_path)
        
        query = """
        SELECT 
            id, title, agency, location, category, due_date, 
            bidnet_url, estimated_value, description, loaded_at
        FROM live_contracts 
        ORDER BY id
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        return df
    except Exception as e:
        print(f"❌ Error accessing database: {e}")
        return pd.DataFrame()

def format_currency(value):
    """Format currency value"""
    if pd.isna(value) or value is None or str(value).lower() in ['nan', 'none', '']:
        return "N/A"
    return str(value)

def truncate_text(text, max_length=50):
    """Truncate text to max length"""
    if pd.isna(text) or text is None:
        return "N/A"
    text = str(text).strip()
    if len(text) > max_length:
        return text[:max_length-3] + "..."
    return text

def get_domain(url):
    """Extract domain from URL"""
    if pd.isna(url) or not url:
        return "N/A"
    try:
        parsed = urlparse(str(url))
        return parsed.netloc or "N/A"
    except:
        return "N/A"

def display_contracts_table(df, start_index=0, page_size=10):
    """Display contracts in a formatted table"""
    clear_screen()
    
    print("🏢 LIVE HVAC CONTRACT DATABASE VIEWER")
    print("=" * 100)
    print(f"📊 Total Contracts: {len(df)}")
    print(f"🕐 Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📄 Showing {start_index + 1}-{min(start_index + page_size, len(df))} of {len(df)} contracts")
    print("=" * 100)
    
    if df.empty:
        print("📭 No contracts found in database")
        return
    
    # Get page slice
    end_index = min(start_index + page_size, len(df))
    page_df = df.iloc[start_index:end_index]
    
    # Display contracts
    for idx, row in page_df.iterrows():
        print(f"\\n📋 Contract #{row['id']:2d}")
        print(f"   📝 Title:    {truncate_text(row['title'], 70)}")
        print(f"   🏛️  Agency:   {truncate_text(row['agency'], 50)}")
        print(f"   📍 Location: {truncate_text(row['location'], 40)}")
        print(f"   💰 Value:    {format_currency(row['estimated_value'])}")
        print(f"   📅 Due Date: {truncate_text(row['due_date'], 30)}")
        print(f"   🔗 URL:      {get_domain(row['bidnet_url'])}")
        print(f"   📄 Desc:     {truncate_text(row['description'], 80)}")
        print("-" * 100)
    
    print(f"\\n🎮 CONTROLS:")
    print(f"   [Enter] Next page | [p] Previous page | [q] Quit")
    print(f"   [s] Search | [f] Filter | [d] Details | [r] Refresh")
    print(f"   [1-{page_size}] View contract details")

def search_contracts(df, search_term):
    """Search contracts by title, agency, or description"""
    search_term = search_term.lower()
    
    mask = (
        df['title'].astype(str).str.lower().str.contains(search_term, na=False) |
        df['agency'].astype(str).str.lower().str.contains(search_term, na=False) |
        df['description'].astype(str).str.lower().str.contains(search_term, na=False) |
        df['location'].astype(str).str.lower().str.contains(search_term, na=False)
    )
    
    return df[mask]

def show_contract_details(df, contract_id):
    """Show detailed view of a single contract"""
    clear_screen()
    
    contract = df[df['id'] == contract_id]
    if contract.empty:
        print(f"❌ Contract #{contract_id} not found")
        return
    
    row = contract.iloc[0]
    
    print("🏢 CONTRACT DETAILS")
    print("=" * 80)
    print(f"ID: {row['id']}")
    print(f"Title: {row['title']}")
    print(f"Agency: {row['agency']}")
    print(f"Location: {row['location']}")
    print(f"Category: {row['category']}")
    print(f"Due Date: {row['due_date']}")
    print(f"Estimated Value: {row['estimated_value']}")
    print(f"BidNet URL: {row['bidnet_url']}")
    print(f"Loaded At: {row['loaded_at']}")
    print("\\nDescription:")
    print("-" * 40)
    print(row['description'])
    print("=" * 80)
    print("\\n[Enter] Back to table | [o] Open URL | [q] Quit")

def get_database_stats(db_path="data/bidnet_scraper.db"):
    """Get database statistics"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get counts by type
        cursor.execute("SELECT COUNT(*) FROM live_contracts")
        total_count = cursor.fetchone()[0]
        
        # Get recent additions
        cursor.execute("SELECT COUNT(*) FROM live_contracts WHERE date(loaded_at) = date('now')")
        today_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_contracts': total_count,
            'added_today': today_count
        }
    except:
        return {'total_contracts': 0, 'added_today': 0}

def interactive_viewer():
    """Main interactive viewer loop"""
    print("🚀 Starting Live Contract Table Viewer...")
    play_alert("Contract viewer starting")
    
    current_index = 0
    page_size = 10
    current_df = None
    search_mode = False
    search_term = ""
    
    try:
        while True:
            # Refresh data
            df = get_all_contracts()
            
            if search_mode and search_term:
                df = search_contracts(df, search_term)
                current_df = df
            else:
                current_df = df
                search_mode = False
            
            # Display table
            display_contracts_table(current_df, current_index, page_size)
            
            if search_mode:
                print(f"🔍 Search active: '{search_term}' ({len(current_df)} results)")
            
            # Get user input
            try:
                user_input = input("\\n> ").strip().lower()
            except KeyboardInterrupt:
                break
            
            # Handle commands
            if user_input == 'q':
                break
            elif user_input == '' or user_input == 'n':  # Next page
                if current_index + page_size < len(current_df):
                    current_index += page_size
                else:
                    print("\\a📄 Already at last page")
                    time.sleep(1)
            elif user_input == 'p':  # Previous page
                if current_index >= page_size:
                    current_index -= page_size
                else:
                    current_index = 0
            elif user_input == 'r':  # Refresh
                print("\\a🔄 Refreshing data...")
                play_alert("Data refreshed")
                time.sleep(0.5)
            elif user_input == 's':  # Search
                try:
                    search_term = input("🔍 Enter search term: ").strip()
                    if search_term:
                        search_mode = True
                        current_index = 0
                        print(f"\\a🔍 Searching for '{search_term}'...")
                        time.sleep(0.5)
                    else:
                        search_mode = False
                except:
                    pass
            elif user_input == 'f':  # Clear filter
                search_mode = False
                search_term = ""
                current_index = 0
                print("\\a🗑️ Filter cleared")
                time.sleep(0.5)
            elif user_input.isdigit():  # View contract details
                contract_num = int(user_input)
                if 1 <= contract_num <= min(page_size, len(current_df) - current_index):
                    contract_idx = current_index + contract_num - 1
                    if contract_idx < len(current_df):
                        contract_id = current_df.iloc[contract_idx]['id']
                        show_contract_details(current_df, contract_id)
                        input()  # Wait for user
                else:
                    print(f"\\a❌ Invalid contract number: {contract_num}")
                    time.sleep(1)
            elif user_input == 'd':  # Database stats
                stats = get_database_stats()
                print(f"\\n📊 Database Stats:")
                print(f"   Total contracts: {stats['total_contracts']}")
                print(f"   Added today: {stats['added_today']}")
                input("\\n[Enter] to continue...")
            
    except KeyboardInterrupt:
        pass
    finally:
        clear_screen()
        print("👋 Live Contract Viewer closed")
        play_alert("Contract viewer closed")

def main():
    """Main function"""
    print("🌟 Live HVAC Contract Table Viewer Starting...")
    
    # Check if database exists
    db_path = "data/bidnet_scraper.db"
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        print("💡 Run load_contracts_from_excel.py first to load contracts")
        return
    
    interactive_viewer()

if __name__ == "__main__":
    main()