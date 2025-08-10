#!/usr/bin/env python3
"""
Smart BidNet Contract Parser
Handles the 4 different BidNet data formats identified by user
"""

import logging
import time
import subprocess
import os
import re
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
    print("\\a", end="", flush=True)
    try:
        subprocess.run(['osascript', '-e', f'display notification "{message}" with title "Smart Parser"'], 
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

def smart_parse_bidnet_contract(tr_element, row_index, search_keyword):
    """
    Smart parser for BidNet contracts handling 4 different formats:
    1. Standard Format: Title -> Location -> Agency -> Description -> Prebid
    2. Federal Format: Title -> Agency1 -> Agency2 -> Description -> Location/Prebid
    3. State Format: Title -> Agency1 -> Agency2 -> Description -> Prebid -> Location
    4. Member Agency Format: Title -> Agency1 -> Agency2 -> Description/Location/Prebid
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
        lines = [line.strip() for line in full_text.split('\n') if line.strip()]
        
        if not lines:
            return None
            
        # Initialize fields
        title = ""
        primary_agency = "Unknown Agency"
        secondary_agency = ""
        location = ""
        description = ""
        prebid_info = ""
        
        # Extract complete title by combining title lines that appear to be connected
        title_lines = []
        for i, line in enumerate(lines):
            # First line is always part of title
            if i == 0:
                title_lines.append(line)
            # Check if subsequent lines are continuation of title (before agency/location info)
            elif i < 5:  # Only check first few lines
                line_lower = line.lower()
                # Skip lines that are clearly agency/location/bid type indicators
                if any(indicator in line_lower for indicator in [
                    'state & local bids', 'federal bids', 'member agency bids',
                    'university of', 'city of', 'county of', 'state of california',
                    'california federal notification', 'district', 'authority'
                ]):
                    break
                # Skip calendar/closing date lines
                elif any(skip in line_lower for skip in ['calendar', 'closing date', 'location', 'published date']):
                    break
                # If it's a short line that might be part of title
                elif len(line.strip()) > 0 and len(line.strip()) < 80:
                    title_lines.append(line)
                else:
                    break
        
        # Combine title lines with space
        original_title = ' '.join(title_lines).strip()
        
        # Use first line only for parsing/format detection to avoid confusion
        parsing_title = lines[0] if lines else "Unknown Title"
        
        # Determine format type and parse accordingly
        format_type = "unknown"
        
        # Look for format indicators
        has_federal = any("federal" in line.lower() for line in lines)
        has_state_local = any("state & local" in line.lower() for line in lines)
        has_member_agency = any("member agency" in line.lower() for line in lines)
        has_university = any("university of" in line.lower() for line in lines)
        has_city_county = any(keyword in line.lower() for line in lines for keyword in ["city of", "county of"])
        
        if has_federal:
            format_type = "federal"
        elif has_state_local and (has_city_county or "state of" in full_text.lower()):
            format_type = "state"
        elif has_member_agency:
            format_type = "member_agency"
        elif has_university or has_city_county:
            format_type = "standard"
        
        logger.debug(f"Detected format: {format_type} for contract: {title[:30]}...")
        
        # Parse based on format type with improved field extraction
        if format_type == "standard":
            # Standard Format: Title -> Location -> Agency -> Description -> Prebid
            # Example: Mid-Wilshire... -> UCLA -> State & Local Bids -> Description -> Mandatory Pre-Bid
            for i, line in enumerate(lines[1:], 1):  # Skip title
                if "university of" in line.lower() or "ucla" in line.lower():
                    if primary_agency == "Unknown Agency":
                        primary_agency = line
                    if not location:
                        location = line
                elif "state & local bids" in line.lower():
                    secondary_agency = line
                elif "mandatory pre-bid" in line.lower():
                    prebid_info = line
                elif len(line) > 50 and not description and not any(skip in line.lower() for skip in ['bids', 'mandatory', 'calendar', 'closing', 'location', 'published']):
                    description = line
                    
        elif format_type == "federal":
            # Federal Format: Title -> Agency1 -> Agency2 -> Description -> Location/Prebid
            # Example: USACE... -> California Federal Notification Required -> Federal Bids -> Description
            for i, line in enumerate(lines[1:], 1):
                if "federal notification" in line.lower() and primary_agency == "Unknown Agency":
                    primary_agency = line
                elif "federal bids" in line.lower():
                    secondary_agency = line
                elif len(line) > 50 and not description and not any(skip in line.lower() for skip in ['bids', 'federal', 'calendar', 'closing', 'location', 'published']):
                    description = line
                elif "california" in line.lower() and "federal" not in line.lower() and not location:
                    location = line
                        
        elif format_type == "state":
            # State Format: Title -> Agency1 -> Agency2 -> Description -> Prebid -> Location
            # Example: CHP... -> State of California - CHP -> State & Local Bids -> Description -> Mandatory Pre-Bid
            for i, line in enumerate(lines[1:], 1):
                # Look for city/state agency indicators
                if (any(keyword in line.lower() for keyword in ["city of", "county of", "state of california", "california highway patrol", "chp"]) 
                    and primary_agency == "Unknown Agency"):
                    primary_agency = line
                elif "state & local bids" in line.lower():
                    secondary_agency = line
                elif "mandatory pre-bid" in line.lower():
                    prebid_info = line
                elif len(line) > 50 and not description and not any(skip in line.lower() for skip in ['bids', 'mandatory', 'state of', 'calendar', 'closing', 'location', 'published']):
                    description = line
                    
        elif format_type == "member_agency":
            # Member Agency Format: Title -> Agency1 -> Agency2 -> Description/Location/Prebid
            # Example: HWD... -> Helix Water District -> Member Agency Bids
            for i, line in enumerate(lines[1:], 1):
                if (any(keyword in line.lower() for keyword in ["district", "water district", "helix", "county bhs"]) 
                    and primary_agency == "Unknown Agency"):
                    primary_agency = line
                elif "member agency bids" in line.lower():
                    secondary_agency = line
                elif len(line) > 30 and not description and not any(skip in line.lower() for skip in ['bids', 'district', 'calendar', 'closing', 'location', 'published']):
                    description = line
        else:
            # Enhanced fallback parsing for unknown formats
            for i, line in enumerate(lines[1:], 1):
                # Look for agency indicators first
                if any(keyword in line.lower() for keyword in ["city of", "county of", "state of", "university of", "district", "authority"]):
                    if primary_agency == "Unknown Agency":
                        primary_agency = line
                # Look for bid type indicators
                elif any(keyword in line.lower() for keyword in ["bids", "federal notification"]):
                    if not secondary_agency:
                        secondary_agency = line
                # Look for prebid info
                elif "mandatory" in line.lower() and "pre-bid" in line.lower():
                    prebid_info = line
                # Look for location indicators
                elif any(keyword in line.lower() for keyword in ["california", "los angeles", ", ca"]) and not location:
                    if not any(skip in line.lower() for skip in ['bids', 'state of']):
                        location = line
                # Look for description (longer lines that aren't other fields)
                elif len(line) > 50 and not description:
                    if not any(skip in line.lower() for skip in ['bids', 'mandatory', 'state of', 'federal', 'california']):
                        description = line
        
        # Clean up extracted fields
        original_title = original_title.strip()  # Clean but preserve full title
        primary_agency = primary_agency.strip()
        secondary_agency = secondary_agency.strip()
        location = location.strip() if location else "N/A"
        description = description.strip() if description else "N/A"
        prebid_info = prebid_info.strip() if prebid_info else "N/A"
        
        # Skip if no meaningful title
        if not original_title or len(original_title) < 5:
            return None
            
        return {
            'row_index': row_index,
            'title': original_title,  # Use the complete, unmodified title
            'primary_agency': primary_agency,
            'secondary_agency': secondary_agency,
            'location': location,
            'description': description,
            'prebid_info': prebid_info,
            'bidnet_url': bidnet_url,
            'search_keyword': search_keyword,
            'format_type': format_type,
            'extracted_at': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error parsing contract from row {row_index}: {e}")
        return None

def get_page_contracts_smart(page, search_keyword):
    """Extract contracts with smart parsing"""
    contracts = []
    
    try:
        # Wait for table to load
        page.wait_for_selector('tr', timeout=10000)
        
        # Get all TR elements
        tr_elements = page.query_selector_all('tr')
        logger.info(f"Found {len(tr_elements)} TR elements on current page")
        
        for i, tr in enumerate(tr_elements):
            contract = smart_parse_bidnet_contract(tr, i, search_keyword)
            if contract:
                contracts.append(contract)
                logger.info(f"✅ Row {i}: {contract['title'][:40]}...")
                logger.info(f"   Format: {contract['format_type']}")
                logger.info(f"   Primary Agency: {contract['primary_agency'][:40]}...")
                logger.info(f"   Secondary Agency: {contract['secondary_agency'][:40]}...")
                logger.info(f"   Location: {contract['location'][:30]}...")
            else:
                logger.debug(f"⏭️  Skipped TR {i}")
                
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
                    page.wait_for_timeout(3000)
                    return True
            except Exception as e:
                logger.error(f"Failed to click next with {selector}: {e}")
                continue
                
        return False
        
    except Exception as e:
        logger.error(f"Error going to next page: {e}")
        return False

def extract_smart_hvac_contracts():
    """Extract HVAC contracts with smart parsing"""
    logger.info("🚀 Starting Smart Contract Extraction with Intelligent Parsing")
    play_alert("Starting smart extraction")
    
    all_contracts = []
    seen_urls = set()
    search_keyword = "hvac"
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
            
            handle_cookie_banner(page)
            
            username = os.getenv("BIDNET_USERNAME")
            password = os.getenv("BIDNET_PASSWORD")
            
            page.fill("input[name='j_username']", username)
            page.fill("input[name='j_password']", password)
            page.click("button[type='submit']")
            page.wait_for_timeout(10000)
            
            logger.info("✅ Login successful!")
            
            # Search
            logger.info(f"🔍 Searching for '{search_keyword}' contracts...")
            page.goto("https://www.bidnetdirect.com/private/supplier/solicitations/search")
            page.wait_for_timeout(5000)
            
            handle_cookie_banner(page)
            
            search_field = page.wait_for_selector("textarea#solicitationSingleBoxSearch", timeout=10000)
            search_field.fill(search_keyword)
            
            search_button = page.wait_for_selector("button#topSearchButton", timeout=10000)
            search_button.click()
            page.wait_for_timeout(8000)
            
            # Extract with smart parsing
            while len(all_contracts) < max_contracts:
                logger.info(f"📄 Processing page {page_num} with smart parsing...")
                
                page_contracts = get_page_contracts_smart(page, search_keyword)
                new_contracts_added = 0
                
                for contract in page_contracts:
                    if contract['bidnet_url'] and contract['bidnet_url'] in seen_urls:
                        logger.info(f"⏭️  Skipping duplicate: {contract['title'][:30]}...")
                        continue
                        
                    all_contracts.append(contract)
                    if contract['bidnet_url']:
                        seen_urls.add(contract['bidnet_url'])
                    new_contracts_added += 1
                    
                    logger.info(f"✅ Added contract {len(all_contracts)}: {contract['title'][:40]}...")
                    
                    if len(all_contracts) >= max_contracts:
                        break
                
                logger.info(f"📊 Page {page_num} complete: {new_contracts_added} new contracts (Total: {len(all_contracts)})")
                
                if len(all_contracts) < max_contracts and has_next_page(page):
                    logger.info("➡️  Going to next page...")
                    if go_to_next_page(page):
                        page_num += 1
                        page.wait_for_timeout(3000)
                    else:
                        logger.info("❌ Could not navigate to next page")
                        break
                else:
                    logger.info("🏁 Reached target or no more pages")
                    break
            
            logger.info(f"🎉 Smart extraction complete! Found {len(all_contracts)} unique contracts")
            play_alert(f"Smart extraction complete: {len(all_contracts)} contracts")
            
        except Exception as e:
            logger.error(f"❌ Error during extraction: {e}")
            play_alert("Smart extraction failed")
            
        finally:
            browser.close()
    
    return all_contracts

def save_smart_contracts(contracts):
    """Save contracts with smart parsing results"""
    if not contracts:
        logger.info("📭 No contracts to save")
        return
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"data/smart_contracts_{timestamp}.txt"
    
    with open(filename, 'w') as f:
        f.write(f"SMART HVAC CONTRACTS EXTRACTION\\n")
        f.write(f"Total Contracts: {len(contracts)}\\n")
        f.write(f"Extraction Time: {datetime.now()}\\n")
        f.write("=" * 100 + "\\n\\n")
        
        # Group by format type
        format_counts = {}
        for contract in contracts:
            format_type = contract.get('format_type', 'unknown')
            format_counts[format_type] = format_counts.get(format_type, 0) + 1
        
        f.write("FORMAT DISTRIBUTION:\\n")
        for format_type, count in format_counts.items():
            f.write(f"  {format_type}: {count} contracts\\n")
        f.write("\\n" + "=" * 100 + "\\n\\n")
        
        for i, contract in enumerate(contracts, 1):
            f.write(f"Contract {i} [{contract.get('format_type', 'unknown').upper()}]:\\n")
            f.write(f"  Title: {contract['title']}\\n")
            f.write(f"  Primary Agency: {contract['primary_agency']}\\n")
            f.write(f"  Secondary Agency: {contract['secondary_agency']}\\n")
            f.write(f"  Location: {contract['location']}\\n")
            f.write(f"  Description: {contract['description']}\\n")
            f.write(f"  Prebid Info: {contract['prebid_info']}\\n")
            f.write(f"  BidNet URL: {contract['bidnet_url']}\\n")
            f.write(f"  Search Keyword: {contract['search_keyword']}\\n")
            f.write(f"  Format Type: {contract.get('format_type', 'unknown')}\\n")
            f.write(f"  Extracted: {contract['extracted_at']}\\n")
            f.write("-" * 100 + "\\n")
    
    logger.info(f"💾 Saved {len(contracts)} contracts to {filename}")
    
    # Update notes
    notes_file = "/Users/christophernguyen/Documents/hvacscraper/scraper_issues_and_fixes.txt"
    with open(notes_file, 'a') as f:
        f.write(f"\\n\\nSMART EXTRACTION RUN - {datetime.now()}\\n")
        f.write(f"SUCCESS: Intelligent parsing for 4 BidNet formats\\n")
        f.write(f"Total contracts extracted: {len(contracts)}\\n")
        f.write(f"Format distribution: {format_counts}\\n")
        f.write(f"File saved: {filename}\\n")
        f.write(f"New features: Smart format detection, proper field extraction\\n")
    
    play_alert(f"Smart extraction complete: {len(contracts)} contracts saved")

def main():
    """Main smart extraction process"""
    logger.info("🌟 Smart BidNet Contract Parser Starting...")
    
    contracts = extract_smart_hvac_contracts()
    save_smart_contracts(contracts)
    
    logger.info("✅ Smart extraction process complete!")
    play_alert("All tasks complete")

if __name__ == "__main__":
    main()