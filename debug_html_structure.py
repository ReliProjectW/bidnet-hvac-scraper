#!/usr/bin/env python3
"""
Debug HTML Structure - Save actual BidNet search results for inspection
"""

import os
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def debug_search_results():
    """Save search results HTML for manual inspection"""
    print("🔍 Debugging BidNet HTML structure...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        try:
            # Login
            print("🔐 Logging in...")
            page.goto("https://www.bidnetdirect.com/public/authentication/login")
            page.wait_for_timeout(3000)
            
            # Handle cookie banner if present
            try:
                cookie_accept = page.query_selector('.cookie-banner button')
                if cookie_accept:
                    cookie_accept.click()
                    page.wait_for_timeout(1000)
            except:
                pass
            
            username = os.getenv("BIDNET_USERNAME")
            password = os.getenv("BIDNET_PASSWORD")
            
            page.fill("input[name='j_username']", username)
            page.fill("input[name='j_password']", password)
            page.click("button[type='submit']")
            page.wait_for_timeout(10000)
            
            print("✅ Login complete")
            
            # Navigate and search
            print("🔍 Searching for HVAC...")
            page.goto("https://www.bidnetdirect.com/private/supplier/solicitations/search")
            page.wait_for_timeout(5000)
            
            # Handle cookie banner again if needed
            try:
                cookie_accept = page.query_selector('.cookie-banner button')
                if cookie_accept:
                    cookie_accept.click()
                    page.wait_for_timeout(1000)
            except:
                pass
            
            search_field = page.wait_for_selector("textarea#solicitationSingleBoxSearch", timeout=10000)
            search_field.fill("hvac")
            
            search_button = page.wait_for_selector("button#topSearchButton", timeout=10000)
            search_button.click()
            page.wait_for_timeout(8000)  # Wait longer for results
            
            print("💾 Saving HTML for inspection...")
            
            # Save full page HTML
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            html_file = f"data/debug_search_results_{timestamp}.html"
            
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(page.content())
            
            print(f"📄 Full page HTML saved: {html_file}")
            
            # Try to find any table-like structures
            print("🔍 Analyzing page structure...")
            
            # Check different selectors
            selectors_to_try = [
                '[class*="table-row"]',
                '[class*="result"]', 
                '[class*="solicitation"]',
                'tr',
                '.search-result',
                '[data-testid]'
            ]
            
            for selector in selectors_to_try:
                try:
                    elements = page.query_selector_all(selector)
                    print(f"  {selector}: Found {len(elements)} elements")
                    
                    if elements and len(elements) > 0:
                        # Sample first few elements
                        for i, elem in enumerate(elements[:3]):
                            text = elem.inner_text()[:100].replace('\\n', ' ')
                            print(f"    Element {i+1}: {text}...")
                except Exception as e:
                    print(f"    {selector}: Error - {e}")
            
            # Look for links specifically
            print("\\n🔗 Looking for contract links...")
            links = page.query_selector_all('a[href*="solicitation"]')
            print(f"Found {len(links)} solicitation links:")
            for i, link in enumerate(links[:5]):
                try:
                    text = link.inner_text().strip()
                    href = link.get_attribute('href')
                    print(f"  Link {i+1}: {text[:50]}... -> {href}")
                except:
                    pass
            
            # Take a screenshot
            screenshot_file = f"data/debug_search_screenshot_{timestamp}.png"
            page.screenshot(path=screenshot_file)
            print(f"📸 Screenshot saved: {screenshot_file}")
            
            print("\\n🎯 Manual inspection needed:")
            print(f"1. Open {html_file} in browser")
            print(f"2. Check {screenshot_file}")
            print("3. Look for actual contract data structure")
            print("4. Update selectors in improved_contract_extractor.py")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    debug_search_results()