#!/usr/bin/env python3
"""
Debug login - see what's actually on the page
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

def debug_login_page():
    """Debug what's on the login page"""
    
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
        wait = WebDriverWait(driver, 20)
        
        # Navigate to main page
        driver.get(Config.BASE_URL)
        print(f"Main page title: {driver.title}")
        print(f"Main page URL: {driver.current_url}")
        
        # Find login link
        login_link = None
        login_selectors = [
            "a[href*='login']",
            "a:contains('Login')", 
            ".login",
            "#login"
        ]
        
        for selector in login_selectors:
            try:
                login_link = driver.find_element(By.CSS_SELECTOR, selector)
                print(f"Found login link with selector: {selector}")
                break
            except:
                continue
                
        if login_link:
            print(f"Login link text: '{login_link.text}'")
            print(f"Login link href: {login_link.get_attribute('href')}")
            
            # Click login
            driver.execute_script("arguments[0].click();", login_link)
            time.sleep(3)
            
            print(f"\nAfter login click:")
            print(f"URL: {driver.current_url}")
            print(f"Title: {driver.title}")
            
            # Get page source snippet
            page_source = driver.page_source
            print(f"\nPage source length: {len(page_source)}")
            
            # Look for forms
            forms = driver.find_elements(By.TAG_NAME, "form")
            print(f"\nFound {len(forms)} forms on page")
            
            # Look for input fields
            inputs = driver.find_elements(By.TAG_NAME, "input")
            print(f"Found {len(inputs)} input fields:")
            for i, inp in enumerate(inputs[:10]):  # First 10 inputs
                print(f"  Input {i+1}: type='{inp.get_attribute('type')}', name='{inp.get_attribute('name')}', id='{inp.get_attribute('id')}'")
                
            # Check if we need to wait longer or if there's a loading state
            print("\nWaiting 5 more seconds to see if page changes...")
            time.sleep(5)
            
            # Check again
            inputs2 = driver.find_elements(By.TAG_NAME, "input")
            if len(inputs2) != len(inputs):
                print(f"Now found {len(inputs2)} input fields (changed!)")
                for i, inp in enumerate(inputs2[:10]):
                    print(f"  Input {i+1}: type='{inp.get_attribute('type')}', name='{inp.get_attribute('name')}', id='{inp.get_attribute('id')}'")
        else:
            print("Could not find login link!")
            
    except Exception as e:
        print(f"Error: {e}")
        
    finally:
        input("Press Enter to close browser...")
        driver.quit()

if __name__ == "__main__":
    debug_login_page()