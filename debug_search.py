#!/usr/bin/env python3
"""
Debug search page - see what search fields are actually available
"""

import sys
import time
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from config import Config
from auth.bidnet_auth import BidNetAuthenticator

def debug_search_page():
    """Debug what's on the search page after successful login"""
    
    # Setup Chrome driver
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    try:
        # Create authenticator and use auto-login
        auth = BidNetAuthenticator()
        wait = WebDriverWait(driver, 20)
        
        # Navigate to search page
        search_url = f"{Config.BASE_URL}private/supplier/solicitations/search"
        print(f"Navigating to: {search_url}")
        driver.get(search_url)
        
        time.sleep(3)
        print(f"Current URL: {driver.current_url}")
        print(f"Page title: {driver.title}")
        
        # Use auto-login if needed
        if not auth.auto_login_if_needed(driver):
            print("❌ Auto-login failed")
            return
        
        # Navigate to search page again if needed
        if driver.current_url != search_url:
            print("Re-navigating to search page after login")
            driver.get(search_url)
            time.sleep(3)
            
        print(f"\n✅ After login - URL: {driver.current_url}")
        print(f"✅ After login - Title: {driver.title}")
        
        # Look for ALL input fields
        all_inputs = driver.find_elements(By.TAG_NAME, "input")
        print(f"\n🔍 Found {len(all_inputs)} input fields:")
        for i, inp in enumerate(all_inputs):
            input_type = inp.get_attribute('type') or 'text'
            input_name = inp.get_attribute('name') or ''
            input_id = inp.get_attribute('id') or ''
            input_class = inp.get_attribute('class') or ''
            input_placeholder = inp.get_attribute('placeholder') or ''
            print(f"  Input {i+1}: type='{input_type}', name='{input_name}', id='{input_id}', class='{input_class}', placeholder='{input_placeholder}'")
        
        # Look for specific search-related fields
        search_selectors = [
            'input[name*="search"]',
            'input[name*="keyword"]',
            'input[name*="term"]',
            'input[placeholder*="search"]',
            'input[placeholder*="keyword"]',
            '.search-input',
            '#search',
            '#keyword'
        ]
        
        print(f"\n🎯 Testing search selectors:")
        search_field = None
        for selector in search_selectors:
            try:
                field = driver.find_element(By.CSS_SELECTOR, selector)
                print(f"  ✅ Found with '{selector}': {field.get_attribute('outerHTML')[:100]}...")
                if not search_field:
                    search_field = field
            except:
                print(f"  ❌ Not found: '{selector}'")
        
        # If we found a search field, try to use it
        if search_field:
            print(f"\n🧪 Testing search field input...")
            try:
                search_field.click()
                time.sleep(1)
                search_field.clear()
                time.sleep(1)
                search_field.send_keys("HVAC")
                print("✅ Successfully entered 'HVAC' in search field")
                
                # Look for search button
                button_selectors = [
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'button:contains("Search")',
                    '.search-button',
                    '#searchButton'
                ]
                
                search_button = None
                for selector in button_selectors:
                    try:
                        button = driver.find_element(By.CSS_SELECTOR, selector)
                        print(f"  ✅ Found search button with '{selector}': {button.get_attribute('outerHTML')[:100]}...")
                        if not search_button:
                            search_button = button
                    except:
                        print(f"  ❌ No search button: '{selector}'")
                
                if search_button:
                    print("🔍 Clicking search button...")
                    search_button.click()
                    time.sleep(5)
                    
                    print(f"After search - URL: {driver.current_url}")
                    print(f"After search - Title: {driver.title}")
                    
                    # Look for results
                    results = driver.find_elements(By.CSS_SELECTOR, "div, tr, li")
                    results_with_hvac = [r for r in results if "hvac" in r.text.lower()]
                    print(f"Found {len(results_with_hvac)} elements containing 'hvac'")
                    
                    for i, result in enumerate(results_with_hvac[:5]):
                        print(f"  Result {i+1}: {result.text[:100]}...")
                else:
                    print("❌ No search button found - trying form submit")
                    search_field.submit()
                    time.sleep(5)
                    print(f"After submit - URL: {driver.current_url}")
                    
            except Exception as e:
                print(f"❌ Error testing search: {str(e)}")
        else:
            print("❌ No search field found")
            
            # Save page source for inspection
            with open("debug_search_page.html", "w") as f:
                f.write(driver.page_source)
            print("💾 Saved page source to debug_search_page.html")
            
    except Exception as e:
        print(f"Error: {e}")
        
    finally:
        input("Press Enter to close browser...")
        driver.quit()

if __name__ == "__main__":
    debug_search_page()