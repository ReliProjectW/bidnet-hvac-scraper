#!/usr/bin/env python3
"""
Updated BidNet Contract Extractor
Fixes data extraction and adds search keyword tracking
"""

import logging
import time
import subprocess
import os
import re
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
        subprocess.run(['osascript', '-e', f'display notification "{message}" with title "Updated Extractor"'], 
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

def parse_bidnet_contract_data(tr_element, row_index, search_keyword):
    """
    Parse BidNet contract data handling multiple formats
    Based on the examples provided by user
    """
    try:
        # Get all TD cells
        cells = tr_element.query_selector_all('td')
        
        if len(cells) < 2:
            return None
            
        # Look for contract link to get BidNet URL
        contract_link = tr_element.query_selector('a[href*="/private/supplier/interception/"]')
        
        if not contract_link:
            return None
            
        # Extract BidNet URL
        bidnet_url = contract_link.get_attribute('href')
        if bidnet_url and not bidnet_url.startswith('http'):
            bidnet_url = f"https://www.bidnetdirect.com{bidnet_url}"
            
        # Get the full text content for parsing
        full_text = tr_element.inner_text()
        lines = [line.strip() for line in full_text.split('\\n') if line.strip()]
        
        if not lines:
            return None
            
        # Extract title (usually the first substantial line)
        title = lines[0] if lines else "Unknown Title"
        
        # Initialize fields
        primary_agency = "Unknown Agency"
        secondary_agency = ""
        location = ""
        description = ""
        prebid_info = ""
        
        # Smart parsing based on content patterns
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Look for agency patterns
            if any(pattern in line_lower for pattern in ['state & local bids', 'federal bids', 'member agency bids']):
                secondary_agency = line
                # Previous line might be primary agency
                if i > 0:
                    prev_line = lines[i-1]
                    if not any(skip in prev_line.lower() for skip in ['hvac', 'air conditioning', 'heating']):
                        primary_agency = prev_line
            
            # Look for specific agency names
            elif any(pattern in line for pattern in ['University of', 'City of', 'County of', 'State of', 'District']):
                if primary_agency == "Unknown Agency":
                    primary_agency = line
                else:
                    location = line
            
            # Look for location patterns
            elif any(pattern in line for pattern in ['California', ', CA', 'Los Angeles']):
                if not location:
                    location = line
            
            # Look for prebid information
            elif 'mandatory pre-bid' in line_lower or 'pre-bid event' in line_lower:
                prebid_info = line
            
            # Look for description (longer lines that aren't titles/agencies)
            elif len(line) > 50 and not any(skip in line_lower for skip in ['state &', 'federal', 'member agency', 'mandatory']):
                if not description:
                    description = line
        
        # Clean up extracted data
        title = title.strip()
        primary_agency = primary_agency.strip() if primary_agency != "Unknown Agency" else primary_agency
        secondary_agency = secondary_agency.strip()
        location = location.strip() if location else "N/A"
        description = description.strip() if description else "N/A"
        prebid_info = prebid_info.strip() if prebid_info else "N/A"
        
        # Skip if no meaningful title
        if not title or len(title) < 5:
            return None
            
        return {
            'row_index': row_index,
            'title': title,
            'primary_agency': primary_agency,
            'secondary_agency': secondary_agency,
            'location': location,
            'description': description,
            'prebid_info': prebid_info,
            'bidnet_url': bidnet_url,
            'search_keyword': search_keyword,
            'extracted_at': datetime.now().isoformat(),
            'raw_text': full_text[:300]  # First 300 chars for debugging
        }
        
    except Exception as e:
        logger.error(f"Error parsing contract from row {row_index}: {e}")
        return None

def get_page_contracts(page, search_keyword):
    """Extract contracts from current page with improved parsing"""
    contracts = []
    
    try:
        # Wait for table to load
        page.wait_for_selector('tr', timeout=10000)
        
        # Get all TR elements
        tr_elements = page.query_selector_all('tr')
        logger.info(f"Found {len(tr_elements)} TR elements on current page")
        
        for i, tr in enumerate(tr_elements):
            contract = parse_bidnet_contract_data(tr, i, search_keyword)
            if contract:
                contracts.append(contract)
                logger.info(f"✅ Row {i}: {contract['title'][:50]}...")
                logger.info(f"   Agency: {contract['primary_agency'][:40]}...")
                logger.info(f"   URL: {contract['bidnet_url']}")
            else:
                logger.debug(f"⏭️  Skipped TR {i} (header/invalid)")
                
        logger.info(f"📊 Extracted {len(contracts)} valid contracts from {len(tr_elements)} rows")
                
    except Exception as e:
        logger.error(f"Error extracting page contracts: {e}")
    
    return contracts

def has_next_page(page):
    """Check if there's a next page available"""
    try:
        next_selectors = [
            'a[rel="next"]',
            'a[aria-label="Next"]',
            '.pagination-next:not(.disabled)',
            'a:has-text("Next"):not(.disabled)'
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
            'a[rel="next"]',
            'a[aria-label="Next"]', 
            '.pagination-next:not(.disabled)',
            'a:has-text("Next"):not(.disabled)'
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

def extract_updated_hvac_contracts():
    """Extract HVAC contracts with updated parsing"""
    logger.info("🚀 Starting Updated Contract Extraction with Improved Parsing")
    play_alert("Starting updated extraction")
    
    all_contracts = []
    seen_urls = set()  # For deduplication
    search_keyword = "hvac"  # Track what we searched for
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
            logger.info(f"🔍 Searching for '{search_keyword}' contracts...")
            page.goto("https://www.bidnetdirect.com/private/supplier/solicitations/search")
            page.wait_for_timeout(5000)
            
            # Handle cookie banner again if needed
            handle_cookie_banner(page)
            
            # Search for HVAC
            search_field = page.wait_for_selector("textarea#solicitationSingleBoxSearch", timeout=10000)
            search_field.fill(search_keyword)
            
            search_button = page.wait_for_selector("button#topSearchButton", timeout=10000)
            search_button.click()
            page.wait_for_timeout(8000)  # Wait longer for results
            
            # Extract contracts from all pages
            while len(all_contracts) < max_contracts:
                logger.info(f"📄 Processing page {page_num}...")
                
                page_contracts = get_page_contracts(page, search_keyword)
                new_contracts_added = 0
                
                for contract in page_contracts:
                    # Skip duplicates
                    if contract['bidnet_url'] and contract['bidnet_url'] in seen_urls:
                        logger.info(f"⏭️  Skipping duplicate: {contract['title'][:30]}...")
                        continue
                        
                    # Add unique contract
                    all_contracts.append(contract)
                    if contract['bidnet_url']:
                        seen_urls.add(contract['bidnet_url'])
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

def save_updated_contracts(contracts):
    """Save contracts with updated format including search keyword"""
    if not contracts:
        logger.info("📭 No contracts to save")
        return
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"data/updated_contracts_{timestamp}.txt"
    
    with open(filename, 'w') as f:
        f.write(f"UPDATED HVAC CONTRACTS EXTRACTION\\n")
        f.write(f"Total Contracts: {len(contracts)}\\n")
        f.write(f"Extraction Time: {datetime.now()}\\n")
        f.write("=" * 100 + "\\n\\n")
        
        for i, contract in enumerate(contracts, 1):
            f.write(f"Contract {i}:\\n")
            f.write(f"  Title: {contract['title']}\\n")
            f.write(f"  Primary Agency: {contract['primary_agency']}\\n")
            f.write(f"  Secondary Agency: {contract['secondary_agency']}\\n")
            f.write(f"  Location: {contract['location']}\\n")
            f.write(f"  Description: {contract['description']}\\n")
            f.write(f"  Prebid Info: {contract['prebid_info']}\\n")
            f.write(f"  BidNet URL: {contract['bidnet_url']}\\n")
            f.write(f"  Search Keyword: {contract['search_keyword']}\\n")
            f.write(f"  Extracted: {contract['extracted_at']}\\n")
            f.write(f"  Raw Text Sample: {contract['raw_text']}\\n")
            f.write("-" * 100 + "\\n")
    
    logger.info(f"💾 Saved {len(contracts)} contracts to {filename}")
    
    # Update notes
    notes_file = "/Users/christophernguyen/Documents/hvacscraper/scraper_issues_and_fixes.txt"
    with open(notes_file, 'a') as f:
        f.write(f"\\n\\nUPDATED EXTRACTION RUN - {datetime.now()}\\n")
        f.write(f"SUCCESS: Improved data parsing and added search keyword tracking\\n")
        f.write(f"Total contracts extracted: {len(contracts)}\\n")
        f.write(f"File saved: {filename}\\n")
        f.write(f"New features: Search keyword column, proper BidNet URLs, smart parsing\\n")
    
    play_alert(f"Updated extraction complete: {len(contracts)} contracts saved")

def main():
    """Main updated extraction process"""
    logger.info("🌟 Updated BidNet Contract Extractor Starting...")
    
    contracts = extract_updated_hvac_contracts()
    save_updated_contracts(contracts)
    
    logger.info("✅ Updated extraction process complete!")
    play_alert("All tasks complete")

if __name__ == "__main__":
    main()