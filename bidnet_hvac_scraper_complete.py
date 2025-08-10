#!/usr/bin/env python3
"""
BidNet HVAC Scraper - Complete Working Version
==============================================

This is the main production scraper that:
1. Automatically logs into BidNet Direct
2. Searches for HVAC contracts
3. Extracts ALL results with pagination support
4. Filters out invalid/duplicate entries
5. Validates results match expected total
6. Saves clean data to Excel and CSV files

Features:
- Smart pagination with duplicate detection
- Cookie banner handling
- Result count validation (self-checking)
- Clean data filtering (removes "No results found" entries)
- Comprehensive error handling
- Saves to Documents/hvacscraper/ folder

Usage: python3 bidnet_hvac_scraper_complete.py

Output: 
- Excel file: hvac_contracts_full_extraction_[timestamp].xlsx
- CSV file: hvac_contracts_full_extraction_[timestamp].csv
- Debug HTML files: data/debug_full_extraction_page_[N].html
"""

import logging
import time
from config import Config
from src.auth.bidnet_auth import BidNetAuthenticator
from src.scraper.bidnet_search import BidNetSearcher
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd
import os

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_full_hvac_extraction():
    """Complete test: Login + Search + Extract HVAC results to Excel"""
    logger.info("🧪 Starting Combined Full HVAC Extraction Test")
    
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
        
        # Initialize authenticator for helper methods
        authenticator = BidNetAuthenticator()
        authenticator.page = page
        authenticator.context = context
        authenticator.browser = browser
        
        # STEP 1: LOGIN (Test 1 functionality)
        logger.info("=" * 60)
        logger.info("STEP 1: LOGIN")
        logger.info("=" * 60)
        
        # Navigate directly to login URL (proven approach)
        login_url = "https://www.bidnetdirect.com/public/authentication/login"
        logger.info(f"Navigating directly to login page: {login_url}")
        page.goto(login_url)
        
        # Wait for page to load
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        page.wait_for_timeout(3000)
        
        logger.info(f"After navigation - Current URL: {page.url}")
        logger.info(f"After navigation - Page title: {page.title()}")
        
        # Perform login
        try:
            # Wait for login fields to appear
            page.wait_for_selector("input[name='j_username']", timeout=10000)
            page.wait_for_selector("input[name='j_password']", timeout=10000)
            
            # Enter credentials
            username_element = page.locator("input[name='j_username']").first
            password_element = page.locator("input[name='j_password']").first
            
            if username_element.is_visible() and password_element.is_visible():
                logger.info("Entering credentials")
                username_element.clear()
                username_element.fill(Config.USERNAME)
                password_element.clear()
                password_element.fill(Config.PASSWORD)
                
                # Click login button
                login_button = page.locator("button[type='submit']").first
                logger.info("Clicking login button")
                login_button.click()
                
                # Wait for login to complete
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except:
                    logger.info("Login may have succeeded despite timeout")
                
                logger.info("✅ Login attempt completed")
            else:
                logger.error("❌ Could not find login fields")
                return False
                
        except Exception as e:
            logger.warning(f"Login had issues but continuing: {e}")
        
        # STEP 2: NAVIGATE TO SEARCH AND PERFORM HVAC SEARCH (Test 3 functionality)
        logger.info("=" * 60)
        logger.info("STEP 2: HVAC SEARCH")
        logger.info("=" * 60)
        
        # Navigate to search page
        search_url = f"{Config.BASE_URL}private/supplier/solicitations/search"
        logger.info(f"Navigating to search page: {search_url}")
        try:
            page.goto(search_url, timeout=15000)
            page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception as e:
            logger.warning(f"Navigation timeout, but continuing: {e}")
        
        # Wait for dynamic content
        time.sleep(3)
        
        # Try to dismiss any cookie banner that might interfere with interactions
        logger.info("Checking for cookie banner to dismiss...")
        cookie_selectors = [
            '.cookie-banner button',
            '#cookie-banner button', 
            '[class*="cookie"] button',
            'button[class*="cookie"]',
            'button:has-text("Accept")',
            'button:has-text("OK")',
            'button:has-text("Close")',
            '.cookie-banner .close',
            '.cookie-banner [aria-label*="close"]',
            '.cookie-banner [aria-label*="dismiss"]'
        ]
        
        for cookie_selector in cookie_selectors:
            try:
                cookie_button = page.locator(cookie_selector).first
                if cookie_button.is_visible(timeout=2000):
                    logger.info(f"Dismissing cookie banner with selector: {cookie_selector}")
                    cookie_button.click()
                    time.sleep(1)
                    break
            except:
                continue
        
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
        
        # Save search page HTML for debugging
        page_html = page.content()
        debug_file = f"{Config.DATA_DIR}/debug_full_extraction_search_page.html"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(page_html)
        logger.info(f"Saved search page HTML: {debug_file}")
        
        # Find and fill search field
        search_element = None
        search_selectors = [
            'textarea#solicitationSingleBoxSearch',  # BidNet specific main search
            'textarea[name="keywords"]',              # BidNet specific
            'input[name*="search"]',
            'input[name*="keyword"]',
            'input[name*="query"]',
            'textarea[placeholder*="search"]',
            'textarea[placeholder*="keyword"]',
            'input[placeholder*="search"]',
            'input[placeholder*="keyword"]',
            '#search',
            '#searchText',
            '#keyword',
            '.search-input',
            'input[type="search"]',
            'input[type="text"][name*="search"]',
            'textarea[name*="search"]'
        ]
        
        for selector in search_selectors:
            try:
                if page.locator(selector).first.is_visible(timeout=2000):
                    search_element = page.locator(selector).first
                    logger.info(f"Found search field with selector: {selector}")
                    break
            except Exception as e:
                logger.debug(f"Search selector '{selector}' failed: {e}")
                continue
        
        if not search_element:
            logger.error("❌ Search field not found")
            return False
        
        # Enter HVAC keyword
        keyword = "hvac"
        logger.info(f"Entering keyword: {keyword}")
        
        try:
            search_element.clear()
            search_element.fill(keyword)
            
            # Verify the text was entered
            entered_value = search_element.input_value()
            logger.info(f"Search field value after entry: '{entered_value}'")
            
            if entered_value.lower() != keyword.lower():
                logger.warning(f"Search value doesn't match expected. Trying JavaScript...")
                # Try JavaScript input as fallback
                page.evaluate(f"""
                    const searchElement = document.querySelector('{search_selectors[0]}');
                    if (searchElement) {{
                        searchElement.value = '{keyword}';
                        searchElement.dispatchEvent(new Event('input'));
                        searchElement.dispatchEvent(new Event('change'));
                    }}
                """)
            
        except Exception as e:
            logger.error(f"Failed to enter search term: {str(e)}")
            return False
        
        # Find and click search button
        search_button = None
        button_selectors = [
            'button#topSearchButton',                 # BidNet specific
            'button.topSearch',                       # BidNet specific  
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Search")',
            'input[value*="Search"]',
            '.search-button',
            '#searchButton',
            '[data-testid*="search"]',
            'button[name*="search"]'
        ]
        
        for selector in button_selectors:
            try:
                if page.locator(selector).first.is_visible(timeout=2000):
                    search_button = page.locator(selector).first
                    logger.info(f"Found search button with selector: {selector}")
                    break
            except Exception as e:
                logger.debug(f"Button selector '{selector}' failed: {e}")
                continue
        
        if search_button:
            logger.info("✅ Search button found! Clicking...")
            search_button.click()
        else:
            logger.info("⚠️ No search button found - trying Enter key...")
            search_element.press("Enter")
        
        # Wait for search results to load
        logger.info("Waiting for search results...")
        try:
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        except:
            logger.info("Search results loading timeout, but continuing...")
        
        time.sleep(5)  # Extra wait for dynamic content
        
        # Check if we got results
        current_url = page.url
        logger.info(f"Current URL after search: {current_url}")
        
        # Look for signs of search results
        results_indicators = [
            'table',
            '.result',
            '.search-result',
            '[class*="table-row"]',
            'tr[class*="mets-table-row"]',
            'div[data-solicitation-id]',
            'tbody tr'
        ]
        
        found_results = False
        result_count = 0
        for indicator in results_indicators:
            try:
                elements = page.locator(indicator).all()
                visible_elements = [el for el in elements if el.is_visible(timeout=500)]
                if len(visible_elements) > 1:  # More than just header
                    logger.info(f"✅ Found {len(visible_elements)} result elements using '{indicator}'")
                    result_count = len(visible_elements)
                    found_results = True
                    break
            except Exception as e:
                logger.debug(f"Results indicator '{indicator}' check failed: {e}")
                continue
        
        if not found_results:
            logger.error("❌ No search results found")
            return False
        
        logger.info(f"✅ Found {result_count} search results!")
        
        # STEP 3: EXTRACT ALL RESULTS TO EXCEL (Test 4 functionality)
        logger.info("=" * 60)
        logger.info("STEP 3: EXTRACT RESULTS TO EXCEL")
        logger.info("=" * 60)
        
        # Extract results from all pages
        logger.info("Starting comprehensive result extraction...")
        all_contracts = []
        
        # Initialize BidNet searcher for parsing
        searcher = BidNetSearcher()
        
        # Extract results from current page and paginate through all
        all_contracts = extract_all_paginated_results(page, keyword, searcher)
        
        if all_contracts:
            logger.info(f"✅ Extracted {len(all_contracts)} total contracts!")
            
            # Save to Excel with timestamp
            timestamp = int(time.time())
            excel_filename = f"hvac_contracts_full_extraction_{timestamp}.xlsx"
            excel_path = save_contracts_to_excel(all_contracts, excel_filename)
            
            if excel_path:
                logger.info(f"✅ Successfully saved results to Excel: {excel_path}")
                
                # Also save a CSV version
                csv_filename = f"hvac_contracts_full_extraction_{timestamp}.csv"
                csv_path = save_contracts_to_csv(all_contracts, csv_filename)
                
                if csv_path:
                    logger.info(f"✅ Also saved results to CSV: {csv_path}")
                
                # Print summary
                logger.info("=" * 60)
                logger.info("EXTRACTION SUMMARY")
                logger.info("=" * 60)
                logger.info(f"Total contracts extracted: {len(all_contracts)}")
                logger.info(f"Search keyword: {keyword}")
                logger.info(f"Excel file: {excel_path}")
                logger.info(f"CSV file: {csv_path}")
                logger.info("=" * 60)
                
                return True
            else:
                logger.error("❌ Failed to save results to Excel")
                return False
                
        else:
            logger.error("❌ No contracts extracted")
            return False
            
    except Exception as e:
        logger.error(f"❌ Full extraction test ERROR: {str(e)}")
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
        
        logger.info("Combined full extraction test complete")

