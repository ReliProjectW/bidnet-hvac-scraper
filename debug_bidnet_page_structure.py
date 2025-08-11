#!/usr/bin/env python3
"""
Debug script to analyze actual BidNet page HTML structure
"""

import logging
import os
from datetime import datetime
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def handle_cookie_banner(page):
    """Handle cookie banner if present"""
    try:
        cookie_banner = page.query_selector('.cookie-banner')
        if cookie_banner:
            cookie_accept = page.query_selector('.cookie-banner button')
            if cookie_accept:
                logger.info("🍪 Accepting cookie banner...")
                cookie_accept.click()
                page.wait_for_timeout(1000)
                return True
    except:
        pass
    return False

def debug_page_structure(page, url):
    """Debug the structure of a BidNet contract page"""
    logger.info(f"🔍 Analyzing page structure: {url}")
    
    try:
        # Navigate to the page
        page.goto(url)
        page.wait_for_timeout(3000)
        
        handle_cookie_banner(page)
        
        # Wait for page to load
        page.wait_for_selector('body', timeout=10000)
        
        # Save HTML for analysis
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        html_file = f"data/debug_contract_page_{timestamp}.html"
        
        with open(html_file, 'w') as f:
            f.write(page.content())
        
        logger.info(f"💾 Saved HTML to {html_file}")
        
        # Analyze page structure
        print(f"\n=== PAGE ANALYSIS FOR {url} ===")
        
        # Look for common table structures
        tables = page.query_selector_all('table')
        print(f"Found {len(tables)} tables")
        
        # Look for key-value pairs in various formats
        print(f"\n--- TABLE ANALYSIS ---")
        for i, table in enumerate(tables[:3]):  # First 3 tables
            print(f"Table {i+1}:")
            rows = table.query_selector_all('tr')
            print(f"  Rows: {len(rows)}")
            
            for j, row in enumerate(rows[:5]):  # First 5 rows
                cells = row.query_selector_all('td, th')
                if len(cells) >= 2:
                    cell1_text = cells[0].inner_text().strip()[:50]
                    cell2_text = cells[1].inner_text().strip()[:50]
                    print(f"    Row {j+1}: '{cell1_text}' | '{cell2_text}'")
        
        # Look for divs with potential field information
        print(f"\n--- DIV ANALYSIS ---")
        divs_with_text = page.query_selector_all('div:has-text("Reference"), div:has-text("Solicitation"), div:has-text("Contact"), div:has-text("Due"), div:has-text("Published"), div:has-text("Location")')
        print(f"Found {len(divs_with_text)} relevant divs")
        
        for i, div in enumerate(divs_with_text[:10]):
            try:
                text = div.inner_text().strip()[:100]
                print(f"  Div {i+1}: {text}")
            except:
                pass
        
        # Look for form fields and labels
        print(f"\n--- FORM FIELDS ---")
        labels = page.query_selector_all('label, .label, .field-label')
        print(f"Found {len(labels)} labels")
        
        for i, label in enumerate(labels[:10]):
            try:
                text = label.inner_text().strip()[:50]
                print(f"  Label {i+1}: {text}")
            except:
                pass
        
        # Look for spans with potential field data
        print(f"\n--- SPAN ANALYSIS ---")
        spans = page.query_selector_all('span')
        relevant_spans = []
        for span in spans[:20]:  # First 20 spans
            try:
                text = span.inner_text().strip()
                if any(keyword in text.lower() for keyword in ['reference', 'solicitation', 'due', 'contact', 'published', 'location', 'agency', 'type']):
                    relevant_spans.append(text[:50])
            except:
                pass
        
        print(f"Found {len(relevant_spans)} relevant spans:")
        for span_text in relevant_spans:
            print(f"  Span: {span_text}")
        
        # Look for headings and their following content
        print(f"\n--- HEADING ANALYSIS ---")
        headings = page.query_selector_all('h1, h2, h3, h4, h5, h6, .heading, .title')
        print(f"Found {len(headings)} headings")
        
        for i, heading in enumerate(headings[:5]):
            try:
                text = heading.inner_text().strip()[:50]
                print(f"  Heading {i+1}: {text}")
            except:
                pass
        
        # Try to extract any visible text that might contain field information
        print(f"\n--- FULL TEXT SEARCH ---")
        full_text = page.inner_text('body')
        
        keywords = ['reference number', 'solicitation number', 'due date', 'closing date', 'contact', 'location', 'agency', 'published', 'issuing']
        
        for keyword in keywords:
            if keyword.lower() in full_text.lower():
                # Find the line containing the keyword
                lines = full_text.split('\n')
                for line in lines:
                    if keyword.lower() in line.lower():
                        print(f"  {keyword.title()}: {line.strip()[:100]}")
                        break
        
        print(f"\n=== END ANALYSIS ===\n")
        
    except Exception as e:
        logger.error(f"Error analyzing page: {e}")

def main():
    """Debug BidNet page structure"""
    logger.info("🔍 Starting BidNet Page Structure Analysis")
    
    # Sample URLs from successful extractions
    test_urls = [
        "https://www.bidnetdirect.com/private/supplier/interception/view-notice/443612578366",  # UCLA HVAC
        "https://www.bidnetdirect.com/private/supplier/interception/view-notice/443612145885",  # Senior Center
        "https://www.bidnetdirect.com/private/supplier/interception/view-notice/443606116157"   # Treatment HVAC
    ]
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = context.new_page()
        
        try:
            # Login
            logger.info("🔐 Logging in to BidNet...")
            page.goto("https://www.bidnetdirect.com/public/authentication/login")
            page.wait_for_timeout(3000)
            
            handle_cookie_banner(page)
            
            username = os.getenv("BIDNET_USERNAME")
            password = os.getenv("BIDNET_PASSWORD")
            
            page.fill("input[name='j_username']", username)
            page.fill("input[name='j_password']", password)
            page.click("button[type='submit']")
            page.wait_for_timeout(10000)
            
            logger.info("✅ Login successful!")
            
            # Analyze each test URL
            for url in test_urls:
                debug_page_structure(page, url)
                page.wait_for_timeout(2000)  # Brief pause between pages
            
        except Exception as e:
            logger.error(f"❌ Error during analysis: {e}")
            
        finally:
            browser.close()
    
    logger.info("✅ Analysis complete!")

if __name__ == "__main__":
    main()