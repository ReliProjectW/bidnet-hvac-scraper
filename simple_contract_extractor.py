#!/usr/bin/env python3
"""
Simple BidNet Contract Extractor with Audio Alerts
Focus: Just login and extract 53 HVAC contracts reliably
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

def extract_hvac_contracts():
    """Simple, reliable HVAC contract extraction"""
    logger.info("🚀 Starting Simple Contract Extraction")
    play_alert("Starting contract extraction")
    
    contracts = []
    
    with sync_playwright() as p:
        # Launch browser (non-headless for debugging)
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
            # Step 1: Navigate to login
            logger.info("🔐 Step 1: Navigating to BidNet login...")
            page.goto("https://www.bidnetdirect.com/public/authentication/login")
            page.wait_for_timeout(3000)
            
            logger.info(f"Current URL: {page.url}")
            logger.info(f"Page title: {page.title()}")
            
            # Step 2: Login
            logger.info("🔑 Step 2: Attempting login...")
            
            # Wait for login fields
            page.wait_for_selector("input[name='j_username']", timeout=10000)
            page.wait_for_selector("input[name='j_password']", timeout=10000)
            
            # Enter credentials from .env file
            username = os.getenv("BIDNET_USERNAME")
            password = os.getenv("BIDNET_PASSWORD")
            
            if not username or not password:
                logger.error("❌ Missing credentials in .env file")
                play_alert("Missing credentials")
                return contracts
            
            logger.info(f"Using username: {username}")
            page.fill("input[name='j_username']", username)
            page.fill("input[name='j_password']", password)
            
            # Click login
            page.click("button[type='submit']")
            page.wait_for_timeout(10000)  # Wait for login to complete
            
            logger.info(f"After login - URL: {page.url}")
            logger.info(f"After login - Title: {page.title()}")
            
            # Check if login was successful
            if "login" in page.url.lower():
                logger.error("❌ Login appears to have failed - still on login page")
                play_alert("Login failed")
                return contracts
            
            logger.info("✅ Login appears successful!")
            play_alert("Login successful")
            
            # Step 3: Navigate to search
            logger.info("🔍 Step 3: Navigating to search page...")
            search_url = "https://www.bidnetdirect.com/private/supplier/solicitations/search"
            page.goto(search_url)
            page.wait_for_timeout(5000)
            
            logger.info(f"Search page URL: {page.url}")
            
            # Step 4: Search for HVAC
            logger.info("🏢 Step 4: Searching for HVAC contracts...")
            
            # Try different search field selectors
            search_selectors = [
                "textarea#solicitationSingleBoxSearch",
                "input[name='searchKeyword']", 
                "textarea[placeholder*='search']",
                ".search-input",
                "#search"
            ]
            
            search_field = None
            for selector in search_selectors:
                try:
                    search_field = page.wait_for_selector(selector, timeout=3000)
                    logger.info(f"✅ Found search field with selector: {selector}")
                    break
                except:
                    logger.info(f"❌ Search selector failed: {selector}")
                    continue
            
            if not search_field:
                # Save page for debugging
                page.locator("body").screenshot(path="data/search_page_debug.png")
                with open("data/search_page_debug.html", "w") as f:
                    f.write(page.content())
                logger.error("❌ Could not find search field")
                play_alert("Search field not found")
                return contracts
            
            # Enter search term
            search_field.fill("hvac")
            logger.info("✅ Entered 'hvac' in search field")
            
            # Find and click search button
            search_buttons = [
                "button#topSearchButton",
                "button[type='submit']",
                ".search-button",
                "input[type='submit']"
            ]
            
            search_button = None
            for selector in search_buttons:
                try:
                    search_button = page.wait_for_selector(selector, timeout=3000)
                    logger.info(f"✅ Found search button with selector: {selector}")
                    break
                except:
                    continue
            
            if search_button:
                search_button.click()
                logger.info("🔍 Clicked search button")
                page.wait_for_timeout(5000)
            else:
                # Try pressing Enter
                search_field.press("Enter")
                logger.info("🔍 Pressed Enter to search")
                page.wait_for_timeout(5000)
            
            # Step 5: Extract results
            logger.info("📋 Step 5: Extracting contract results...")
            
            # Try different result selectors
            result_selectors = [
                '[class*="table-row"]:not(.table-header)',
                '.search-result',
                '.solicitation-row',
                '[data-testid="search-result"]'
            ]
            
            results = []
            for selector in result_selectors:
                try:
                    results = page.query_selector_all(selector)
                    if results:
                        logger.info(f"✅ Found {len(results)} results with selector: {selector}")
                        break
                except:
                    continue
            
            if not results:
                # Save page for debugging
                with open("data/search_results_debug.html", "w") as f:
                    f.write(page.content())
                logger.warning("❌ No results found - saved page for debugging")
                play_alert("No search results found")
                return contracts
            
            # Extract contract details
            logger.info(f"📊 Processing {len(results)} potential contracts...")
            
            for i, result in enumerate(results):
                try:
                    # Extract basic info (adapt based on actual HTML structure)
                    title_elem = result.query_selector('a[href*="/private/solicitation/"]')
                    title = title_elem.inner_text().strip() if title_elem else f"Contract {i+1}"
                    
                    source_url = title_elem.get_attribute('href') if title_elem else None
                    if source_url and not source_url.startswith('http'):
                        source_url = f"https://www.bidnetdirect.com{source_url}"
                    
                    contract = {
                        'id': i + 1,
                        'title': title,
                        'source_url': source_url,
                        'extracted_at': datetime.now().isoformat()
                    }
                    
                    contracts.append(contract)
                    logger.info(f"✅ Extracted contract {i+1}: {title[:50]}...")
                    
                except Exception as e:
                    logger.error(f"❌ Error extracting contract {i+1}: {e}")
                    continue
            
            logger.info(f"🎉 Extraction complete! Found {len(contracts)} contracts")
            play_alert(f"Extraction complete: {len(contracts)} contracts found")
            
        except Exception as e:
            logger.error(f"❌ Error during extraction: {e}")
            play_alert("Extraction failed")
            
        finally:
            browser.close()
    
    return contracts

def save_contracts(contracts):
    """Save contracts to file with audio alert"""
    if not contracts:
        logger.info("📭 No contracts to save")
        return
    
    # Save as simple text file for now
    filename = f"data/extracted_contracts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(filename, 'w') as f:
        f.write(f"HVAC Contracts Extracted: {len(contracts)}\\n")
        f.write(f"Extraction Time: {datetime.now()}\\n")
        f.write("=" * 80 + "\\n\\n")
        
        for contract in contracts:
            f.write(f"Contract {contract['id']}:\\n")
            f.write(f"  Title: {contract['title']}\\n")
            f.write(f"  URL: {contract['source_url']}\\n")
            f.write(f"  Extracted: {contract['extracted_at']}\\n")
            f.write("-" * 40 + "\\n")
    
    logger.info(f"💾 Saved {len(contracts)} contracts to {filename}")
    play_alert(f"Contracts saved to {filename}")

def main():
    """Main extraction process"""
    logger.info("🌟 Simple BidNet Contract Extractor Starting...")
    
    contracts = extract_hvac_contracts()
    save_contracts(contracts)
    
    logger.info("✅ Extraction process complete!")
    play_alert("All tasks complete")

if __name__ == "__main__":
    main()