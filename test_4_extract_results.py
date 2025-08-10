#!/usr/bin/env python3
"""
Test 4: Extract Listings from Search Results to Excel
Tests extracting all listings from each search result page and saving to Excel
"""

import logging
import time
from config import Config
from src.auth.bidnet_auth import BidNetAuthenticator
from src.scraper.bidnet_search import BidNetSearcher
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_extract_results():
    """Test extracting search results and saving to Excel"""
    logger.info("🧪 Starting Test 4: Extract Search Results to Excel")
    
    playwright = None
    browser = None
    context = None
    page = None
    
    try:
        # Setup Playwright browser
        playwright = sync_playwright().start()
        
        browser = playwright.chromium.launch(
            headless=Config.BROWSER_SETTINGS.get("headless", False),
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage", 
                "--disable-gpu"
            ]
        )
        
        context = browser.new_context(
            user_agent=Config.BROWSER_SETTINGS.get("user_agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"),
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = context.new_page()
        
        # Initialize authenticator with our page
        authenticator = BidNetAuthenticator()
        authenticator.page = page
        authenticator.context = context
        authenticator.browser = browser
        
        # Navigate to BidNet and login if needed
        logger.info("Navigating to BidNet...")
        page.goto(Config.BASE_URL)
        page.wait_for_load_state("networkidle")
        
        # Auto-login if on login page
        if authenticator.is_login_page(page):
            logger.info("🔑 Login required - performing auto-login...")
            if not authenticator.auto_login_if_needed(page):
                logger.error("❌ Auto-login failed")
                return False
        
        # Navigate to search page
        search_url = f"{Config.BASE_URL}private/supplier/solicitations/search"
        logger.info(f"Navigating to search page: {search_url}")
        page.goto(search_url)
        page.wait_for_load_state("networkidle")
        
        # Check if we got redirected to login again
        if authenticator.is_login_page(page):
            logger.info("🔑 Login required again - performing auto-login...")
            if not authenticator.auto_login_if_needed(page):
                logger.error("❌ Auto-login failed on search page")
                return False
            
            # Navigate back to search page after login
            page.goto(search_url)
            page.wait_for_load_state("networkidle")
        
        logger.info(f"Current URL: {page.url}")
        
        # Perform HVAC search
        search_element = None
        search_selectors = [
            'textarea#solicitationSingleBoxSearch',  # BidNet specific main search
            'textarea[name="keywords"]',              # BidNet specific
            'input[name*="search"]',
            'input[name*="keyword"]',
            'input[name*="query"]',
            'textarea[placeholder*="search"]',
            'input[type="search"]',
            'input[type="text"][name*="search"]'
        ]
        
        for selector in search_selectors:
            try:
                if page.locator(selector).first.is_visible(timeout=2000):
                    search_element = page.locator(selector).first
                    logger.info(f"Found search field with selector: {selector}")
                    break
            except:
                continue
        
        if not search_element:
            logger.error("❌ Search field not found")
            return False
        
        # Enter "hvac" and search
        keyword = "hvac"
        logger.info(f"Entering keyword: {keyword}")
        
        search_element.clear()
        search_element.fill(keyword)
        
        # Find and click search button
        search_button = None
        button_selectors = [
            'button#topSearchButton',
            'button.topSearch',
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Search")'
        ]
        
        for selector in button_selectors:
            try:
                if page.locator(selector).first.is_visible(timeout=2000):
                    search_button = page.locator(selector).first
                    break
            except:
                continue
        
        if search_button:
            search_button.click()
        else:
            search_element.press("Enter")
        
        # Wait for results
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        
        # Extract results from all pages
        logger.info("Starting result extraction...")
        all_contracts = []
        
        # Initialize BidNet searcher for parsing
        searcher = BidNetSearcher()
        
        # Extract results from current page and paginate through all
        all_contracts = _extract_all_paginated_results(page, keyword, searcher)
        
        if all_contracts:
            logger.info(f"✅ Extracted {len(all_contracts)} contracts!")
            
            # Save to Excel
            excel_filename = f"hvac_contracts_test_{int(time.time())}.xlsx"
            excel_path = save_contracts_to_excel(all_contracts, excel_filename)
            
            if excel_path:
                logger.info(f"✅ Successfully saved results to Excel: {excel_path}")
                return True
            else:
                logger.error("❌ Failed to save results to Excel")
                return False
                
        else:
            logger.error("❌ No contracts extracted")
            return False
            
    except Exception as e:
        logger.error(f"❌ Extract results test ERROR: {str(e)}")
        return False
    
    finally:
        # Clean up
        try:
            if page:
                page.close()
            if context:
                context.close()
            if browser:
                browser.close()
            if playwright:
                playwright.stop()
        except Exception as e:
            logger.debug(f"Error during cleanup: {e}")
        
        logger.info("Test 4 complete")

def _extract_all_paginated_results(page, keyword, searcher):
    """Extract results from all pages"""
    all_contracts = []
    page_num = 1
    max_pages = 5  # Limit for testing
    
    while page_num <= max_pages:
        logger.info(f"Processing page {page_num} of results...")
        
        # Save current page source for debugging
        debug_file = f"{Config.DATA_DIR}/debug_results_page_{page_num}.html"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(page.content())
        logger.info(f"Saved page {page_num} HTML: {debug_file}")
        
        # Parse results from current page using searcher's method
        page_contracts = searcher._parse_search_results(page.content(), keyword)
        
        if not page_contracts:
            logger.info(f"No contracts found on page {page_num}, ending pagination")
            break
            
        all_contracts.extend(page_contracts)
        logger.info(f"Found {len(page_contracts)} contracts on page {page_num} (total: {len(all_contracts)})")
        
        # Look for next page button
        next_button = None
        next_selectors = [
            'a[rel="next"]',
            'a[class*="next"]',
            'a[title*="Next"]',
            '.mets-pagination-page-icon.next',
            'a.next',
            'button[title*="Next"]'
        ]
        
        for selector in next_selectors:
            try:
                if page.locator(selector).first.is_visible(timeout=2000):
                    next_button = page.locator(selector).first
                    logger.info(f"Found next page button: {selector}")
                    break
            except:
                continue
        
        if next_button:
            try:
                next_button.scroll_into_view_if_needed()
                time.sleep(1)
                next_button.click()
                time.sleep(3)
                page_num += 1
            except Exception as e:
                logger.error(f"Failed to click next page button: {e}")
                break
        else:
            # Try looking for direct page number link
            try:
                next_page_link = page.locator(f"text={page_num + 1}").first
                if next_page_link.is_visible(timeout=2000):
                    logger.info(f"Found direct page {page_num + 1} link")
                    next_page_link.click()
                    time.sleep(3)
                    page_num += 1
                    continue
            except:
                pass
                
            logger.info(f"No more pages found after page {page_num}")
            break
    
    logger.info(f"Pagination complete: collected {len(all_contracts)} contracts from {page_num} pages")
    return all_contracts

def save_contracts_to_excel(contracts, filename):
    """Save contracts to Excel file"""
    try:
        if not contracts:
            logger.warning("No contracts to save")
            return None
            
        filepath = f"{Config.PROCESSED_DATA_DIR}/{filename}"
        
        # Prepare data for Excel
        excel_data = []
        for contract in contracts:
            row = {
                'Title': contract.get('title', 'No title'),
                'Agency': contract.get('agency', 'Unknown'),
                'Location': contract.get('location', 'Unknown'),
                'Dates': contract.get('dates', 'No dates found'),
                'Estimated_Value': contract.get('estimated_value', 'Not specified'),
                'URL': contract.get('url', 'No URL'),
                'Search_Keyword': contract.get('search_keyword', ''),
                'Contract_ID': contract.get('id', ''),
                'Full_Text_Preview': contract.get('full_text', '')[:200] + '...' if contract.get('full_text') else ''
            }
            excel_data.append(row)
        
        # Convert to DataFrame and save
        df = pd.DataFrame(excel_data)
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='HVAC Contracts', index=False)
            
            # Auto-adjust column widths
            workbook = writer.book
            worksheet = writer.sheets['HVAC Contracts']
            
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                        
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        logger.info(f"Saved {len(contracts)} contracts to Excel file: {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"Failed to save Excel file: {str(e)}")
        return None

if __name__ == "__main__":
    success = test_extract_results()
    if success:
        logger.info("✅ Test 4 PASSED")
    else:
        logger.error("❌ Test 4 FAILED")