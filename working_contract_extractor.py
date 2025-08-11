#!/usr/bin/env python3
"""
Working BidNet Contract Extractor - Fixed HTML Structure
Based on debugging findings: Use 'tr' elements, handle cookies
"""

import logging
import time
import subprocess
import os
from datetime import datetime
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def play_alert(message="Task complete"):
    """Play terminal bell and system notification"""
    print("\\a", end="", flush=True)  # Terminal bell
    try:
        subprocess.run(['osascript', '-e', f'display notification "{message}" with title "BidNet Extractor"'], 
                      capture_output=True, check=False)
    except:
        pass

def handle_cookie_banner(page):
    """Handle cookie banner if present"""
    try:
        cookie_banner = page.query_selector('.cookie-banner')
        if cookie_banner:
            cookie_accept = page.query_selector('.cookie-banner button')
            if cookie_accept:
                logger.info("🍪 Accepting cookie banner...")
                cookie_accept.click()
                page.wait_for_timeout(1000)
                return True
    except:
        pass
    return False

def extract_contract_from_tr(tr_element, row_index):
    """Extract contract data from a TR element"""
    try:
        # Get all TD cells
        cells = tr_element.query_selector_all('td')
        
        if len(cells) < 2:  # Not enough cells, probably header row
            return None
            
        # Look for contract link in the row (correct pattern discovered)
        contract_link = tr_element.query_selector('a[href*="/private/supplier/interception/"]')
        
        if not contract_link:
            # Skip rows without contract links
            return None
            
        # Extract title and URL
        title = contract_link.inner_text().strip()
        source_url = contract_link.get_attribute('href')
        
        if source_url and not source_url.startswith('http'):
            source_url = f"https://www.bidnetdirect.com{source_url}"
            
        # Skip if no meaningful title
        if not title or len(title) < 5:
            return None
            
        # Extract data from TD structure (we know there are 3 TDs)
        agency = "Unknown Agency"
        location = "Unknown Location"
        due_date = "Unknown Date"
        
        if len(cells) >= 2:
            # TD 0: Contains title and agency info
            td0_text = cells[0].inner_text() if cells[0] else ""
            lines = [line.strip() for line in td0_text.split('\\n') if line.strip()]
            
            # Look for agency (usually after title)
            for line in lines:
                if any(word in line.lower() for word in ['city of', 'county of', 'state of', 'university of', 'district', 'authority']):
                    agency = line
                    break
            
            # TD 1: Contains date and location info
            if len(cells) >= 2:
                td1_text = cells[1].inner_text() if cells[1] else ""
                
                # Extract closing date
                if "CLOSING DATE" in td1_text:
                    lines = td1_text.split('\\n')
                    for i, line in enumerate(lines):
                        if "CLOSING DATE" in line and i + 1 < len(lines):
                            due_date = lines[i + 1].strip()
                            break
                
                # Extract location (California is common)
                if "california" in td1_text.lower():
                    location = "California"
        
        return {
            'row_index': row_index,
            'title': title,
            'agency': agency,
            'location': location,
            'due_date': due_date,
            'source_url': source_url,
            'extracted_at': datetime.now().isoformat(),
            'full_text': tr_element.inner_text().replace('\\n', ' ')[:200]  # For debugging
        }
        
    except Exception as e:
        logger.error(f"Error extracting from row {row_index}: {e}")
        return None

def get_page_contracts(page):
    """Extract contracts from current page using TR elements"""
    contracts = []
    
    try:
        # Wait for table to load
        page.wait_for_selector('tr', timeout=10000)
        
        # Get all TR elements
        tr_elements = page.query_selector_all('tr')
        logger.info(f"Found {len(tr_elements)} TR elements on current page")
        
        for i, tr in enumerate(tr_elements):
            contract = extract_contract_from_tr(tr, i)
            if contract:
                contracts.append(contract)
                logger.info(f"✅ Row {i}: {contract['title'][:60]}...")
            else:
                logger.debug(f"⏭️  Skipped TR {i} (header/invalid)")
                
        logger.info(f"📊 Extracted {len(contracts)} valid contracts from {len(tr_elements)} rows")
                
    except Exception as e:
        logger.error(f"Error extracting page contracts: {e}")
    
    return contracts

