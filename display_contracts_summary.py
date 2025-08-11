#!/usr/bin/env python3
"""
Display Contracts Summary - Show all 53 contracts in a readable format
"""

import sqlite3
import pandas as pd
import subprocess
from datetime import datetime

def play_alert(message="Summary complete"):
    """Play terminal bell and system notification"""
    print("\\a", end="", flush=True)
    try:
        subprocess.run(['osascript', '-e', f'display notification "{message}" with title "Contract Summary"'], 
                      capture_output=True, check=False)
    except:
        pass

def display_all_contracts():
    """Display all 53 contracts in a summary format"""
    print("🚀 Loading all HVAC contracts from database...")
    play_alert("Loading contracts")
    
    try:
        conn = sqlite3.connect("data/bidnet_scraper.db")
        
        query = """
        SELECT 
            id, title, agency, location, due_date, bidnet_url, estimated_value
        FROM live_contracts 
        ORDER BY id
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        print("\\n🏢 HVAC CONTRACTS DATABASE SUMMARY")
        print("=" * 100)
        print(f"📊 Total Contracts: {len(df)}")
        print(f"🕐 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 100)
        
        for idx, row in df.iterrows():
            # Clean up title and agency
            title = str(row['title']).strip() if pd.notna(row['title']) else "Unknown Title"
            agency = str(row['agency']).strip() if pd.notna(row['agency']) else "Unknown Agency"
            location = str(row['location']).strip() if pd.notna(row['location']) else "Unknown Location"
            due_date = str(row['due_date']).strip() if pd.notna(row['due_date']) else "N/A"
            
            # Extract clean agency name (first line usually)
            if '\\n' in agency:
                agency_clean = agency.split('\\n')[0].strip()
            else:
                agency_clean = agency
            
            print(f"\\n📋 Contract {row['id']:2d}/53")
            print(f"   📝 {title[:70]}")
            print(f"   🏛️  {agency_clean[:50]}")
            print(f"   📍 {location}")
            print(f"   📅 Due: {due_date}")
            
            if pd.notna(row['bidnet_url']) and str(row['bidnet_url']).strip():
                print(f"   🔗 {row['bidnet_url']}")
            
            print("-" * 80)
        
        print(f"\\n✅ Successfully displayed all {len(df)} HVAC contracts!")
        play_alert(f"Summary complete: {len(df)} contracts")
        
        # Save summary to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        summary_file = f"/Users/christophernguyen/Documents/hvacscraper/contracts_summary_{timestamp}.txt"
        
        with open(summary_file, 'w') as f:
            f.write(f"HVAC CONTRACTS DATABASE SUMMARY\\n")
            f.write(f"Generated: {datetime.now()}\\n")
            f.write(f"Total Contracts: {len(df)}\\n")
            f.write("=" * 80 + "\\n\\n")
            
            for idx, row in df.iterrows():
                title = str(row['title']).strip() if pd.notna(row['title']) else "Unknown Title"
                agency = str(row['agency']).strip() if pd.notna(row['agency']) else "Unknown Agency"
                location = str(row['location']).strip() if pd.notna(row['location']) else "Unknown Location"
                
                # Clean agency name
                if '\\n' in agency:
                    agency_clean = agency.split('\\n')[0].strip()
                else:
                    agency_clean = agency
                
                f.write(f"Contract {row['id']:2d}: {title}\\n")
                f.write(f"  Agency: {agency_clean}\\n")
                f.write(f"  Location: {location}\\n")
                if pd.notna(row['bidnet_url']):
                    f.write(f"  URL: {row['bidnet_url']}\\n")
                f.write("\\n")
        
        print(f"📁 Summary saved to: {summary_file}")
        
    except Exception as e:
        print(f"❌ Error displaying contracts: {e}")
        play_alert("Error displaying contracts")

def get_database_statistics():
    """Show database statistics"""
    try:
        conn = sqlite3.connect("data/bidnet_scraper.db")
        cursor = conn.cursor()
        
        # Basic stats
        cursor.execute("SELECT COUNT(*) FROM live_contracts")
        total_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM live_contracts WHERE title LIKE '%HVAC%'")
        hvac_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT agency) FROM live_contracts WHERE agency IS NOT NULL AND agency != 'Unknown Agency'")
        unique_agencies = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT location) FROM live_contracts WHERE location IS NOT NULL AND location != 'Unknown Location'")
        unique_locations = cursor.fetchone()[0]
        
        conn.close()
        
        print("\\n📊 DATABASE STATISTICS")
        print("-" * 40)
        print(f"Total Contracts: {total_count}")
        print(f"HVAC-specific: {hvac_count}")
        print(f"Unique Agencies: {unique_agencies}")
        print(f"Unique Locations: {unique_locations}")
        
    except Exception as e:
        print(f"❌ Error getting statistics: {e}")

def main():
    """Main display function"""
    print("🌟 HVAC Contract Database Summary Generator")
    
    # Check database exists
    try:
        conn = sqlite3.connect("data/bidnet_scraper.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM live_contracts")
        count = cursor.fetchone()[0]
        conn.close()
        
        if count == 0:
            print("❌ No contracts found in database")
            print("💡 Run load_contracts_from_excel.py first")
            return
            
    except Exception as e:
        print(f"❌ Database error: {e}")
        return
    
    # Display contracts and stats
    display_all_contracts()
    get_database_statistics()
    
    print("\\n✅ Contract summary complete!")

if __name__ == "__main__":
    main()