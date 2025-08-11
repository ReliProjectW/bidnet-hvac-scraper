#!/usr/bin/env python3
"""
Examine Table Rows - Debug exact TR/TD structure
"""

import os
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def examine_table_structure():
    """Examine each TR element individually"""
    print("🔍 Examining table structure in detail...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()
        
        try:
            # Login and search
            print("🔐 Logging in...")
            page.goto("https://www.bidnetdirect.com/public/authentication/login")
            page.wait_for_timeout(3000)
            
            # Handle cookie banner
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
            
            # Search
            print("🔍 Searching...")
            page.goto("https://www.bidnetdirect.com/private/supplier/solicitations/search")
            page.wait_for_timeout(5000)
            
            # Handle cookie banner again
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
            page.wait_for_timeout(8000)
            
            # Examine TR elements
            print("📊 Examining TR elements...")
            tr_elements = page.query_selector_all('tr')
            
            for i, tr in enumerate(tr_elements):
                try:
                    # Get all text content
                    text_content = tr.inner_text().strip()
                    
                    if text_content and len(text_content) > 10:  # Skip empty rows
                        print(f"\\n--- TR {i} ---")
                        print(f"Text: {text_content[:150]}...")
                        
                        # Check for TD elements
                        tds = tr.query_selector_all('td')
                        print(f"TDs found: {len(tds)}")
                        
                        # Check for links
                        links = tr.query_selector_all('a')
                        print(f"Links found: {len(links)}")
                        
                        # Show links if any
                        for j, link in enumerate(links):
                            href = link.get_attribute('href')
                            link_text = link.inner_text().strip()
                            print(f"  Link {j}: '{link_text[:50]}...' -> {href}")
                        
                        # Show TD content
                        for j, td in enumerate(tds):
                            td_text = td.inner_text().strip()
                            if td_text:
                                print(f"  TD {j}: {td_text[:80]}...")
                        
                        if i >= 10:  # Don't examine too many
                            break
                            
                except Exception as e:
                    print(f"Error examining TR {i}: {e}")
            
            # Also look for the main results container
            print("\\n🎯 Looking for main results container...")
            
            # Try different selectors for results
            result_containers = [
                '#searchResultsDisplayDiv',
                '.results-table',
                '.search-results',
                '[id*="result"]',
                '[class*="result"]'
            ]
            
            for selector in result_containers:
                try:
                    elements = page.query_selector_all(selector)
                    if elements:
                        print(f"{selector}: Found {len(elements)} elements")
                        if elements:
                            sample_text = elements[0].inner_text()[:200]
                            print(f"  Sample: {sample_text}...")
                except:
                    print(f"{selector}: Error")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    examine_table_structure()