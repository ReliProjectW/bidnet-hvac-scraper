#!/usr/bin/env python3
"""
Export Contracts to Clean Excel File
Create a user-friendly Excel file with all 53 contracts
"""

import sqlite3
import pandas as pd
import subprocess
from datetime import datetime
import re

def play_alert(message="Excel export complete"):
    """Play terminal bell and system notification"""
    print("\\a", end="", flush=True)
    try:
        subprocess.run(['osascript', '-e', f'display notification "{message}" with title "Excel Export"'], 
                      capture_output=True, check=False)
    except:
        pass

def clean_text(text):
    """Clean text for Excel display"""
    if pd.isna(text) or text is None:
        return ""
    
    text = str(text).strip()
    
    # Remove excessive newlines and whitespace
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    
    return text

def extract_agency_name(agency_text):
    """Extract clean agency name from the full text"""
    if pd.isna(agency_text) or not agency_text:
        return "Unknown Agency"
    
    text = str(agency_text).strip()
    
    # Split by newlines and take first non-empty line
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if lines:
        # Take the first substantial line (usually the agency name)
        for line in lines:
            if len(line) > 3 and not line.lower().startswith('state'):
                return line
        return lines[0]
    
    return text

def extract_description(full_text):
    """Extract description from full text"""
    if pd.isna(full_text) or not full_text:
        return ""
    
    text = str(full_text).strip()
    
    # Look for description patterns
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Find substantial content lines
    description_parts = []
    for line in lines:
        if len(line) > 20 and not any(skip in line.lower() for skip in ['state & local bids', 'federal bids', 'california federal']):
            description_parts.append(line)
            if len(description_parts) >= 2:  # Limit to first 2 substantial lines
                break
    
    return ' '.join(description_parts)

def create_excel_export():
    """Create a clean Excel file with all contracts"""
    print("🚀 Creating clean Excel export of all 53 contracts...")
    play_alert("Starting Excel export")
    
    try:
        # Connect to database
        conn = sqlite3.connect("data/bidnet_scraper.db")
        
        query = """
        SELECT 
            id, title, agency, location, category, due_date, 
            bidnet_url, estimated_value, description, loaded_at
        FROM live_contracts 
        ORDER BY id
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        print(f"📊 Processing {len(df)} contracts for Excel export...")
        
        # Create clean DataFrame for Excel
        excel_data = []
        
        for idx, row in df.iterrows():
            # Clean and extract data
            contract_id = row['id']
            title = clean_text(row['title'])
            agency = extract_agency_name(row['agency'])
            location = clean_text(row['location']) if clean_text(row['location']) != "Unknown location" else ""
            due_date = clean_text(row['due_date'])
            estimated_value = clean_text(row['estimated_value'])
            bidnet_url = clean_text(row['bidnet_url'])
            description = extract_description(row['agency'])  # Use agency field which has more description
            
            # Determine contract type based on title
            contract_type = "HVAC"
            if "hvac" in title.lower():
                contract_type = "HVAC System"
            elif "air conditioning" in title.lower():
                contract_type = "Air Conditioning"
            elif "heating" in title.lower():
                contract_type = "Heating"
            elif "ventilation" in title.lower():
                contract_type = "Ventilation"
            
            excel_data.append({
                'ID': contract_id,
                'Title': title,
                'Agency': agency,
                'Location': location,
                'Contract Type': contract_type,
                'Due Date': due_date,
                'Estimated Value': estimated_value,
                'Description': description,
                'BidNet URL': bidnet_url,
                'Loaded Date': row['loaded_at']
            })
        
        # Create DataFrame
        excel_df = pd.DataFrame(excel_data)
        
        # Create Excel file with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_file = f"/Users/christophernguyen/Documents/hvacscraper/hvac_contracts_clean_{timestamp}.xlsx"
        
        # Write to Excel with formatting
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            excel_df.to_excel(writer, sheet_name='HVAC Contracts', index=False)
            
            # Get workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['HVAC Contracts']
            
            # Adjust column widths
            column_widths = {
                'A': 8,   # ID
                'B': 60,  # Title
                'C': 30,  # Agency
                'D': 20,  # Location
                'E': 15,  # Contract Type
                'F': 15,  # Due Date
                'G': 15,  # Estimated Value
                'H': 50,  # Description
                'I': 40,  # BidNet URL
                'J': 20   # Loaded Date
            }
            
            for col, width in column_widths.items():
                worksheet.column_dimensions[col].width = width
            
            # Set header row formatting
            header_row = worksheet[1]
            for cell in header_row:
                cell.font = cell.font.copy(bold=True)
                cell.fill = cell.fill.copy(start_color="366092", end_color="366092", fill_type="solid")
                cell.font = cell.font.copy(color="FFFFFF")
        
        print(f"✅ Excel file created successfully!")
        print(f"📁 Location: {excel_file}")
        print(f"📊 Contains: {len(excel_df)} contracts")
        
        # Create summary sheet
        print("📋 Creating summary statistics...")
        
        # Summary data
        summary_data = {
            'Statistic': [
                'Total Contracts',
                'Unique Agencies',
                'Contracts with Due Dates',
                'Contracts with Locations',
                'Contracts with URLs',
                'Export Date',
                'Database File'
            ],
            'Value': [
                len(excel_df),
                excel_df['Agency'].nunique(),
                len(excel_df[excel_df['Due Date'] != '']),
                len(excel_df[excel_df['Location'] != '']),
                len(excel_df[excel_df['BidNet URL'] != '']),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'bidnet_scraper.db'
            ]
        }
        
        summary_df = pd.DataFrame(summary_data)
        
        # Add summary to Excel file
        with pd.ExcelWriter(excel_file, engine='openpyxl', mode='a') as writer:
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Format summary sheet
            worksheet = writer.sheets['Summary']
            worksheet.column_dimensions['A'].width = 25
            worksheet.column_dimensions['B'].width = 30
            
            # Header formatting
            header_row = worksheet[1]
            for cell in header_row:
                cell.font = cell.font.copy(bold=True)
        
        print(f"📊 Added summary statistics sheet")
        play_alert(f"Excel export complete: {len(excel_df)} contracts")
        
        return excel_file
        
    except Exception as e:
        print(f"❌ Error creating Excel file: {e}")
        play_alert("Excel export failed")
        return None

def main():
    """Main export function"""
    print("🌟 HVAC Contracts Excel Export Tool")
    
    # Check database
    try:
        conn = sqlite3.connect("data/bidnet_scraper.db")
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM live_contracts")
        count = cursor.fetchone()[0]
        conn.close()
        
        if count == 0:
            print("❌ No contracts found in database")
            return
            
    except Exception as e:
        print(f"❌ Database error: {e}")
        return
    
    # Create Excel export
    excel_file = create_excel_export()
    
    if excel_file:
        print("\\n✅ Excel export complete!")
        print(f"📁 File: {excel_file}")
        print("💡 You can now open this file in Excel for easy viewing and filtering")
    else:
        print("❌ Excel export failed")

if __name__ == "__main__":
    main()