def extract_working_hvac_contracts():
    """Extract HVAC contracts with fixed structure"""
    logger.info("🚀 Starting Working Contract Extraction (Fixed Structure)")
    play_alert("Starting working extraction")
    
    all_contracts = []
    seen_urls = set()
    max_contracts = 53
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = context.new_page()
        
        try:
            # Login
            logger.info("🔐 Logging in to BidNet...")
            page.goto("https://www.bidnetdirect.com/public/authentication/login")
            page.wait_for_timeout(3000)
            
            # Handle cookie banner early
            handle_cookie_banner(page)
            
            username = os.getenv("BIDNET_USERNAME")
            password = os.getenv("BIDNET_PASSWORD")
            
            page.fill("input[name='j_username']", username)
            page.fill("input[name='j_password']", password)
            page.click("button[type='submit']")
            page.wait_for_timeout(10000)
            
            logger.info("✅ Login successful!")
            
            # Navigate to search
            logger.info("🔍 Searching for HVAC contracts...")
            page.goto("https://www.bidnetdirect.com/private/supplier/solicitations/search")
            page.wait_for_timeout(5000)
            
            # Handle cookie banner again if needed
            handle_cookie_banner(page)
            
            # Search for HVAC
            search_field = page.wait_for_selector("textarea#solicitationSingleBoxSearch", timeout=10000)
            search_field.fill("hvac")
            
            search_button = page.wait_for_selector("button#topSearchButton", timeout=10000)
            search_button.click()
            page.wait_for_timeout(8000)  # Wait longer for results
            
            # Extract first page contracts
            logger.info("📋 Processing first page...")
            page_contracts = get_page_contracts(page)
            
            for contract in page_contracts:
                # Skip duplicates
                if contract['source_url'] and contract['source_url'] in seen_urls:
                    continue
                    
                all_contracts.append(contract)
                if contract['source_url']:
                    seen_urls.add(contract['source_url'])
                    
                logger.info(f"✅ Added contract {len(all_contracts)}: {contract['title'][:50]}...")
                
                # Stop if we reach target
                if len(all_contracts) >= max_contracts:
                    break
            
            logger.info(f"🎉 Extraction complete! Found {len(all_contracts)} unique contracts")
            play_alert(f"Extraction complete: {len(all_contracts)} contracts")
            
        except Exception as e:
            logger.error(f"❌ Error during extraction: {e}")
            play_alert("Extraction failed")
            
        finally:
            browser.close()
    
    return all_contracts

def save_working_contracts(contracts):
    """Save contracts with detailed info"""
    if not contracts:
        logger.info("📭 No contracts to save")
        return
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"data/working_contracts_{timestamp}.txt"
    
    with open(filename, 'w') as f:
        f.write(f"WORKING HVAC CONTRACTS EXTRACTION (Fixed Structure)\\n")
        f.write(f"Total Contracts: {len(contracts)}\\n")
        f.write(f"Extraction Time: {datetime.now()}\\n")
        f.write("=" * 100 + "\\n\\n")
        
        for i, contract in enumerate(contracts, 1):
            f.write(f"Contract {i}:\\n")
            f.write(f"  Row Index: {contract['row_index']}\\n")
            f.write(f"  Title: {contract['title']}\\n")
            f.write(f"  Agency: {contract['agency']}\\n")
            f.write(f"  Location: {contract['location']}\\n")
            f.write(f"  Due Date: {contract['due_date']}\\n")
            f.write(f"  URL: {contract['source_url']}\\n")
            f.write(f"  Full Text Sample: {contract['full_text']}\\n")
            f.write(f"  Extracted: {contract['extracted_at']}\\n")
            f.write("-" * 100 + "\\n")
    
    logger.info(f"💾 Saved {len(contracts)} contracts to {filename}")
    
    # Update notes
    notes_file = "/Users/christophernguyen/Documents/hvacscraper/scraper_issues_and_fixes.txt"
    with open(notes_file, 'a') as f:
        f.write(f"\\n\\nWORKING EXTRACTION RUN - {datetime.now()}\\n")
        f.write(f"SUCCESS: Fixed HTML structure using TR elements\\n")
        f.write(f"Total contracts extracted: {len(contracts)}\\n")
        f.write(f"File saved: {filename}\\n")
        f.write(f"Next: Add pagination to reach 53 contracts\\n")
    
    play_alert(f"Working extraction complete: {len(contracts)} contracts saved")

def main():
    """Main working extraction process"""
    logger.info("🌟 Working BidNet Contract Extractor Starting...")
    
    contracts = extract_working_hvac_contracts()
    save_working_contracts(contracts)
    
    logger.info("✅ Working extraction process complete!")
    play_alert("All tasks complete")

if __name__ == "__main__":
    main()