def extract_all_paginated_results(page, keyword, searcher):
    """Extract results from all pages with duplicate detection and result count validation"""
    all_contracts = []
    seen_urls = set()  # Track URLs to prevent duplicates
    page_num = 1
    max_pages = 20  # Safety limit
    expected_total = None
    
    # First, try to extract the expected total number of results
    try:
        page_content = page.content()
        # Look for patterns like "1 - 25 of 53 results found"
        import re
        total_patterns = [
            r'(\d+)\s+results?\s+found',
            r'of\s+(\d+)\s+results?',
            r'(\d+)\s+total\s+results?',
            r'showing\s+\d+\s*-\s*\d+\s+of\s+(\d+)',
            r'page\s+\d+\s+of\s+\d+\s+\((\d+)\s+total\)'
        ]
        
        for pattern in total_patterns:
            matches = re.findall(pattern, page_content, re.IGNORECASE)
            if matches:
                expected_total = int(matches[0])
                logger.info(f"📊 Expected total results: {expected_total}")
                break
        
        if not expected_total:
            # Fallback: Look in visible text
            page_text = page.inner_text()
            for pattern in total_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                if matches:
                    expected_total = int(matches[0])
                    logger.info(f"📊 Expected total results (from text): {expected_total}")
                    break
                    
    except Exception as e:
        logger.warning(f"Could not extract expected total: {e}")
        
    # Calculate expected pages if we know the total
    expected_pages = None
    if expected_total:
        results_per_page = 25  # BidNet typically shows 25 per page
        expected_pages = (expected_total + results_per_page - 1) // results_per_page  # Ceiling division
        logger.info(f"📊 Expected pages: {expected_pages} (based on {expected_total} results, {results_per_page} per page)")
    
    while page_num <= max_pages:
        logger.info(f"Processing page {page_num} of results...")
        
        # Save current page source for debugging
        debug_file = f"{Config.DATA_DIR}/debug_full_extraction_page_{page_num}.html"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(page.content())
        logger.info(f"Saved page {page_num} HTML: {debug_file}")
        
        # Parse results from current page using searcher's method
        page_contracts = searcher._parse_search_results(page.content(), keyword)
        
        # Filter out duplicates by URL
        new_contracts = []
        duplicates_found = 0
        
        for contract in page_contracts:
            contract_url = contract.get('url', '')
            if contract_url and contract_url not in seen_urls:
                seen_urls.add(contract_url)
                new_contracts.append(contract)
            elif contract_url:
                duplicates_found += 1
        
        if duplicates_found > 0:
            logger.warning(f"⚠️ Found {duplicates_found} duplicate contracts on page {page_num} (skipped)")
        
        if not new_contracts:
            # Check if we've reached our expected total
            if expected_total and len(all_contracts) >= expected_total:
                logger.info(f"✅ Reached expected total of {expected_total} contracts. Stopping pagination.")
                break
                
            # Check if we've hit expected page limit
            if expected_pages and page_num >= expected_pages:
                logger.info(f"✅ Reached expected page limit of {expected_pages}. Stopping pagination.")
                break
                
            # Don't stop immediately - continue for a few more pages to ensure we get everything
            logger.info(f"No new contracts found on page {page_num}, but continuing to check more pages...")
            
            # Only stop if we've checked at least 3 pages and hit 2 consecutive empty pages
            empty_pages = getattr(extract_all_paginated_results, '_empty_page_count', 0) + 1
            setattr(extract_all_paginated_results, '_empty_page_count', empty_pages)
            
            if empty_pages >= 2 and page_num >= 3:
                logger.info(f"Ending pagination after {empty_pages} consecutive empty pages")
                break
        else:
            # Reset empty page counter when we find new contracts
            setattr(extract_all_paginated_results, '_empty_page_count', 0)
            
        all_contracts.extend(new_contracts)
        logger.info(f"Found {len(new_contracts)} new contracts on page {page_num} (total unique: {len(all_contracts)})")
        
        # Check if we've reached our target
        if expected_total and len(all_contracts) >= expected_total:
            logger.info(f"✅ Reached expected total of {expected_total} contracts. Stopping pagination.")
            break
        
        # Look for next page button with enhanced selectors
        next_button = None
        next_selectors = [
            'a[rel="next"]',
            'a[class*="next"]',
            'a[title*="Next"]',
            'a[aria-label*="Next"]',
            f'a[href*="pageNumber={page_num + 1}"]',    # Direct page number link
            '.mets-pagination-page-icon.next',
            'a.next',
            'button[title*="Next"]',
            f'a[href*="&pageNumber={page_num + 1}"]',   # Alternative page number format
            f'a:has-text("{page_num + 1}")',            # Link containing next page number
            'button:has-text("Next")',
            '[data-testid="next"]'
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
                # First, try to dismiss any cookie banner that might be blocking
                cookie_selectors = [
                    '.cookie-banner button',
                    '#cookie-banner button',
                    '[class*="cookie"] button',
                    'button[class*="cookie"]',
                    'button:has-text("Accept")',
                    'button:has-text("OK")',
                    'button:has-text("Close")',
                    '.cookie-banner .close',
                    '.cookie-banner [aria-label*="close"]',
                    '.cookie-banner [aria-label*="dismiss"]'
                ]
                
                for cookie_selector in cookie_selectors:
                    try:
                        cookie_button = page.locator(cookie_selector).first
                        if cookie_button.is_visible(timeout=1000):
                            logger.info(f"Dismissing cookie banner with selector: {cookie_selector}")
                            cookie_button.click()
                            time.sleep(1)
                            break
                    except:
                        continue
                
                # Try to scroll to the next button and click
                next_button.scroll_into_view_if_needed()
                time.sleep(1)
                
                # Try a force click if normal click fails
                try:
                    next_button.click()
                except:
                    logger.info("Normal click failed, trying force click...")
                    next_button.click(force=True)
                
                # Wait for new page to load
                time.sleep(3)
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                page_num += 1
            except Exception as e:
                logger.error(f"Failed to click next page button: {e}")
                # Try to use the href directly as fallback
                try:
                    href = next_button.get_attribute('href')
                    if href:
                        if href.startswith('/'):
                            href = 'https://www.bidnetdirect.com' + href
                        logger.info(f"Trying direct navigation to: {href}")
                        page.goto(href)
                        time.sleep(3)
                        page_num += 1
                        continue
                except:
                    pass
                break
        else:
            # Try looking for direct page number link
            try:
                next_page_link = page.locator(f"text={page_num + 1}").first
                if next_page_link.is_visible(timeout=2000):
                    logger.info(f"Found direct page {page_num + 1} link")
                    next_page_link.scroll_into_view_if_needed()
                    time.sleep(1)
                    next_page_link.click()
                    time.sleep(3)
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                    page_num += 1
                    continue
            except:
                pass
                
            logger.info(f"No more pages found after page {page_num}")
            break
    
    # Final validation
    logger.info(f"Pagination complete: collected {len(all_contracts)} unique contracts from {page_num} pages")
    
    if expected_total:
        if len(all_contracts) == expected_total:
            logger.info(f"✅ SUCCESS: Extracted exactly {len(all_contracts)} contracts matching expected total of {expected_total}")
        elif len(all_contracts) < expected_total:
            logger.warning(f"⚠️ PARTIAL: Extracted {len(all_contracts)} contracts, expected {expected_total}. May have missed some results.")
        else:
            logger.warning(f"⚠️ OVER: Extracted {len(all_contracts)} contracts, expected {expected_total}. May have duplicates or counting error.")
    else:
        logger.info(f"ℹ️ No expected total available for validation. Extracted {len(all_contracts)} contracts.")
    
    return all_contracts

def save_contracts_to_excel(contracts, filename):
    """Save contracts to Excel file"""
    try:
        if not contracts:
            logger.warning("No contracts to save")
            return None
            
        # Save to Documents/hvacscraper folder as requested
        documents_folder = "/Users/christophernguyen/Documents/hvacscraper"
        os.makedirs(documents_folder, exist_ok=True)
        filepath = f"{documents_folder}/{filename}"
        
        # Prepare data for Excel
        excel_data = []
        for i, contract in enumerate(contracts, 1):
            row = {
                'Row_Number': i,
                'Title': contract.get('title', 'No title'),
                'Agency': contract.get('agency', 'Unknown'),
                'Location': contract.get('location', 'Unknown'),
                'Dates': contract.get('dates', 'No dates found'),
                'Estimated_Value': contract.get('estimated_value', 'Not specified'),
                'URL': contract.get('url', 'No URL'),
                'Search_Keyword': contract.get('search_keyword', ''),
                'Contract_ID': contract.get('id', ''),
                'Full_Text_Preview': contract.get('full_text', '')[:300] + '...' if contract.get('full_text') else '',
                'Raw_HTML_Sample': contract.get('raw_html', '')[:200] + '...' if contract.get('raw_html') else ''
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
                        
                adjusted_width = min(max_length + 2, 60)  # Cap at 60 characters
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        logger.info(f"Saved {len(contracts)} contracts to Excel file: {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"Failed to save Excel file: {str(e)}")
        return None

def save_contracts_to_csv(contracts, filename):
    """Save contracts to CSV file"""
    try:
        if not contracts:
            logger.warning("No contracts to save")
            return None
            
        # Save to Documents/hvacscraper folder as requested
        documents_folder = "/Users/christophernguyen/Documents/hvacscraper"
        os.makedirs(documents_folder, exist_ok=True)
        filepath = f"{documents_folder}/{filename}"
        
        # Prepare data for CSV (simpler format)
        csv_data = []
        for i, contract in enumerate(contracts, 1):
            row = {
                'Row_Number': i,
                'Title': contract.get('title', 'No title'),
                'Agency': contract.get('agency', 'Unknown'),
                'Location': contract.get('location', 'Unknown'),
                'Dates': contract.get('dates', 'No dates found'),
                'Estimated_Value': contract.get('estimated_value', 'Not specified'),
                'URL': contract.get('url', 'No URL'),
                'Search_Keyword': contract.get('search_keyword', ''),
                'Contract_ID': contract.get('id', '')
            }
            csv_data.append(row)
        
        # Convert to DataFrame and save
        df = pd.DataFrame(csv_data)
        df.to_csv(filepath, index=False, encoding='utf-8')
        
        logger.info(f"Saved {len(contracts)} contracts to CSV file: {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"Failed to save CSV file: {str(e)}")
        return None

if __name__ == "__main__":
    success = test_full_hvac_extraction()
    if success:
        logger.info("✅ Combined Full HVAC Extraction Test PASSED")
    else:
        logger.error("❌ Combined Full HVAC Extraction Test FAILED")