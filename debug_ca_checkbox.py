#!/usr/bin/env python3
"""
Debug California Purchasing Group checkbox
Opens browser, logs in, goes to search page, expands dropdown, then pauses for manual inspection
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

def debug_ca_checkbox():
    """Debug CA checkbox - open browser and pause for manual inspection"""
    
    # Setup Chrome driver - NOT headless so you can see and inspect
    options = Options()
    options.add_argument("--window-size=1920,1080")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        # Create authenticator and navigate with auto-login
        auth = BidNetAuthenticator()
        search_url = f"{Config.BASE_URL}private/supplier/solicitations/search"
        
        print("🔍 Navigating to search page...")
        driver.get(search_url)
        time.sleep(3)
        
        # Auto-login if needed
        print("🔐 Attempting auto-login...")
        if not auth.auto_login_if_needed(driver):
            print("❌ Auto-login failed")
            return
        
        # Navigate to search page again if needed
        if driver.current_url != search_url:
            print("📍 Re-navigating to search page after login...")
            driver.get(search_url)
            time.sleep(3)
            
        print("✅ On search page successfully")
        
        # Enter HVAC in search field
        print("🔍 Finding and filling search field...")
        search_selectors = [
            'textarea#solicitationSingleBoxSearch',
            'textarea[name="keywords"]'
        ]
        
        search_field = None
        for selector in search_selectors:
            try:
                search_field = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except:
                continue
                
        if search_field:
            search_field.clear()
            search_field.send_keys("HVAC")
            print("✅ Entered 'HVAC' in search field")
        
        # Expand Purchasing Group dropdown
        print("📂 Expanding Purchasing Group dropdown...")
        dropdown_selectors = [
            'div#panelsolicitationPurchasingGroupId',
            'div[data-filter-section="solicitationPurchasingGroupId"]'
        ]
        
        for dropdown_selector in dropdown_selectors:
            try:
                dropdown = driver.find_element(By.CSS_SELECTOR, dropdown_selector)
                dropdown_classes = dropdown.get_attribute('class') or ''
                
                if 'collapsed' in dropdown_classes.lower():
                    print("🔄 Dropdown is collapsed, expanding...")
                    # Find the header to click
                    toggle_selectors = ['div.mets-panel-header', '.mets-panel-toggleable']
                    for toggle_sel in toggle_selectors:
                        try:
                            toggle = dropdown.find_element(By.CSS_SELECTOR, toggle_sel)
                            driver.execute_script("arguments[0].scrollIntoView(true);", toggle)
                            time.sleep(1)
                            toggle.click()
                            time.sleep(3)
                            print("✅ Purchasing Group dropdown expanded")
                            break
                        except:
                            continue
                else:
                    print("✅ Purchasing Group dropdown already expanded")
                break
            except:
                continue
        
        print("\n" + "="*60)
        print("🔍 MANUAL INSPECTION TIME!")
        print("="*60)
        print("The browser is now ready for inspection:")
        print()
        print("1. Look for the California Purchasing Group checkbox")
        print("2. Right-click on it and 'Inspect Element'")
        print("3. Copy the exact HTML attributes:")
        print("   - name='?' ")
        print("   - value='?'")
        print("   - id='?'")
        print("   - Any other relevant attributes")
        print()
        print("4. Try clicking the checkbox manually to verify it works")
        print("5. Note what happens to the search results count")
        print()
        print("Current URL:", driver.current_url)
        print()
        
        # Show current checkboxes for reference
        try:
            checkboxes = driver.find_elements(By.CSS_SELECTOR, 'input[type="checkbox"]')
            print(f"Found {len(checkboxes)} total checkboxes on the page")
            
            # Look for any with California or 88020151 value
            for i, checkbox in enumerate(checkboxes):
                value = checkbox.get_attribute('value') or ''
                name = checkbox.get_attribute('name') or ''
                if 'california' in name.lower() or value == '88020151':
                    print(f"🎯 Potential CA checkbox: name='{name}', value='{value}'")
        except Exception as e:
            print(f"Error listing checkboxes: {e}")
        
        print("\n📋 When ready, press Enter to close the browser...")
        input()
        
    except Exception as e:
        print(f"Error: {e}")
        print("\n📋 Press Enter to close browser...")
        input()
        
    finally:
        driver.quit()

if __name__ == "__main__":
    debug_ca_checkbox()