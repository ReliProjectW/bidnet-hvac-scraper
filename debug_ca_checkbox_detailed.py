#!/usr/bin/env python3
"""
Debug script to understand the California purchasing group checkbox
"""

import logging
import time
from config import Config
from src.auth.bidnet_auth import BidNetAuthenticator
from playwright.sync_api import sync_playwright

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_ca_checkbox():
    """Debug the California purchasing group checkbox situation"""
    authenticator = BidNetAuthenticator()
    
    try:
        # First login
        logger.info("🔐 Logging in to BidNet...")
        success = authenticator.login()
        
        if not success:
            logger.error("❌ Login failed")
            return
            
        logger.info("✅ Login successful!")
        
        # Now set up browser for interactive debugging
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=False)  # Show browser
        context = browser.new_context()
        
        # Load cookies from authenticator
        if authenticator.cookies_file.exists():
            import json
            with open(authenticator.cookies_file, 'r') as f:
                cookie_data = json.load(f)
            
            playwright_cookies = cookie_data.get("playwright_cookies", [])
            if playwright_cookies:
                context.add_cookies(playwright_cookies)
                logger.info("Cookies loaded into debug browser")
        
        page = context.new_page()
        
        # Navigate to search page where we might need to check the checkbox
        search_url = "https://www.bidnetdirect.com/search"
        logger.info(f"Navigating to search page: {search_url}")
        page.goto(search_url)
        
        # Wait for page to load
        page.wait_for_load_state("networkidle", timeout=30000)
        
        logger.info(f"Current URL: {page.url}")
        logger.info(f"Page title: {page.title()}")
        
        # Take screenshot
        page.screenshot(path="debug_search_page.png")
        logger.info("Screenshot saved as debug_search_page.png")
        
        # Look for purchasing group elements
        logger.info("\n🔍 SEARCHING FOR PURCHASING GROUP ELEMENTS...")
        
        # Possible selectors for purchasing group dropdown/checkbox
        purchasing_group_selectors = [
            # Dropdown selectors
            "select[name*='purchasing']",
            "select[name*='group']",
            "select[id*='purchasing']",
            "select[id*='group']",
            "select[class*='purchasing']",
            "select[class*='group']",
            
            # Checkbox selectors
            "input[type='checkbox'][name*='california']",
            "input[type='checkbox'][name*='purchasing']",
            "input[type='checkbox'][name*='group']",
            "input[type='checkbox'][id*='california']",
            "input[type='checkbox'][id*='purchasing']",
            "input[type='checkbox'][id*='group']",
            
            # Generic form elements that might contain purchasing group
            "[name*='purchasing']",
            "[id*='purchasing']",
            "[class*='purchasing']",
            "[name*='california']",
            "[id*='california']",
            "[class*='california']"
        ]
        
        found_elements = []
        
        for selector in purchasing_group_selectors:
            try:
                elements = page.locator(selector)
                count = elements.count()
                if count > 0:
                    logger.info(f"✅ Found {count} element(s) with selector: {selector}")
                    found_elements.append((selector, count))
                    
                    # Get details about each element
                    for i in range(count):
                        element = elements.nth(i)
                        try:
                            tag_name = page.evaluate("(element) => element.tagName", element.element_handle())
                            element_type = page.evaluate("(element) => element.type || 'N/A'", element.element_handle())
                            element_name = page.evaluate("(element) => element.name || 'N/A'", element.element_handle())
                            element_id = page.evaluate("(element) => element.id || 'N/A'", element.element_handle())
                            element_class = page.evaluate("(element) => element.className || 'N/A'", element.element_handle())
                            is_visible = element.is_visible()
                            is_checked = None
                            
                            if tag_name.lower() == 'input' and element_type == 'checkbox':
                                is_checked = element.is_checked()
                                
                            logger.info(f"  Element {i+1}: {tag_name} type='{element_type}' name='{element_name}' id='{element_id}' class='{element_class}' visible={is_visible} checked={is_checked}")
                            
                            # Get surrounding text for context
                            try:
                                parent_text = page.evaluate("""
                                    (element) => {
                                        const parent = element.parentElement;
                                        return parent ? parent.textContent.trim().substring(0, 200) : 'No parent';
                                    }
                                """, element.element_handle())
                                logger.info(f"    Context: {parent_text}")
                            except:
                                pass
                                
                        except Exception as e:
                            logger.warning(f"  Could not get details for element {i+1}: {e}")
                            
            except Exception as e:
                # This is expected for many selectors
                pass
        
        if not found_elements:
            logger.warning("❌ No purchasing group elements found with standard selectors")
            
            # Let's try a broader search
            logger.info("\n🔍 BROADER SEARCH - Looking for text containing 'california' or 'purchasing'...")
            
            # Search for text containing relevant keywords
            text_search_results = page.evaluate("""
                () => {
                    const walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_TEXT,
                        null,
                        false
                    );
                    
                    const results = [];
                    let node;
                    
                    while (node = walker.nextNode()) {
                        const text = node.textContent.toLowerCase();
                        if (text.includes('california') || text.includes('purchasing') || text.includes('group')) {
                            results.push({
                                text: node.textContent.trim(),
                                parentTag: node.parentElement ? node.parentElement.tagName : 'unknown',
                                parentClass: node.parentElement ? node.parentElement.className : '',
                                parentId: node.parentElement ? node.parentElement.id : ''
                            });
                        }
                    }
                    
                    return results;
                }
            """)
            
            for result in text_search_results:
                logger.info(f"Found text: '{result['text'][:100]}...' in <{result['parentTag']}> class='{result['parentClass']}' id='{result['parentId']}'")
        
        # Get all form elements for reference
        logger.info("\n📋 ALL FORM ELEMENTS ON PAGE:")
        
        form_elements = page.evaluate("""
            () => {
                const forms = document.querySelectorAll('form');
                const inputs = document.querySelectorAll('input, select, textarea');
                
                const results = {
                    forms: [],
                    inputs: []
                };
                
                forms.forEach((form, index) => {
                    results.forms.push({
                        index: index,
                        id: form.id || 'N/A',
                        name: form.name || 'N/A',
                        action: form.action || 'N/A',
                        method: form.method || 'N/A'
                    });
                });
                
                inputs.forEach((input, index) => {
                    results.inputs.push({
                        index: index,
                        tag: input.tagName,
                        type: input.type || 'N/A',
                        name: input.name || 'N/A',
                        id: input.id || 'N/A',
                        className: input.className || 'N/A',
                        value: input.value || 'N/A',
                        checked: input.checked || false
                    });
                });
                
                return results;
            }
        """)
        
        logger.info(f"Found {len(form_elements['forms'])} forms and {len(form_elements['inputs'])} input elements")
        
        for form in form_elements['forms']:
            logger.info(f"Form {form['index']}: id='{form['id']}' name='{form['name']}' action='{form['action']}' method='{form['method']}'")
            
        for input_elem in form_elements['inputs'][:20]:  # Limit to first 20 to avoid spam
            logger.info(f"Input {input_elem['index']}: <{input_elem['tag']}> type='{input_elem['type']}' name='{input_elem['name']}' id='{input_elem['id']}' class='{input_elem['className']}' value='{input_elem['value']}' checked={input_elem['checked']}")
        
        if len(form_elements['inputs']) > 20:
            logger.info(f"... and {len(form_elements['inputs']) - 20} more input elements")
        
        logger.info(f"\n🌐 Page HTML saved to debug_search_page.html")
        with open("debug_search_page.html", "w") as f:
            f.write(page.content())
        
        logger.info(f"\n📸 You can now manually inspect the page in the browser window.")
        logger.info(f"Please:")
        logger.info(f"1. Look for the purchasing group dropdown/checkbox")
        logger.info(f"2. Note its location and any surrounding elements")
        logger.info(f"3. Try clicking on it and see what happens")
        logger.info(f"4. Check the browser console for any JavaScript errors")
        
        # Keep browser open for manual inspection
        input("\n⏸️  Press Enter to close browser and continue...")
        
        browser.close()
        playwright.stop()
        
    except Exception as e:
        logger.error(f"❌ Debug failed: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        authenticator.cleanup()

if __name__ == "__main__":
    debug_ca_checkbox()