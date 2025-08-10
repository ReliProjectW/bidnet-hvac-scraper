#!/usr/bin/env python3
"""
Test 2: California Purchasing Group Checkbox Verification
Tests finding and checking the California purchasing group checkbox
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

def test_california_checkbox():
    """Test California purchasing group checkbox functionality"""
    logger.info("🧪 Starting Test 2: California Purchasing Group Checkbox")
    
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
        
        # Navigate to search page to find filters
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
        debug_file = f"{Config.DATA_DIR}/debug_ca_checkbox_page.html"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(page_html)
        logger.info(f"Saved page HTML for debugging: {debug_file}")
        
        # Look for California purchasing group checkbox
        ca_checkbox = None
        ca_selectors = [
            # Specific California selectors
            'input[value*="California"]',
            'input[name*="california"]',
            'input[id*="california"]',
            'input[data-value*="California"]',
            
            # Generic checkbox patterns near "California" text
            'input[type="checkbox"]:near(text="California")',
            'input[type="checkbox"] ~ label:has-text("California")',
            'label:has-text("California") input[type="checkbox"]',
            
            # Purchasing group patterns
            'input[value*="CA Purchasing"]',
            'input[value*="California Purchasing"]',
            'input[name*="purchasing"][value*="CA"]',
            
            # Generic checkbox selectors
            'input[type="checkbox"][name*="location"]',
            'input[type="checkbox"][name*="region"]',
            'input[type="checkbox"][name*="state"]',
            'input[type="checkbox"][name*="filter"]'
        ]
        
        for selector in ca_selectors:
            try:
                elements = page.locator(selector).all()
                for element in elements:
                    if element.is_visible(timeout=1000):
                        # Check if this checkbox is related to California
                        element_html = element.evaluate("el => el.outerHTML")
                        nearby_text = element.evaluate("""
                            el => {
                                const parent = el.closest('div, li, tr, label') || el.parentElement;
                                return parent ? parent.textContent : '';
                            }
                        """)
                        
                        if "california" in (element_html + nearby_text).lower():
                            ca_checkbox = element
                            logger.info(f"Found California checkbox with selector: {selector}")
                            logger.info(f"Checkbox HTML: {element_html}")
                            logger.info(f"Nearby text: {nearby_text}")
                            break
            except Exception as e:
                logger.debug(f"Selector '{selector}' failed: {e}")
                continue
            
            if ca_checkbox:
                break
        
        if ca_checkbox:
            logger.info("✅ California checkbox found!")
            
            # Check if it's already checked
            is_checked = ca_checkbox.is_checked()
            logger.info(f"Checkbox current state: {'checked' if is_checked else 'unchecked'}")
            
            # If not checked, check it
            if not is_checked:
                logger.info("Checking the California checkbox...")
                ca_checkbox.check()
                
                # Verify it got checked
                time.sleep(1)
                is_checked_after = ca_checkbox.is_checked()
                if is_checked_after:
                    logger.info("✅ California checkbox successfully checked!")
                    return True
                else:
                    logger.error("❌ Failed to check California checkbox")
                    return False
            else:
                logger.info("✅ California checkbox was already checked!")
                return True
                
        else:
            logger.error("❌ California purchasing group checkbox not found")
            
            # List all visible checkboxes for debugging
            logger.info("Available checkboxes on the page:")
            all_checkboxes = page.locator('input[type="checkbox"]').all()
            for i, checkbox in enumerate(all_checkboxes[:10]):  # Show first 10
                try:
                    if checkbox.is_visible(timeout=500):
                        checkbox_html = checkbox.evaluate("el => el.outerHTML")
                        nearby_text = checkbox.evaluate("""
                            el => {
                                const parent = el.closest('div, li, tr, label') || el.parentElement;
                                return parent ? parent.textContent.substring(0, 100) : '';
                            }
                        """)
                        logger.info(f"Checkbox {i+1}: {checkbox_html[:100]}... | Nearby: {nearby_text}")
                except:
                    continue
            
            return False
            
    except Exception as e:
        logger.error(f"❌ California checkbox test ERROR: {str(e)}")
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
        
        logger.info("Test 2 complete")

if __name__ == "__main__":
    success = test_california_checkbox()
    if success:
        logger.info("✅ Test 2 PASSED")
    else:
        logger.error("❌ Test 2 FAILED")