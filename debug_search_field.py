#!/usr/bin/env python3
"""
Debug script to identify search field elements on BidNet search page
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

def debug_search_page():
    """Debug search page to identify search field elements"""
    logger.info("🔍 Starting search page debug")
    
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
        
        # Initialize authenticator
        authenticator = BidNetAuthenticator()
        authenticator.page = page
        authenticator.context = context
        authenticator.browser = browser
        
        # Login first
        logger.info("🔑 Logging in...")
        login_url = "https://www.bidnetdirect.com/public/authentication/login"
        page.goto(login_url)
        page.wait_for_load_state("domcontentloaded", timeout=15000)
        page.wait_for_timeout(3000)
        
        if not authenticator._perform_login_on_current_page():
            logger.error("❌ Login failed")
            return False
        
        logger.info("✅ Login successful")
        
        # Navigate to search page
        search_url = f"{Config.BASE_URL}private/supplier/solicitations/search"
        logger.info(f"🔍 Navigating to search page: {search_url}")
        page.goto(search_url)
        page.wait_for_load_state("networkidle")
        
        # Check if redirected to login
        if authenticator.is_login_page(page):
            logger.info("🔑 Redirected to login, performing auto-login...")
            if not authenticator.auto_login_if_needed(page):
                logger.error("❌ Auto-login failed")
                return False
            page.goto(search_url)
            page.wait_for_load_state("networkidle")
        
        logger.info(f"Current URL: {page.url}")
        
        # Save full page HTML
        page_html = page.content()
        debug_file = f"{Config.DATA_DIR}/debug_search_page_full.html"
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(page_html)
        logger.info(f"📄 Saved full page HTML: {debug_file}")
        
        # Take screenshot
        screenshot_file = f"{Config.DATA_DIR}/debug_search_page_screenshot.png"
        page.screenshot(path=screenshot_file, full_page=True)
        logger.info(f"📸 Saved screenshot: {screenshot_file}")
        
        # List ALL input fields and textareas
        logger.info("🔍 ANALYZING ALL INPUT FIELDS:")
        logger.info("=" * 80)
        
        all_inputs = page.locator('input').all()
        all_textareas = page.locator('textarea').all()
        
        logger.info(f"Found {len(all_inputs)} input elements and {len(all_textareas)} textarea elements")
        logger.info("")
        
        # Analyze input fields
        logger.info("INPUT FIELDS:")
        logger.info("-" * 40)
        for i, input_field in enumerate(all_inputs):
            try:
                is_visible = input_field.is_visible(timeout=500)
                if is_visible:
                    input_html = input_field.evaluate("el => el.outerHTML")
                    input_type = input_field.get_attribute("type") or "text"
                    input_name = input_field.get_attribute("name") or ""
                    input_id = input_field.get_attribute("id") or ""
                    input_class = input_field.get_attribute("class") or ""
                    input_placeholder = input_field.get_attribute("placeholder") or ""
                    
                    logger.info(f"Input #{i+1} (VISIBLE):")
                    logger.info(f"  Type: {input_type}")
                    logger.info(f"  Name: {input_name}")
                    logger.info(f"  ID: {input_id}")
                    logger.info(f"  Class: {input_class}")
                    logger.info(f"  Placeholder: {input_placeholder}")
                    logger.info(f"  HTML: {input_html[:200]}...")
                    logger.info("")
                else:
                    logger.debug(f"Input #{i+1} (HIDDEN)")
            except Exception as e:
                logger.debug(f"Error analyzing input #{i+1}: {e}")
        
        # Analyze textarea fields
        logger.info("TEXTAREA FIELDS:")
        logger.info("-" * 40)
        for i, textarea in enumerate(all_textareas):
            try:
                is_visible = textarea.is_visible(timeout=500)
                if is_visible:
                    textarea_html = textarea.evaluate("el => el.outerHTML")
                    textarea_name = textarea.get_attribute("name") or ""
                    textarea_id = textarea.get_attribute("id") or ""
                    textarea_class = textarea.get_attribute("class") or ""
                    textarea_placeholder = textarea.get_attribute("placeholder") or ""
                    
                    logger.info(f"Textarea #{i+1} (VISIBLE):")
                    logger.info(f"  Name: {textarea_name}")
                    logger.info(f"  ID: {textarea_id}")
                    logger.info(f"  Class: {textarea_class}")
                    logger.info(f"  Placeholder: {textarea_placeholder}")
                    logger.info(f"  HTML: {textarea_html[:200]}...")
                    logger.info("")
                else:
                    logger.debug(f"Textarea #{i+1} (HIDDEN)")
            except Exception as e:
                logger.debug(f"Error analyzing textarea #{i+1}: {e}")
        
        # Look for buttons that might be search buttons
        logger.info("BUTTON ELEMENTS (potential search buttons):")
        logger.info("-" * 40)
        all_buttons = page.locator('button').all()
        for i, button in enumerate(all_buttons):
            try:
                is_visible = button.is_visible(timeout=500)
                if is_visible:
                    button_text = button.text_content() or ""
                    button_type = button.get_attribute("type") or ""
                    button_id = button.get_attribute("id") or ""
                    button_class = button.get_attribute("class") or ""
                    
                    if any(keyword in button_text.lower() for keyword in ["search", "find", "go"]) or \
                       any(keyword in button_id.lower() for keyword in ["search", "find"]) or \
                       any(keyword in button_class.lower() for keyword in ["search", "find"]):
                        button_html = button.evaluate("el => el.outerHTML")
                        logger.info(f"Button #{i+1} (VISIBLE, likely search):")
                        logger.info(f"  Text: '{button_text}'")
                        logger.info(f"  Type: {button_type}")
                        logger.info(f"  ID: {button_id}")
                        logger.info(f"  Class: {button_class}")
                        logger.info(f"  HTML: {button_html[:200]}...")
                        logger.info("")
            except Exception as e:
                logger.debug(f"Error analyzing button #{i+1}: {e}")
        
        # Check for form elements
        logger.info("FORM ELEMENTS:")
        logger.info("-" * 40)
        all_forms = page.locator('form').all()
        for i, form in enumerate(all_forms):
            try:
                is_visible = form.is_visible(timeout=500)
                if is_visible:
                    form_action = form.get_attribute("action") or ""
                    form_method = form.get_attribute("method") or ""
                    form_id = form.get_attribute("id") or ""
                    form_class = form.get_attribute("class") or ""
                    
                    logger.info(f"Form #{i+1} (VISIBLE):")
                    logger.info(f"  Action: {form_action}")
                    logger.info(f"  Method: {form_method}")
                    logger.info(f"  ID: {form_id}")
                    logger.info(f"  Class: {form_class}")
                    logger.info("")
            except Exception as e:
                logger.debug(f"Error analyzing form #{i+1}: {e}")
        
        logger.info("=" * 80)
        logger.info("🔍 Debug complete! Check the files and logs above to identify the search field.")
        logger.info(f"📄 HTML file: {debug_file}")
        logger.info(f"📸 Screenshot: {screenshot_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Debug ERROR: {str(e)}")
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

if __name__ == "__main__":
    success = debug_search_page()
    if success:
        logger.info("✅ Debug completed successfully")
    else:
        logger.error("❌ Debug failed")