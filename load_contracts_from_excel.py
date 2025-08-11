#!/usr/bin/env python3
"""
Load 53 Contracts from Excel into SQLite Database
Load the successfully extracted contracts into database for live viewing
"""

import pandas as pd
import sqlite3
import os
import subprocess
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def play_alert(message="Task complete"):
    """Play terminal bell and system notification"""
    print("\\a", end="", flush=True)  # Terminal bell
    try:
        subprocess.run(['osascript', '-e', f'display notification "{message}" with title "Database Loader"'], 
                      capture_output=True, check=False)
    except:
        pass

def load_contracts_to_database():
    """Load the 53 contracts from Excel into SQLite database"""
    logger.info("🚀 Loading 53 contracts from Excel into SQLite database...")
    play_alert("Starting database load")
    
    # Find the Excel file
    excel_file = "/Users/christophernguyen/Documents/hvacscraper/hvac_contracts_full_extraction_1754864773.xlsx"
    
    if not os.path.exists(excel_file):
        logger.error(f"❌ Excel file not found: {excel_file}")
        play_alert("Excel file not found")
        return False
    
    try:
        # Read Excel file
        logger.info(f"📖 Reading Excel file: {excel_file}")
        df = pd.read_excel(excel_file)
        
        logger.info(f"📊 Found {len(df)} contracts in Excel file")
        logger.info(f"📋 Columns: {list(df.columns)}")
        
        # Connect to SQLite database
        db_path = "data/bidnet_scraper.db"
        logger.info(f"🔗 Connecting to database: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create contracts table if it doesn't exist
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS live_contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            agency TEXT,
            location TEXT,
            category TEXT,
            due_date TEXT,
            posted_date TEXT,
            description TEXT,
            bidnet_url TEXT,
            estimated_value TEXT,
            contact_info TEXT,
            contract_type TEXT,
            loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            source_file TEXT
        )
        """
        
        cursor.execute(create_table_sql)
        
        # Clear existing data
        cursor.execute("DELETE FROM live_contracts")
        logger.info("🗑️  Cleared existing contracts from database")
        
        # Insert contracts
        contracts_loaded = 0
        
        for index, row in df.iterrows():
            try:
                # Map Excel columns to database columns (adjust based on actual Excel structure)
                title = str(row.get('Title', '')).strip()
                agency = str(row.get('Agency', '')).strip()
                location = str(row.get('Location', '')).strip()
                category = str(row.get('Category', '')).strip()
                due_date = str(row.get('Due Date', '')).strip()
                posted_date = str(row.get('Posted Date', '')).strip()
                description = str(row.get('Description', '')).strip()
                bidnet_url = str(row.get('BidNet URL', '')).strip()
                estimated_value = str(row.get('Estimated Value', '')).strip()
                contact_info = str(row.get('Contact', '')).strip()
                contract_type = 'HVAC'
                
                # Skip empty rows
                if not title or title.lower() in ['nan', 'none', '']:
                    continue
                
                insert_sql = """
                INSERT INTO live_contracts 
                (title, agency, location, category, due_date, posted_date, description, 
                 bidnet_url, estimated_value, contact_info, contract_type, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                cursor.execute(insert_sql, (
                    title, agency, location, category, due_date, posted_date,
                    description, bidnet_url, estimated_value, contact_info, 
                    contract_type, excel_file
                ))
                
                contracts_loaded += 1
                logger.info(f"✅ Loaded contract {contracts_loaded}: {title[:50]}...")
                
            except Exception as e:
                logger.error(f"❌ Error loading contract {index + 1}: {e}")
                continue
        
        # Commit changes
        conn.commit()
        
        # Verify count
        cursor.execute("SELECT COUNT(*) FROM live_contracts")
        total_count = cursor.fetchone()[0]
        
        conn.close()
        
        logger.info(f"💾 Successfully loaded {contracts_loaded} contracts into database")
        logger.info(f"📊 Database now contains {total_count} total contracts")
        
        play_alert(f"Database loaded: {contracts_loaded} contracts")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error loading contracts: {e}")
        play_alert("Database load failed")
        return False

def verify_database_contents():
    """Verify the database contents"""
    logger.info("🔍 Verifying database contents...")
    
    try:
        conn = sqlite3.connect("data/bidnet_scraper.db")
        cursor = conn.cursor()
        
        # Get count
        cursor.execute("SELECT COUNT(*) FROM live_contracts")
        count = cursor.fetchone()[0]
        
        # Get sample records
        cursor.execute("SELECT title, agency, location, due_date FROM live_contracts LIMIT 5")
        samples = cursor.fetchall()
        
        logger.info(f"📊 Total contracts in database: {count}")
        logger.info("📋 Sample contracts:")
        
        for i, (title, agency, location, due_date) in enumerate(samples, 1):
            logger.info(f"  {i}. {title[:40]}... | {agency} | {location} | {due_date}")
        
        conn.close()
        
        return count
        
    except Exception as e:
        logger.error(f"❌ Error verifying database: {e}")
        return 0

def main():
    """Main loading process"""
    logger.info("🌟 Contract Database Loader Starting...")
    
    success = load_contracts_to_database()
    
    if success:
        count = verify_database_contents()
        logger.info(f"✅ Database loading complete! {count} contracts ready for live viewing")
        play_alert(f"Ready for live viewing: {count} contracts")
    else:
        logger.error("❌ Database loading failed")
        play_alert("Database loading failed")

if __name__ == "__main__":
    main()