#!/usr/bin/env python3
"""
Fully Automated BidNet HVAC Search
Logs in, searches for HVAC contracts, and extracts all results automatically
"""

import sys
import logging
import json
import time
from pathlib import Path
from datetime import datetime
import pandas as pd

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from config import Config
import re

def setup_logging():
    """Set up simple logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def setup_browser():
    """Set up browser"""
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(3)
    
    return driver

def load_saved_cookies(driver):
    """Load cookies saved by login_only.py"""
    logger = logging.getLogger(__name__)
    cookies_file = Path(Config.DATA_DIR) / "bidnet_cookies.json"
    
    if not cookies_file.exists():
        logger.error("❌ No saved cookies found. Will attempt fresh login...")
        return False
    
    try:
        with open(cookies_file, 'r') as f:
            cookie_data = json.load(f)
        
        # Check cookie age
        cookie_age = time.time() - cookie_data.get("timestamp", 0)
        if cookie_age > 86400:  # 24 hours
            logger.warning("⚠️ Cookies are over 24 hours old, may need refresh")
        
        # Navigate to domain first
        driver.get(Config.BASE_URL)
        time.sleep(2)
        
        # Load cookies
        selenium_cookies = cookie_data.get("selenium_cookies", [])
        for cookie in selenium_cookies:
            try:
                cookie_clean = {k: v for k, v in cookie.items() 
                              if k in ['name', 'value', 'domain', 'path', 'secure', 'httpOnly']}
                driver.add_cookie(cookie_clean)
            except Exception as e:
                logger.debug(f"Could not add cookie: {e}")
        
        logger.info("✅ Loaded saved authentication cookies")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to load cookies: {e}")
        return False

def test_authentication(driver):
    """Test if current authentication is working"""
    logger = logging.getLogger(__name__)
    
    try:
        # Try to access a protected page
        test_url = f"{Config.BASE_URL}private/supplier/solicitations/search"
        driver.get(test_url)
        time.sleep(3)
        
        current_url = driver.current_url
        page_source = driver.page_source
        
        # More specific checks for successful authentication
        # Look for positive signs first
        if ('Solicitation Search' in page_source or 
            'solicitations/search' in current_url or
            'Search Results' in page_source or
            'mets-table-row' in page_source):
            logger.info("✅ Authentication test passed - found protected content")
            return True
        
        # Only fail if we're clearly redirected to login
        if ('login' in current_url.lower() and 'solicitation' not in current_url.lower()) or \
           'saml' in current_url.lower() or \
           'please log in' in page_source.lower() or \
           'sign in' in page_source.lower():
            logger.warning("❌ Authentication test failed - redirected to login")
            return False
            
        # If we're not sure, assume it's working (less strict)
        logger.info("✅ Authentication test passed - no clear login redirect")
        return True
        
    except Exception as e:
        logger.error(f"❌ Authentication test error: {e}")
        return False

def perform_fresh_login(driver):
    """Perform fresh authentication using the browser"""
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("🔄 Performing fresh authentication...")
        
        # Navigate to login page
        driver.get(Config.BASE_URL)
        time.sleep(2)
        driver.get(Config.LOGIN_URL)
        time.sleep(3)
        
        # Look for username field
        wait = WebDriverWait(driver, 20)
        username_selectors = [
            "input[name='username']",
            "input[type='email']", 
            "input[id*='username']",
            "input[id*='email']"
        ]
        
        username_field = None
        for selector in username_selectors:
            try:
                username_field = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except NoSuchElementException:
                continue
                
        if not username_field:
            logger.error("❌ Could not find username field for fresh login")
            return False
        
        # Look for password field
        password_field = None
        password_selectors = [
            "input[name='password']",
            "input[type='password']"
        ]
        
        for selector in password_selectors:
            try:
                password_field = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except NoSuchElementException:
                continue
                
        if not password_field:
            logger.error("❌ Could not find password field for fresh login")
            return False
        
        # Enter credentials
        logger.info("🔑 Entering credentials...")
        username_field.clear()
        username_field.send_keys(Config.USERNAME)
        
        password_field.clear()
        password_field.send_keys(Config.PASSWORD)
        
        # Find and click login button
        login_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button[id*='login']"
        ]
        
        login_button = None
        for selector in login_selectors:
            try:
                login_button = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except NoSuchElementException:
                continue
                
        if login_button:
            logger.info("🚀 Clicking login button...")
            login_button.click()
        else:
            # Try pressing Enter
            password_field.send_keys(Keys.RETURN)
        
        # Wait for authentication to complete
        time.sleep(5)
        
        # Test if login worked
        if test_authentication(driver):
            logger.info("✅ Fresh authentication successful!")
            # Save cookies for future use
            save_cookies_from_driver(driver)
            return True
        else:
            logger.error("❌ Fresh authentication failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Fresh login error: {e}")
        return False

def save_cookies_from_driver(driver):
    """Save cookies from current driver session"""
    try:
        cookies_file = Path(Config.DATA_DIR) / "bidnet_cookies.json"
        
        # Get all cookies from driver
        selenium_cookies = driver.get_cookies()
        
        # Build requests-compatible cookies
        requests_cookies = {}
        for cookie in selenium_cookies:
            requests_cookies[cookie['name']] = cookie['value']
        
        cookie_data = {
            "selenium_cookies": selenium_cookies,
            "requests_cookies": requests_cookies,
            "timestamp": time.time()
        }
        
        with open(cookies_file, 'w') as f:
            json.dump(cookie_data, f, indent=2)
            
        logging.getLogger(__name__).info("💾 Saved fresh cookies")
        
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to save cookies: {e}")

def ensure_authentication(driver):
    """Ensure we have working authentication, with fallback to fresh login"""
    logger = logging.getLogger(__name__)
    
    logger.info("🔐 Ensuring authentication...")
    
    # Step 1: Try to load saved cookies
    cookies_loaded = load_saved_cookies(driver)
    
    # Step 2: Test if authentication works
    if cookies_loaded:
        if test_authentication(driver):
            logger.info("✅ Saved authentication is working")
            return True
        else:
            logger.warning("⚠️ Saved cookies are invalid, attempting fresh login...")
    
    # Step 3: Fallback to fresh login
    if perform_fresh_login(driver):
        logger.info("✅ Authentication restored via fresh login")
        return True
    else:
        logger.error("❌ All authentication methods failed")
        return False

def perform_search(driver, search_term="hvac"):
    """Navigate to search page and perform search"""
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"🔍 Searching for: {search_term}")
        
        # Navigate to search page
        search_url = f"{Config.BASE_URL}private/supplier/solicitations/search"
        driver.get(search_url)
        time.sleep(3)
        
        # Look for search input field
        wait = WebDriverWait(driver, 10)
        search_field = None
        
        search_selectors = [
            'input[name*="search"]',
            'input[name*="keyword"]', 
            'input[name*="query"]',
            'input[placeholder*="search"]',
            'input[placeholder*="keyword"]',
            '#search',
            '#searchText',
            '#keyword',
            '.search-input',
            'input[type="search"]'
        ]
        
        for selector in search_selectors:
            try:
                search_field = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                logger.info(f"✅ Found interactive search field with selector: {selector}")
                break
            except (NoSuchElementException, TimeoutException):
                continue
        
        if not search_field:
            logger.error("❌ Could not find search field")
            return False
        
        # Wait for field to be interactive and clear any existing content
        try:
            # Scroll field into view
            driver.execute_script("arguments[0].scrollIntoView(true);", search_field)
            time.sleep(1)
            
            # Click the field first to ensure it's focused and active
            search_field.click()
            time.sleep(1)
            
            # Clear existing content (try multiple methods)
            try:
                search_field.clear()
            except:
                # Fallback: select all and delete
                search_field.send_keys(Keys.CONTROL + "a")
                search_field.send_keys(Keys.DELETE)
            
            # Enter search term
            search_field.send_keys(search_term)
            logger.info(f"📝 Entered search term: {search_term}")
            
        except Exception as e:
            logger.error(f"❌ Error entering search term: {e}")
            return False
        
        # Look for search button
        search_button = None
        button_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:contains("Search")',
            '.search-button',
            '#searchButton',
            '[data-testid*="search"]'
        ]
        
        for selector in button_selectors:
            try:
                if 'contains' in selector:
                    search_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Search')]")
                else:
                    search_button = driver.find_element(By.CSS_SELECTOR, selector)
                logger.info(f"✅ Found search button with selector: {selector}")
                break
            except NoSuchElementException:
                continue
        
        if search_button:
            logger.info("🚀 Clicking search button...")
            search_button.click()
        else:
            logger.info("🚀 Pressing Enter to search...")
            search_field.send_keys(Keys.RETURN)
        
        # Wait for results to load
        time.sleep(3)
        
        logger.info("✅ Search completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Search failed: {e}")
        return False

def set_results_per_page(driver, results_per_page=100):
    """Try to set results per page to get more contracts"""
    logger = logging.getLogger(__name__)
    
    try:
        wait = WebDriverWait(driver, 5)
        
        # Look for results per page dropdown/selector
        selectors_to_try = [
            'select[name*="pageSize"]',
            'select[name*="resultsPerPage"]', 
            'select[id*="pageSize"]',
            'select[id*="resultsPerPage"]',
            '.results-per-page select',
            '.page-size select'
        ]
        
        for selector in selectors_to_try:
            try:
                dropdown = driver.find_element(By.CSS_SELECTOR, selector)
                # Try to select 100 results per page
                from selenium.webdriver.support.ui import Select
                select = Select(dropdown)
                
                # Try different values
                for value in ['100', '50', '25']:
                    try:
                        select.select_by_value(value)
                        logger.info(f"✅ Set results per page to {value}")
                        time.sleep(2)  # Wait for page to reload
                        return True
                    except:
                        continue
                        
            except NoSuchElementException:
                continue
        
        logger.info("ℹ️ Could not find results per page setting")
        return False
        
    except Exception as e:
        logger.debug(f"Results per page setting failed: {e}")
        return False

def extract_single_contract(element, index, selector_used):
    """Extract data from a single contract element"""
    try:
        text_content = element.get_text(strip=True)
        
        contract = {
            'index': index,
            'selector_used': selector_used,
            'raw_html': str(element)[:1000],
            'full_text': text_content[:500]
        }
        
        # Extract title - first meaningful text or link
        title_element = element.find(['a', 'strong', 'b', 'h1', 'h2', 'h3']) 
        if title_element:
            title = title_element.get_text(strip=True)
        else:
            # Use first line of text
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
            title = lines[0] if lines else 'No title'
        
        contract['title'] = title[:200]  # Limit length
        
        # Extract all links - prioritize BidNet contract links
        links = element.find_all('a', href=True)
        best_link = None
        link_text = None
        
        for link in links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Priority 1: Direct contract/solicitation links
            if any(term in href.lower() for term in ['view-notice', 'solicitation', 'opportunity']):
                best_link = href
                link_text = text
                break
            # Priority 2: Any BidNet internal link with meaningful text
            elif href.startswith('/') and len(text) > 10:
                best_link = href
                link_text = text
        
        # Fallback: take first link
        if not best_link and links:
            best_link = links[0].get('href', '')
            link_text = links[0].get_text(strip=True)
        
        # Ensure full URL
        if best_link:
            if not best_link.startswith('http'):
                if best_link.startswith('/'):
                    best_link = 'https://www.bidnetdirect.com' + best_link
                else:
                    best_link = 'https://www.bidnetdirect.com/' + best_link.lstrip('/')
        
        contract['url'] = best_link
        contract['link_text'] = link_text
        
        # Extract dates
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{1,2}-\d{1,2}-\d{4}',
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4}'
        ]
        
        found_dates = []
        for pattern in date_patterns:
            dates = re.findall(pattern, text_content, re.IGNORECASE)
            found_dates.extend(dates)
        
        contract['dates'] = ' | '.join(found_dates[:3]) if found_dates else 'No dates'
        
        # Extract dollar amounts
        amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', text_content)
        contract['estimated_value'] = amounts[0] if amounts else 'Not specified'
        
        # Extract agency info
        agency_patterns = [
            r'(?i)(city of|county of|school district)[\w\s]+',
            r'(?i)(university of)[\w\s]+',
        ]
        
        agency = 'Unknown agency'
        for pattern in agency_patterns:
            matches = re.findall(pattern, text_content)
            if matches:
                agency = matches[0]
                break
        
        contract['agency'] = agency
        
        # HVAC relevance scoring
        hvac_terms = ['hvac', 'heat pump', 'air conditioning', 'heating', 'ventilation', 'mini-split', 'furnace', 'air handler']
        hvac_score = sum(1 for term in hvac_terms if term.lower() in text_content.lower())
        contract['hvac_relevance_score'] = hvac_score
        
        # Check for negative terms
        negative_terms = ['maintenance', 'service', 'repair', 'geothermal']
        has_negative = any(term in text_content.lower() for term in negative_terms)
        contract['has_negative_terms'] = has_negative
        
        return contract
        
    except Exception as e:
        print(f"Error extracting contract {index}: {e}")
        return None

def extract_contract_data(soup, url):
    """Extract contract data from page using patterns from page inspector"""
    logger = logging.getLogger(__name__)
    
    # Try the selectors we found from page inspector
    selectors_to_try = [
        'tr.mets-table-row.odd',
        'tr.even.mets-table-row',
        'tr[class*="mets-table-row"]',
        'tbody tr',
        'table tr'
    ]
    
    contracts = []
    
    for selector in selectors_to_try:
        try:
            elements = soup.select(selector)
            if elements and len(elements) > 2:  # Need multiple rows
                logger.info(f"✅ Found {len(elements)} rows using: {selector}")
                
                for i, element in enumerate(elements):
                    # Skip header rows
                    if element.find('th') or len(element.get_text(strip=True)) < 10:
                        continue
                    
                    contract = extract_single_contract(element, i, selector)
                    if contract:
                        contracts.append(contract)
                
                if contracts:
                    logger.info(f"📊 Extracted {len(contracts)} contracts")
                    break
                    
        except Exception as e:
            logger.debug(f"Selector {selector} failed: {e}")
            continue
    
    # Fallback: look for HVAC content
    if not contracts:
        logger.info("🔍 No table rows found, searching for HVAC content...")
        all_elements = soup.find_all(['div', 'tr', 'p', 'article'])
        
        for i, element in enumerate(all_elements):
            text = element.get_text().lower()
            if any(term in text for term in ['hvac', 'heating', 'air conditioning', 'heat pump']):
                if len(text) > 50:  # Meaningful content
                    contract = extract_single_contract(element, i, 'hvac_content')
                    if contract:
                        contracts.append(contract)
        
        if contracts:
            logger.info(f"🎯 Found {len(contracts)} elements with HVAC content")
    
    return contracts

def get_all_pages_contracts(driver):
    """Extract contracts from all pages of search results"""
    logger = logging.getLogger(__name__)
    all_contracts = []
    page_num = 1
    
    while True:
        logger.info(f"📄 Processing page {page_num}...")
        
        # Get contracts from current page
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        contracts = extract_contract_data(soup, driver.current_url)
        
        if contracts:
            logger.info(f"   Found {len(contracts)} contracts on page {page_num}")
            # Add page number to each contract
            for contract in contracts:
                contract['page_number'] = page_num
            all_contracts.extend(contracts)
        else:
            logger.info(f"   No contracts found on page {page_num}")
        
        # Look for next page button/link
        next_page_found = False
        next_selectors = [
            'a[title*="Next"]',
            'a[aria-label*="Next"]', 
            'a:contains("Next")',
            'a:contains(">")',
            '.pagination .next',
            '.pager .next',
            '[class*="next"]:not(.disabled)',
            'a[href*="page"]'
        ]
        
        for selector in next_selectors:
            try:
                if 'contains' in selector:
                    # Use XPath for text-based search
                    xpath = "//a[contains(text(), 'Next')] | //a[contains(text(), '>')]"
                    next_button = driver.find_element(By.XPATH, xpath)
                else:
                    next_button = driver.find_element(By.CSS_SELECTOR, selector)
                
                # Check if button is disabled
                classes = next_button.get_attribute('class') or ''
                if 'disabled' in classes.lower() or 'inactive' in classes.lower():
                    continue
                    
                logger.info(f"🔄 Found next page button, clicking...")
                next_button.click()
                time.sleep(3)  # Wait for page to load
                next_page_found = True
                break
                
            except (NoSuchElementException, Exception) as e:
                continue
        
        if not next_page_found:
            logger.info(f"✅ No more pages found. Processed {page_num} total pages.")
            break
            
        page_num += 1
        
        # Safety limit
        if page_num > 10:
            logger.warning("⚠️ Stopped at 10 pages for safety")
            break
    
    return all_contracts

def save_to_excel(contracts, search_term):
    """Save contracts to Excel file"""
    if not contracts:
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"automated_search_{search_term}_{timestamp}.xlsx"
    filepath = f"data/processed/{filename}"
    
    # Prepare data
    excel_data = []
    for contract in contracts:
        excel_data.append({
            'Title': contract['title'],
            'Agency': contract['agency'], 
            'Dates': contract['dates'],
            'Estimated_Value': contract['estimated_value'],
            'BidNet_URL': contract['url'],
            'Link_Text': contract.get('link_text', ''),
            'Page_Number': contract.get('page_number', 1),
            'HVAC_Relevance_Score': contract['hvac_relevance_score'],
            'Has_Negative_Terms': contract['has_negative_terms'],
            'Selector_Used': contract['selector_used'],
            'Index': contract['index'],
            'Full_Text': contract['full_text']
        })
    
    df = pd.DataFrame(excel_data)
    
    # Save with formatting
    with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='HVAC Contracts', index=False)
        worksheet = writer.sheets['HVAC Contracts']
        
        # Auto-adjust column widths
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
    
    return filepath

def main():
    """Fully automated BidNet HVAC search"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    print("🤖 Fully Automated BidNet HVAC Search")
    print("=" * 40)
    print("This script will:")
    print("• Automatically log in to BidNet")
    print("• Search for HVAC contracts")
    print("• Extract all results from all pages")
    print("• Save to Excel with full BidNet URLs")
    print("")
    
    search_term = input("🔍 Enter search term (default: hvac): ").strip() or "hvac"
    
    driver = setup_browser()
    
    try:
        # Step 1: Ensure authentication
        logger.info("🔐 Step 1: Authenticating...")
        if not ensure_authentication(driver):
            print("❌ Authentication failed. Check your credentials in .env file!")
            return 1
        
        # Step 2: Perform search
        logger.info(f"🔍 Step 2: Searching for '{search_term}'...")
        if not perform_search(driver, search_term):
            print("❌ Search failed!")
            return 1
        
        # Step 3: Try to increase results per page
        logger.info("🔧 Step 3: Optimizing results per page...")
        set_results_per_page(driver)
        
        # Step 4: Extract all contracts from all pages
        logger.info("📊 Step 4: Extracting contracts from all pages...")
        all_contracts = get_all_pages_contracts(driver)
        
        if all_contracts:
            logger.info(f"✅ Found {len(all_contracts)} total contracts!")
            
            # Filter for HVAC relevance
            hvac_contracts = [c for c in all_contracts 
                            if c['hvac_relevance_score'] > 0 and not c['has_negative_terms']]
            
            logger.info(f"🎯 {len(hvac_contracts)} relevant HVAC contracts after filtering")
            
            # Save to Excel
            filepath = save_to_excel(all_contracts, search_term)
            logger.info(f"💾 Results saved to: {filepath}")
            
            # Show summary by page
            from collections import Counter
            page_counts = Counter(c['page_number'] for c in all_contracts)
            print(f"\n📊 CONTRACTS BY PAGE:")
            for page, count in sorted(page_counts.items()):
                print(f"   Page {page}: {count} contracts")
            
            # Show sample results
            print(f"\n📋 SAMPLE RESULTS:")
            for i, contract in enumerate(all_contracts[:5]):
                print(f"\n{i+1}. {contract['title'][:80]}")
                print(f"   Page: {contract['page_number']}")
                print(f"   HVAC Score: {contract['hvac_relevance_score']}")
                print(f"   URL: {contract['url'] or 'No URL'}")
            
            # Open Excel file
            import subprocess
            subprocess.run(['open', filepath])
            print(f"\n🎉 Excel file opened automatically!")
            
            return 0
            
        else:
            logger.warning("❌ No contracts found")
            return 1
            
    except KeyboardInterrupt:
        print("\n⏹️ Search stopped by user")
        return 0
    
    finally:
        driver.quit()

if __name__ == "__main__":
    exit(main())