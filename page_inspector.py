#!/usr/bin/env python3
"""
BidNet Page Inspector
Analyzes the currently loaded page structure to identify contract listing patterns
"""

import sys
import logging
from pathlib import Path
import time
from collections import Counter

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re

def setup_browser():
    """Set up browser for page inspection"""
    chrome_options = Options()
    # Non-headless so you can navigate manually
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.implicitly_wait(5)
    
    return driver

def analyze_page_structure(html_content, page_url):
    """Analyze page structure to identify contract patterns"""
    print(f"\n🔍 ANALYZING PAGE: {page_url}")
    print("=" * 80)
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. Basic page info
    title = soup.find('title')
    print(f"📄 Page Title: {title.get_text() if title else 'No title'}")
    
    # 2. Look for repeated elements (likely contract listings)
    print("\n🔍 ANALYZING REPEATED ELEMENTS...")
    
    # Group elements by tag + class combination
    element_patterns = {}
    
    for tag in ['div', 'tr', 'article', 'li', 'section']:
        elements = soup.find_all(tag)
        for elem in elements:
            classes = elem.get('class', [])
            if classes:
                class_str = ' '.join(sorted(classes))
                key = f"{tag}.{class_str}"
                if key not in element_patterns:
                    element_patterns[key] = []
                element_patterns[key].append(elem)
    
    # Find the most common patterns (likely contract listings)
    common_patterns = [(k, len(v)) for k, v in element_patterns.items() if len(v) > 2]
    common_patterns.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n📊 TOP REPEATED ELEMENT PATTERNS:")
    for pattern, count in common_patterns[:10]:
        print(f"  {pattern}: {count} occurrences")
    
    # 3. Analyze the most promising pattern
    if common_patterns:
        top_pattern, top_count = common_patterns[0]
        print(f"\n🎯 ANALYZING TOP PATTERN: {top_pattern} ({top_count} elements)")
        
        elements = element_patterns[top_pattern]
        
        # Analyze first few elements for content patterns
        print("\n📝 CONTENT ANALYSIS:")
        for i, elem in enumerate(elements[:3]):
            print(f"\n  ELEMENT {i+1}:")
            text_content = elem.get_text(strip=True)
            print(f"    Text length: {len(text_content)} chars")
            print(f"    Text preview: {text_content[:100]}...")
            
            # Look for links
            links = elem.find_all('a', href=True)
            if links:
                print(f"    Links found: {len(links)}")
                for j, link in enumerate(links[:2]):
                    print(f"      Link {j+1}: {link.get('href')} -> '{link.get_text(strip=True)[:50]}'")
            
            # Look for dates
            date_patterns = [
                r'\d{1,2}/\d{1,2}/\d{4}',
                r'\d{1,2}-\d{1,2}-\d{4}',
                r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4}'
            ]
            for pattern in date_patterns:
                dates = re.findall(pattern, text_content, re.IGNORECASE)
                if dates:
                    print(f"    Dates found: {dates}")
            
            # Look for dollar amounts
            amounts = re.findall(r'\$[\d,]+(?:\.\d{2})?', text_content)
            if amounts:
                print(f"    Dollar amounts: {amounts}")
    
    # 4. Look for specific contract-related content
    print(f"\n🏗️ CONTRACT-SPECIFIC ANALYSIS:")
    
    # Look for HVAC-related content
    hvac_terms = ['HVAC', 'heat pump', 'air conditioning', 'heating', 'ventilation', 'mini-split', 'furnace']
    hvac_elements = []
    
    for term in hvac_terms:
        elements = soup.find_all(string=re.compile(term, re.IGNORECASE))
        for elem in elements:
            parent = elem.parent
            if parent and parent not in hvac_elements:
                hvac_elements.append(parent)
    
    if hvac_elements:
        print(f"    Found {len(hvac_elements)} elements with HVAC terms")
        for i, elem in enumerate(hvac_elements[:3]):
            print(f"      HVAC Element {i+1}: {elem.name} - {elem.get_text(strip=True)[:100]}...")
    
    # Look for agency/government terms
    agency_terms = ['city of', 'county of', 'school district', 'department of', 'university of']
    agency_elements = []
    
    for term in agency_terms:
        elements = soup.find_all(string=re.compile(term, re.IGNORECASE))
        for elem in elements:
            parent = elem.parent
            if parent and parent not in agency_elements:
                agency_elements.append(parent)
    
    if agency_elements:
        print(f"    Found {len(agency_elements)} elements with agency terms")
    
    # 5. Generate suggested CSS selectors
    print(f"\n🎯 SUGGESTED CSS SELECTORS:")
    if common_patterns:
        top_pattern = common_patterns[0][0]
        tag, classes = top_pattern.split('.', 1)
        
        suggested_selectors = [
            f"{tag}.{classes.replace(' ', '.')}",  # Exact class match
            f"{tag}[class*='{classes.split()[0]}']" if classes else tag,  # Partial class match
            f"{tag}:has(a[href*='solicitation'])" if tag == 'div' else None,
            f"{tag}:has(a[href*='opportunity'])" if tag == 'div' else None,
        ]
        
        suggested_selectors = [s for s in suggested_selectors if s]
        
        print("    For contract containers:")
        for selector in suggested_selectors:
            print(f"      {selector}")
    
    # 6. Save detailed HTML sample
    if common_patterns:
        sample_file = "data/page_structure_sample.html"
        top_elements = element_patterns[common_patterns[0][0]]
        
        with open(sample_file, 'w', encoding='utf-8') as f:
            f.write(f"<!-- Page: {page_url} -->\n")
            f.write(f"<!-- Pattern: {common_patterns[0][0]} -->\n")
            f.write(f"<!-- Sample of {len(top_elements)} similar elements -->\n\n")
            
            for i, elem in enumerate(top_elements[:5]):
                f.write(f"<!-- ELEMENT {i+1} -->\n")
                f.write(str(elem.prettify()))
                f.write("\n\n")
        
        print(f"\n💾 Saved detailed HTML sample to: {sample_file}")

def main():
    """Main page inspector"""
    print("🕵️ BidNet Page Inspector")
    print("=" * 50)
    print("\nInstructions:")
    print("1. A browser window will open")
    print("2. Navigate to BidNet and log in")
    print("3. Go to a search results page with contracts")
    print("4. Come back to this terminal and press ENTER")
    print("5. I'll analyze whatever page is currently loaded")
    
    # Setup browser
    driver = setup_browser()
    
    try:
        # Give user time to navigate
        input("\n🚀 Browser opened! Navigate to BidNet search results, then press ENTER here...")
        
        # Get current page info
        current_url = driver.current_url
        page_source = driver.page_source
        
        # Analyze the page
        analyze_page_structure(page_source, current_url)
        
        # Ask if they want to analyze another page
        while True:
            choice = input(f"\n❓ Analyze another page? (y/n): ").lower()
            if choice == 'y':
                input("Navigate to the next page, then press ENTER...")
                current_url = driver.current_url
                page_source = driver.page_source
                analyze_page_structure(page_source, current_url)
            else:
                break
                
        print("\n✅ Page inspection complete!")
        print("📄 Check the generated files in the 'data' folder for detailed analysis.")
        
    except KeyboardInterrupt:
        print("\n⏹️ Inspection stopped by user")
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()