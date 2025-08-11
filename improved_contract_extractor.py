#!/usr/bin/env python3
"""
Improved BidNet Contract Extractor
Fixes: Data extraction, pagination, duplicates
"""

import logging
import time
import subprocess
import os
from datetime import datetime
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from bs4 import BeautifulSoup

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

def extract_contract_from_row(row_element, page):
    """Extract actual contract data from a table row"""
    try:
        # Get all cells in the row
        cells = row_element.query_selector_all('.table-cell')
        
        if len(cells) < 3:  # Not enough cells, probably header or invalid row
            return None
            
        # Extract title and URL from first cell (usually contains the link)
        title_cell = cells[0] if cells else None
        title_link = title_cell.query_selector('a') if title_cell else None
        
        if not title_link:
            # Try alternative selectors
            title_link = row_element.query_selector('a[href*="/private/solicitation/"]')
        
        if title_link:
            title = title_link.inner_text().strip()
            source_url = title_link.get_attribute('href')
            if source_url and not source_url.startswith('http'):
                source_url = f"https://www.bidnetdirect.com{source_url}"
        else:
            # If no link found, try to get text from first cell
            title = title_cell.inner_text().strip() if title_cell else "Unknown Title"
            source_url = None
        
        # Skip invalid entries
        if not title or title.lower() in ['no results match your criteria', 'no title found', '', 'unknown title']:
            return None
            
        # Extract other details from remaining cells
        agency = cells[1].inner_text().strip() if len(cells) > 1 else "Unknown Agency"
        location = cells[2].inner_text().strip() if len(cells) > 2 else "Unknown Location"
        due_date = cells[3].inner_text().strip() if len(cells) > 3 else "Unknown Date"
        
        # Clean up extracted data
        if agency.lower() in ['no agency found', '', 'unknown']:
            agency = "Unknown Agency"
        if location.lower() in ['no location found', '', 'unknown']:
            location = "Unknown Location"
            
        return {
            'title': title,
            'agency': agency,
            'location': location,
            'due_date': due_date,
            'source_url': source_url,
            'extracted_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error extracting contract data: {e}")
        return None

def get_page_contracts(page):
    """Extract contracts from current page"""
    contracts = []
    
    try:
        # Wait for results to load
        page.wait_for_selector('[class*="table-row"]', timeout=10000)
        
        # Get all result rows (excluding header)
        rows = page.query_selector_all('[class*="table-row"]:not(.table-header)')
        logger.info(f"Found {len(rows)} rows on current page")
        
        for i, row in enumerate(rows):
            contract = extract_contract_from_row(row, page)
            if contract:
                contracts.append(contract)
                logger.info(f"✅ Page contract {i+1}: {contract['title'][:50]}...")
            else:
                logger.info(f"⏭️  Skipped invalid row {i+1}")
                
    except Exception as e:
        logger.error(f"Error extracting page contracts: {e}")
    
    return contracts

def has_next_page(page):
    """Check if there's a next page available"""
    try:
        # Look for next button or pagination
        next_selectors = [
            'a[aria-label="Next"]',
            '.pagination-next:not(.disabled)',
            'a:has-text("Next"):not(.disabled)',
            '.page-next:not(.disabled)'
        ]
        
        for selector in next_selectors:
            try:
                next_button = page.query_selector(selector)
                if next_button and next_button.is_visible():
                    return True
            except:
                continue
                
        return False
        
    except Exception as e:
        logger.error(f"Error checking next page: {e}")
        return False

def go_to_next_page(page):
    """Navigate to next page"""
    try:
        next_selectors = [
            'a[aria-label="Next"]',
            '.pagination-next:not(.disabled)',
            'a:has-text("Next"):not(.disabled)',
            '.page-next:not(.disabled)'
        ]
        
        for selector in next_selectors:
            try:
                next_button = page.query_selector(selector)
                if next_button and next_button.is_visible():
                    logger.info(f"Clicking next page with selector: {selector}")
                    next_button.click()
                    page.wait_for_timeout(3000)  # Wait for page to load
                    return True
            except Exception as e:
                logger.error(f"Failed to click next with {selector}: {e}")
                continue
                
        return False
        
    except Exception as e:
        logger.error(f"Error going to next page: {e}")
        return False

def extract_all_hvac_contracts():
    """Extract HVAC contracts with pagination and deduplication"""
    logger.info("🚀 Starting Improved Contract Extraction")
    play_alert("Starting improved extraction")
    
    all_contracts = []
    seen_urls = set()  # For deduplication
    max_contracts = 53
    page_num = 1
    
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
            
            username = os.getenv("BIDNET_USERNAME")
            password = os.getenv("BIDNET_PASSWORD")
            
            page.fill("input[name='j_username']", username)
            page.fill("input[name='j_password']", password)
            page.click("button[type='submit']")
            page.wait_for_timeout(10000)
            
            logger.info("✅ Login successful!")
            
            # Navigate to search and search for HVAC
            logger.info("🔍 Searching for HVAC contracts...")
            page.goto("https://www.bidnetdirect.com/private/supplier/solicitations/search")
            page.wait_for_timeout(5000)
            
            search_field = page.wait_for_selector("textarea#solicitationSingleBoxSearch", timeout=10000)
            search_field.fill("hvac")
            
            search_button = page.wait_for_selector("button#topSearchButton", timeout=10000)
            search_button.click()
            page.wait_for_timeout(5000)
            
            # Extract contracts from all pages
            while len(all_contracts) < max_contracts:
                logger.info(f"📄 Processing page {page_num}...")
                
                page_contracts = get_page_contracts(page)
                new_contracts_added = 0
                
                for contract in page_contracts:
                    # Skip duplicates
                    if contract['source_url'] and contract['source_url'] in seen_urls:
                        logger.info(f"⏭️  Skipping duplicate: {contract['title'][:30]}...")
                        continue
                        
                    # Add unique contract
                    all_contracts.append(contract)
                    if contract['source_url']:
                        seen_urls.add(contract['source_url'])
                    new_contracts_added += 1
                    
                    logger.info(f"✅ Added contract {len(all_contracts)}: {contract['title'][:50]}...")
                    
                    # Stop if we reach our target
                    if len(all_contracts) >= max_contracts:
                        break
                
                logger.info(f"📊 Page {page_num} complete: {new_contracts_added} new contracts added (Total: {len(all_contracts)})")
                
                # Check if we need to go to next page
                if len(all_contracts) < max_contracts and has_next_page(page):
                    logger.info("➡️  Going to next page...")
                    if go_to_next_page(page):
                        page_num += 1
                        page.wait_for_timeout(3000)  # Wait for page to load
                    else:
                        logger.info("❌ Could not navigate to next page")
                        break
                else:
                    logger.info("🏁 No more pages or reached target")
                    break
            
            logger.info(f"🎉 Extraction complete! Found {len(all_contracts)} unique contracts")
            play_alert(f"Extraction complete: {len(all_contracts)} contracts")
            
        except Exception as e:
            logger.error(f"❌ Error during extraction: {e}")
            play_alert("Extraction failed")
            
        finally:
            browser.close()
    
    return all_contracts

def save_improved_contracts(contracts):
    """Save contracts with better formatting"""
    if not contracts:
        logger.info("📭 No contracts to save")
        return
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"data/improved_contracts_{timestamp}.txt"
    
    with open(filename, 'w') as f:
        f.write(f"IMPROVED HVAC CONTRACTS EXTRACTION\\n")
        f.write(f"Total Contracts: {len(contracts)}\\n")
        f.write(f"Extraction Time: {datetime.now()}\\n")
        f.write("=" * 80 + "\\n\\n")
        
        for i, contract in enumerate(contracts, 1):
            f.write(f"Contract {i}:\\n")
            f.write(f"  Title: {contract['title']}\\n")
            f.write(f"  Agency: {contract['agency']}\\n")
            f.write(f"  Location: {contract['location']}\\n")
            f.write(f"  Due Date: {contract['due_date']}\\n")
            f.write(f"  URL: {contract['source_url']}\\n")
            f.write(f"  Extracted: {contract['extracted_at']}\\n")
            f.write("-" * 80 + "\\n")
    
    logger.info(f"💾 Saved {len(contracts)} contracts to {filename}")
    
    # Also save to hvacscraper folder
    notes_file = "/Users/christophernguyen/Documents/hvacscraper/scraper_issues_and_fixes.txt"
    with open(notes_file, 'a') as f:
        f.write(f"\\n\\nEXTRACTION RUN - {datetime.now()}\\n")
        f.write(f"Total contracts extracted: {len(contracts)}\\n")
        f.write(f"File saved: {filename}\\n")
        f.write(f"Issues encountered: [Add any issues here]\\n")
    
    play_alert(f"Contracts saved: {len(contracts)} total")

def main():
    """Main improved extraction process"""
    logger.info("🌟 Improved BidNet Contract Extractor Starting...")
    
    contracts = extract_all_hvac_contracts()
    save_improved_contracts(contracts)
    
    logger.info("✅ Improved extraction process complete!")
    play_alert("All tasks complete")

if __name__ == "__main__":
    main()