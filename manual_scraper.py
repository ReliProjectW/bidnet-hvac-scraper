#!/usr/bin/env python3
"""
Manual BidNet Contract Scraper
Use this after manually navigating to BidNet search results
"""

import sys
import time
from pathlib import Path
import pandas as pd
from datetime import datetime

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from config import Config
import re

def setup_browser():
    """Set up browser"""
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1920,1080")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(3)
    
    return driver

def extract_contract_from_row(row_element):
    """Extract contract data from a table row"""
    try:
        row_text = row_element.get_text(strip=True)
        
        contract = {
            'raw_text': row_text[:500],
            'raw_html': str(row_element)[:800]
        }
        
        # Extract title - look for links or strong text
        title_element = row_element.find(['a', 'strong', 'b']) or row_element.find('td')
        if title_element:
            title = title_element.get_text(strip=True)
            contract['title'] = title if len(title) > 10 else row_text.split('\n')[0]
        else:
            contract['title'] = row_text.split('\n')[0] if row_text else 'No title'
        
        # Extract all links
        links = row_element.find_all('a', href=True)
        if links:
            # Prefer solicitation/opportunity links
            best_link = None
            for link in links:
                href = link.get('href', '')
                if any(term in href.lower() for term in ['solicitation', 'opportunity', 'bid']):
                    best_link = href
                    break
            
            if not best_link:
                best_link = links[0].get('href', '')
                
            if best_link and not best_link.startswith('http'):
                if best_link.startswith('/'):
                    best_link = 'https://www.bidnetdirect.com' + best_link
                    
            contract['url'] = best_link
            contract['link_text'] = links[0].get_text(strip=True)
        else:
            contract['url'] = None
            contract['link_text'] = None
        
        # Extract dates
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{1,2}-\d{1,2}-\d{4}',
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4}'
        ]
        
        found_dates = []
        for pattern in date_patterns:
            dates = re.findall(pattern, row_text, re.IGNORECASE)
            found_dates.extend(dates)
        
        contract['dates'] = ' | '.join(found_dates[:3]) if found_dates else 'No dates'
        
        # Extract dollar amounts
        amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', row_text)
        contract['estimated_value'] = amounts[0] if amounts else 'Not specified'
        
        # Extract agency/location info from table cells
        cells = row_element.find_all(['td', 'th'])
        if len(cells) >= 2:
            contract['agency'] = cells[1].get_text(strip=True) if len(cells) > 1 else 'Unknown'
            contract['location'] = cells[2].get_text(strip=True) if len(cells) > 2 else 'Unknown'
        else:
            # Try to find agency patterns in text
            agency_patterns = [
                r'(?i)(city of|county of|school district)[\w\s]+',
                r'(?i)(university of)[\w\s]+',
            ]
            agency = 'Unknown'
            for pattern in agency_patterns:
                matches = re.findall(pattern, row_text)
                if matches:
                    agency = matches[0]
                    break
            contract['agency'] = agency
            contract['location'] = 'Unknown'
        
        # Calculate HVAC relevance
        hvac_terms = ['hvac', 'heat pump', 'air conditioning', 'heating', 'ventilation', 'mini-split', 'furnace', 'air handler']
        hvac_score = sum(1 for term in hvac_terms if term in row_text.lower())
        contract['hvac_relevance_score'] = hvac_score
        
        # Flag negative terms
        negative_terms = ['maintenance', 'service', 'repair', 'geothermal']
        has_negative = any(term in row_text.lower() for term in negative_terms)
        contract['has_negative_terms'] = has_negative
        
        return contract
        
    except Exception as e:
        print(f"Error extracting contract: {e}")
        return None

