#!/usr/bin/env python3
"""
Debug search page - find VISIBLE search fields only
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

def debug_visible_search_fields():
    """Find only VISIBLE search fields on the page"""
    
    # Setup Chrome driver  
    options = Options()
    # Don't use headless so we can see the page
    options.add_argument("--window-size=1920,1080")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    try:
        # Create authenticator and navigate with auto-login
        auth = BidNetAuthenticator()
        search_url = f"{Config.BASE_URL}private/supplier/solicitations/search"
        
        print(f"Navigating to: {search_url}")
        driver.get(search_url)
        time.sleep(3)
        
        # Auto-login if needed
        if not auth.auto_login_if_needed(driver):
            print("❌ Auto-login failed")
            return
        
        # Navigate to search page again if needed
        if driver.current_url != search_url:
            print("Re-navigating to search page after login")
            driver.get(search_url)
            time.sleep(5)  # Give more time to load
            
        print(f"✅ On search page: {driver.current_url}")
        
        # Look for VISIBLE text input fields only
        all_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='search'], input:not([type])")
        visible_inputs = []
        
        for inp in all_inputs:
            if inp.is_displayed() and inp.is_enabled():
                visible_inputs.append(inp)
        
        print(f"\n🔍 Found {len(visible_inputs)} VISIBLE text input fields:")
        
        for i, inp in enumerate(visible_inputs):
            input_name = inp.get_attribute('name') or ''
            input_id = inp.get_attribute('id') or ''
            input_class = inp.get_attribute('class') or ''
            input_placeholder = inp.get_attribute('placeholder') or ''
            input_value = inp.get_attribute('value') or ''
            
            print(f"  Input {i+1}:")
            print(f"    name='{input_name}', id='{input_id}'")
            print(f"    class='{input_class}'")
            print(f"    placeholder='{input_placeholder}'")
            print(f"    current_value='{input_value}'")
            print(f"    location: {inp.location}")
            print(f"    size: {inp.size}")
            print()
        
        # Try to find the main search box by looking for common patterns
        main_search_candidates = []
        
        for inp in visible_inputs:
            # Check if it looks like a main search field
            name = (inp.get_attribute('name') or '').lower()
            id_attr = (inp.get_attribute('id') or '').lower()
            class_attr = (inp.get_attribute('class') or '').lower()
            placeholder = (inp.get_attribute('placeholder') or '').lower()
            
            # Score based on how likely it is to be the main search
            score = 0
            if any(term in name for term in ['search', 'keyword', 'query', 'term']):
                score += 3
            if any(term in id_attr for term in ['search', 'keyword', 'query', 'term']):
                score += 3
            if any(term in class_attr for term in ['search', 'keyword', 'query', 'term']):
                score += 2
            if any(term in placeholder for term in ['search', 'keyword', 'query', 'term']):
                score += 2
            
            # Check size - main search boxes are usually larger
            size = inp.size
            if size['width'] > 200:
                score += 1
                
            # Check position - main search boxes are usually near the top
            location = inp.location
            if location['y'] < 500:
                score += 1
                
            main_search_candidates.append((inp, score))
        
        # Sort by score
        main_search_candidates.sort(key=lambda x: x[1], reverse=True)
        
        print("🎯 Best search field candidates (by score):")
        for i, (inp, score) in enumerate(main_search_candidates[:5]):
            name = inp.get_attribute('name') or ''
            id_attr = inp.get_attribute('id') or ''
            print(f"  {i+1}. Score {score}: name='{name}', id='{id_attr}'")
        
        # Try the best candidate
        if main_search_candidates:
            best_field, best_score = main_search_candidates[0]
            print(f"\n🧪 Testing best candidate (score {best_score})...")
            
            try:
                # Scroll to field and click it
                driver.execute_script("arguments[0].scrollIntoView(true);", best_field)
                time.sleep(1)
                best_field.click()
                time.sleep(1)
                best_field.clear()
                time.sleep(1)
                best_field.send_keys("HVAC")
                
                print("✅ Successfully entered 'HVAC' in search field!")
                print(f"Field value after input: '{best_field.get_attribute('value')}'")
                
                # Look for search/submit button
                buttons = driver.find_elements(By.CSS_SELECTOR, "button, input[type='submit']")
                submit_buttons = []
                
                for btn in buttons:
                    if btn.is_displayed() and btn.is_enabled():
                        btn_text = btn.get_attribute('value') or btn.text or ''
                        btn_type = btn.get_attribute('type') or ''
                        
                        if any(term in btn_text.lower() for term in ['search', 'submit', 'go', 'find']) or btn_type == 'submit':
                            submit_buttons.append((btn, btn_text, btn_type))
                
                print(f"\n🔍 Found {len(submit_buttons)} potential submit buttons:")
                for i, (btn, text, btn_type) in enumerate(submit_buttons):
                    print(f"  {i+1}. Text: '{text}', Type: '{btn_type}', Location: {btn.location}")
                
                if submit_buttons:
                    best_button = submit_buttons[0][0]
                    print(f"\n🚀 Clicking submit button...")
                    best_button.click()
                    time.sleep(5)
                    
                    print(f"After search - URL: {driver.current_url}")
                    
                    # Look for results or indication that search was performed
                    page_text = driver.page_source.lower()
                    if 'hvac' in page_text:
                        print("✅ Found 'HVAC' in page results!")
                        hvac_count = page_text.count('hvac')
                        print(f"   'HVAC' appears {hvac_count} times on results page")
                    else:
                        print("❌ No 'HVAC' found in results")
                        
                    # Check for results containers
                    result_containers = driver.find_elements(By.CSS_SELECTOR, "[class*='result'], [class*='contract'], [class*='solicitation'], .opportunity, tr")
                    print(f"Found {len(result_containers)} potential result containers")
                    
                else:
                    print("❌ No submit button found - trying Enter key")
                    best_field.send_keys("\n")  # Press Enter
                    time.sleep(5)
                    print(f"After Enter - URL: {driver.current_url}")
                
            except Exception as e:
                print(f"❌ Error testing search field: {str(e)}")
        else:
            print("❌ No suitable search field candidates found")
            
            # Save page source for manual inspection
            with open("debug_search_page_full.html", "w") as f:
                f.write(driver.page_source)
            print("💾 Saved full page source to debug_search_page_full.html")
            
    except Exception as e:
        print(f"Error: {e}")
        
    finally:
        input("Press Enter to close browser...")
        driver.quit()

if __name__ == "__main__":
    debug_visible_search_fields()