#!/usr/bin/env python3
"""
Test 3: HVAC Keyword Search Functionality
Tests entering "hvac" in search bar and pressing search
"""

import logging
import time
from config import Config
from src.auth.bidnet_auth import BidNetAuthenticator
from playwright.sync_api import sync_playwright

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_hvac_search():
    """Test HVAC keyword search functionality"""
    logger.info("🧪 Starting Test 3: HVAC Keyword Search")
    
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
        
        # Save page HTML for debugging
        page_html = page.content()
        debug_file = f"{Config.DATA_DIR}/debug_hvac_search_page.html"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(page_html)
        logger.info(f"Saved page HTML for debugging: {debug_file}")
        
        # Look for search input field
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
        
        if search_element:
            logger.info("✅ Search field found!")
            
            # Clear and enter "hvac"
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
            
            # Look for search button
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
                
                # Click the search button
                search_button.click()
                
                # Wait for search results to load
                logger.info("Waiting for search results...")
                page.wait_for_load_state("networkidle")
                time.sleep(3)  # Extra wait for dynamic content
                
                # Check if we got results
                current_url = page.url
                logger.info(f"Current URL after search: {current_url}")
                
                # Save results page for debugging
                results_html = page.content()
                debug_file = f"{Config.DATA_DIR}/debug_hvac_search_results.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(results_html)
                logger.info(f"Saved search results HTML: {debug_file}")
                
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
                for indicator in results_indicators:
                    try:
                        elements = page.locator(indicator).all()
                        visible_elements = [el for el in elements if el.is_visible(timeout=500)]
                        if len(visible_elements) > 1:  # More than just header
                            logger.info(f"✅ Found {len(visible_elements)} result elements using '{indicator}'")
                            found_results = True
                            break
                    except Exception as e:
                        logger.debug(f"Results indicator '{indicator}' check failed: {e}")
                        continue
                
                if found_results:
                    logger.info("✅ Search results found!")
                    
                    # Check for "No results" or similar messages
                    no_results_patterns = ["no results", "no records", "0 results", "nothing found"]
                    page_text = page.content().lower()
                    
                    has_no_results = any(pattern in page_text for pattern in no_results_patterns)
                    
                    if has_no_results:
                        logger.warning("⚠️ Search completed but returned no results")
                    else:
                        logger.info("✅ Search completed with results!")
                    
                    return True
                    
                else:
                    logger.error("❌ No search results found on page")
                    return False
                    
            else:
                logger.info("⚠️ No search button found - trying Enter key...")
                
                # Try pressing Enter on search field
                search_element.press("Enter")
                
                # Wait for results
                page.wait_for_load_state("networkidle")
                time.sleep(3)
                
                # Check if URL changed (indicating search was submitted)
                new_url = page.url
                if new_url != search_url:
                    logger.info("✅ Search submitted via Enter key!")
                    return True
                else:
                    logger.error("❌ Enter key didn't trigger search")
                    return False
                    
        else:
            logger.error("❌ Search field not found")
            
            # List all input fields for debugging
            logger.info("Available input fields on the page:")
            all_inputs = page.locator('input, textarea').all()
            for i, input_field in enumerate(all_inputs[:15]):  # Show first 15
                try:
                    if input_field.is_visible(timeout=500):
                        input_html = input_field.evaluate("el => el.outerHTML")
                        logger.info(f"Input {i+1}: {input_html[:150]}...")
                except:
                    continue
            
            return False
            
    except Exception as e:
        logger.error(f"❌ HVAC search test ERROR: {str(e)}")
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
        
        logger.info("Test 3 complete")

if __name__ == "__main__":
    success = test_hvac_search()
    if success:
        logger.info("✅ Test 3 PASSED")
    else:
        logger.error("❌ Test 3 FAILED")