def main():
    """Main manual scraper"""
    print("🔧 Manual BidNet Contract Scraper")
    print("=" * 50)
    print("\nInstructions:")
    print("1. Browser will open")
    print("2. Navigate to BidNet and log in")
    print("3. Search for HVAC contracts")
    print("4. Get to a page with contract results in a table")
    print("5. Come back here and press ENTER")
    print("6. I'll scrape whatever is currently on the page!")
    
    driver = setup_browser()
    
    try:
        input("\n🚀 Navigate to BidNet search results, then press ENTER...")
        
        current_url = driver.current_url
        print(f"\n🔍 Scraping page: {current_url}")
        
        # Get page source
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Look for contract table rows using patterns found by inspector
        selectors_to_try = [
            'tr.mets-table-row.odd',
            'tr.even.mets-table-row',
            'tr[class*="mets-table-row"]',
            'tbody tr',
            'table tr'
        ]
        
        contracts = []
        rows_found = 0
        
        for selector in selectors_to_try:
            try:
                elements = soup.select(selector)
                if elements and len(elements) > 1:  # Need multiple rows
                    print(f"✅ Found {len(elements)} rows using: {selector}")
                    
                    for i, row in enumerate(elements):
                        # Skip header rows or empty rows
                        if row.find(['th']) or len(row.get_text(strip=True)) < 20:
                            continue
                            
                        contract = extract_contract_from_row(row)
                        if contract:
                            contract['row_index'] = i
                            contract['selector_used'] = selector
                            contracts.append(contract)
                    
                    rows_found = len(elements)
                    break
                    
            except Exception as e:
                print(f"❌ Selector {selector} failed: {e}")
                continue
        
        if not contracts:
            print("⚠️  No contract rows found. Let me try a different approach...")
            
            # Fallback: look for any rows with HVAC content
            all_rows = soup.find_all(['tr', 'div'])
            hvac_rows = []
            
            for row in all_rows:
                text = row.get_text().lower()
                if any(term in text for term in ['hvac', 'heating', 'air conditioning', 'heat pump']):
                    hvac_rows.append(row)
            
            if hvac_rows:
                print(f"🎯 Found {len(hvac_rows)} elements with HVAC content")
                for i, row in enumerate(hvac_rows[:10]):  # Limit to 10
                    contract = extract_contract_from_row(row)
                    if contract:
                        contract['row_index'] = i
                        contract['selector_used'] = 'hvac_content_fallback'
                        contracts.append(contract)
        
        if contracts:
            print(f"\n📊 EXTRACTED {len(contracts)} CONTRACTS")
            
            # Filter for HVAC relevance
            hvac_contracts = [c for c in contracts if c['hvac_relevance_score'] > 0 and not c['has_negative_terms']]
            
            print(f"🎯 {len(hvac_contracts)} relevant HVAC contracts after filtering")
            
            # Save to Excel
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"manual_scrape_{timestamp}.xlsx"
            filepath = f"data/processed/{filename}"
            
            # Prepare data for Excel
            excel_data = []
            for contract in contracts:
                excel_data.append({
                    'Title': contract['title'],
                    'Agency': contract['agency'],
                    'Location': contract['location'],
                    'Dates': contract['dates'],
                    'Estimated_Value': contract['estimated_value'],
                    'URL': contract['url'],
                    'Link_Text': contract['link_text'],
                    'HVAC_Relevance_Score': contract['hvac_relevance_score'],
                    'Has_Negative_Terms': contract['has_negative_terms'],
                    'Selector_Used': contract['selector_used'],
                    'Row_Index': contract['row_index'],
                    'Raw_Text': contract['raw_text']
                })
            
            df = pd.DataFrame(excel_data)
            df.to_excel(filepath, index=False)
            
            print(f"\n💾 Results saved to: {filepath}")
            
            # Show sample results
            print(f"\n📋 SAMPLE CONTRACTS:")
            for i, contract in enumerate(contracts[:5]):
                print(f"\n{i+1}. {contract['title'][:80]}")
                print(f"   Agency: {contract['agency']}")
                print(f"   HVAC Score: {contract['hvac_relevance_score']}")
                print(f"   URL: {contract['url']}")
                
            # Open Excel file
            import subprocess
            subprocess.run(['open', filepath])
            print(f"\n🎉 Excel file opened automatically!")
            
        else:
            print("❌ No contracts found. The page might not have the expected structure.")
            
            # Save page source for debugging
            debug_file = f"data/debug_manual_scrape_{datetime.now().strftime('%H%M%S')}.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(page_source)
            print(f"💾 Page source saved to: {debug_file}")
        
    except KeyboardInterrupt:
        print("\n⏹️ Scraping stopped")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()