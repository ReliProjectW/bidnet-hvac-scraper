#!/usr/bin/env python3
"""
Debug script to understand what's happening with the login button
"""

import logging
from config import Config
from playwright.sync_api import sync_playwright

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_login_button():
    """Debug the login button situation"""
    playwright = sync_playwright().start()
    
    try:
        browser = playwright.chromium.launch(headless=False)  # Show browser
        context = browser.new_context()
        page = context.new_page()
        
        # Navigate to main page
        logger.info("Navigating to main page...")
        page.goto(Config.BASE_URL)
        page.wait_for_load_state("networkidle")
        
        logger.info(f"Page title: {page.title()}")
        logger.info(f"Current URL: {page.url}")
        
        # Wait 5 seconds like before
        logger.info("Waiting 5 seconds...")
        page.wait_for_timeout(5000)
        
        # Take screenshot
        page.screenshot(path="debug_page_loaded.png")
        logger.info("Screenshot saved as debug_page_loaded.png")
        
        # Check if button exists
        button_exists = page.locator("#header_btnLogin").count()
        logger.info(f"Login button count: {button_exists}")
        
        if button_exists > 0:
            button = page.locator("#header_btnLogin")
            logger.info(f"Button is visible: {button.is_visible()}")
            logger.info(f"Button is enabled: {button.is_enabled()}")
            
            # Get button attributes
            try:
                data_href = button.get_attribute("data-href")
                logger.info(f"Button data-href: {data_href}")
            except:
                logger.info("Could not get data-href attribute")
            
            # Try to get all button HTML
            try:
                button_html = button.inner_html()
                logger.info(f"Button HTML: {button_html}")
            except:
                logger.info("Could not get button HTML")
                
        # Check for any JavaScript errors
        page.on("console", lambda msg: logger.info(f"Console: {msg.text}"))
        
        # Wait a bit more and try clicking
        logger.info("Trying to click button...")
        try:
            page.evaluate("document.getElementById('header_btnLogin').click()")
            logger.info("JavaScript click executed")
            page.wait_for_timeout(3000)
            logger.info(f"URL after click: {page.url}")
        except Exception as e:
            logger.error(f"Click failed: {e}")
        
        # Keep browser open for manual inspection
        input("Press Enter to close browser...")
        
    finally:
        browser.close()
        playwright.stop()

if __name__ == "__main__":
    debug_login_button()