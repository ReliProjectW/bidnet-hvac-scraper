#!/usr/bin/env python3
"""
Search Field Inspector
Find and analyze search fields on the BidNet search page
"""

import sys
import logging
import json
import time
from pathlib import Path
from datetime import datetime

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from config import Config

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
        logger.error("❌ No saved cookies found. Run login_only.py first!")
        return False
    
    try:
        with open(cookies_file, 'r') as f:
            cookie_data = json.load(f)
        
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

def analyze_search_fields(driver):
    """Analyze all possible search fields on the page"""
    logger = logging.getLogger(__name__)
    
    # Navigate to search page
    search_url = f"{Config.BASE_URL}private/supplier/solicitations/search"
    driver.get(search_url)
    time.sleep(3)
    
    print(f"\n🔍 ANALYZING SEARCH PAGE: {driver.current_url}")
    print("=" * 80)
    
    # Get page source
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    
    # Find ALL input fields
    print("\n📝 ALL INPUT FIELDS ON PAGE:")
    print("-" * 40)
    
    inputs = soup.find_all('input')
    for i, inp in enumerate(inputs, 1):
        input_type = inp.get('type', 'text')
        input_name = inp.get('name', 'N/A')
        input_id = inp.get('id', 'N/A')
        input_class = ' '.join(inp.get('class', []))
        input_placeholder = inp.get('placeholder', 'N/A')
        input_value = inp.get('value', 'N/A')
        
        print(f"\n  INPUT {i}:")
        print(f"    Type: {input_type}")
        print(f"    Name: {input_name}")
        print(f"    ID: {input_id}")
        print(f"    Class: {input_class}")
        print(f"    Placeholder: {input_placeholder}")
        print(f"    Value: {input_value}")
        
        # Check if this looks like a search field
        search_indicators = []
        if 'search' in input_name.lower():
            search_indicators.append("name contains 'search'")
        if 'search' in input_id.lower():
            search_indicators.append("id contains 'search'")
        if 'search' in input_class.lower():
            search_indicators.append("class contains 'search'")
        if 'search' in input_placeholder.lower():
            search_indicators.append("placeholder contains 'search'")
        if 'keyword' in input_name.lower():
            search_indicators.append("name contains 'keyword'")
        if 'query' in input_name.lower():
            search_indicators.append("name contains 'query'")
        
        if search_indicators:
            print(f"    🎯 POSSIBLE SEARCH FIELD: {', '.join(search_indicators)}")
    
    # Find ALL forms
    print(f"\n📋 ALL FORMS ON PAGE:")
    print("-" * 40)
    
    forms = soup.find_all('form')
    for i, form in enumerate(forms, 1):
        form_action = form.get('action', 'N/A')
        form_method = form.get('method', 'GET')
        form_id = form.get('id', 'N/A')
        form_class = ' '.join(form.get('class', []))
        
        print(f"\n  FORM {i}:")
        print(f"    Action: {form_action}")
        print(f"    Method: {form_method}")
        print(f"    ID: {form_id}")
        print(f"    Class: {form_class}")
        
        # Find inputs in this form
        form_inputs = form.find_all('input')
        print(f"    Inputs in form: {len(form_inputs)}")
        for j, inp in enumerate(form_inputs, 1):
            inp_type = inp.get('type', 'text')
            inp_name = inp.get('name', 'N/A')
            inp_placeholder = inp.get('placeholder', 'N/A')
            print(f"      Input {j}: type={inp_type}, name={inp_name}, placeholder={inp_placeholder}")
    
    # Try to find elements using Selenium that might be search fields
    print(f"\n🔍 SELENIUM ELEMENT DETECTION:")
    print("-" * 40)
    
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
        'input[type="search"]',
        'input[type="text"]'  # Try all text inputs
    ]
    
    for selector in search_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"\n  ✅ FOUND {len(elements)} elements with selector: {selector}")
                for i, elem in enumerate(elements, 1):
                    try:
                        tag_name = elem.tag_name
                        is_displayed = elem.is_displayed()
                        is_enabled = elem.is_enabled()
                        location = elem.location
                        size = elem.size
                        
                        print(f"    Element {i}:")
                        print(f"      Tag: {tag_name}")
                        print(f"      Displayed: {is_displayed}")
                        print(f"      Enabled: {is_enabled}")
                        print(f"      Location: {location}")
                        print(f"      Size: {size}")
                        
                        # Try to get attributes
                        try:
                            name = elem.get_attribute('name')
                            elem_id = elem.get_attribute('id')
                            placeholder = elem.get_attribute('placeholder')
                            elem_class = elem.get_attribute('class')
                            
                            print(f"      Name: {name}")
                            print(f"      ID: {elem_id}")
                            print(f"      Placeholder: {placeholder}")
                            print(f"      Class: {elem_class}")
                        except Exception as e:
                            print(f"      Error getting attributes: {e}")
                            
                    except Exception as e:
                        print(f"    Error analyzing element {i}: {e}")
            else:
                print(f"  ❌ No elements found for: {selector}")
        except Exception as e:
            print(f"  ❌ Error with selector '{selector}': {e}")
    
    # Save page source for manual inspection
    debug_file = f"data/search_page_debug_{datetime.now().strftime('%H%M%S')}.html"
    with open(debug_file, 'w', encoding='utf-8') as f:
        f.write(page_source)
    print(f"\n💾 Saved page source to: {debug_file}")
    
    print(f"\n🎯 RECOMMENDATIONS:")
    print("Based on this analysis, look for:")
    print("1. Input fields that are displayed and enabled")
    print("2. Fields with search-related names, IDs, or placeholders")
    print("3. Fields inside forms that might handle search")
    print("4. Check the saved HTML file for more details")

def main():
    """Main search field inspector"""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    print("🔍 Search Field Inspector")
    print("=" * 30)
    print("This tool will analyze the BidNet search page to find search fields.")
    print("")
    
    driver = setup_browser()
    
    try:
        # Load authentication
        if not load_saved_cookies(driver):
            print("❌ Cannot load authentication cookies. Run login_only.py first!")
            return 1
        
        print("✅ Authentication loaded. Analyzing search page...")
        
        # Analyze search fields
        analyze_search_fields(driver)
        
        print(f"\n✅ Analysis complete!")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Error during analysis: {e}")
        return 1
    
    finally:
        driver.quit()

if __name__ == "__main__":
    exit(main())