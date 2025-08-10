import logging
import time
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode, urlparse, parse_qs
import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm

from config import Config
from src.auth.bidnet_auth import BidNetAuthenticator

from playwright.sync_api import sync_playwright

class BidNetSearcher:
    def __init__(self):
        self.authenticator = BidNetAuthenticator()
        self.session = None
        self.page = None
        self.browser = None
        self.context = None
        self.playwright = None
        self.logger = logging.getLogger(__name__)
        
    def get_authenticated_session(self):
        """Get authenticated session"""
        if not self.session:
            self.session = self.authenticator.get_authenticated_session()
        return self.session
    
    def setup_browser(self):
        """Set up Playwright browser for JavaScript-heavy pages"""
        if self.browser:
            return self.browser, self.context, self.page
            
        self.playwright = sync_playwright().start()
        
        # Launch browser with options similar to Selenium config
        self.browser = self.playwright.chromium.launch(
            headless=Config.BROWSER_SETTINGS.get("headless", False),
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage", 
                "--disable-gpu"
            ]
        )
        
        # Create context with user agent and viewport
        self.context = self.browser.new_context(
            user_agent=Config.BROWSER_SETTINGS.get("user_agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"),
            viewport={'width': 1920, 'height': 1080}
        )
        
        # Create new page
        self.page = self.context.new_page()
        
        return self.browser, self.context, self.page
    
    def cleanup(self):
        """Clean up Playwright resources"""
        try:
            if self.page:
                self.page.close()
                self.page = None
            if self.context:
                self.context.close()
                self.context = None
            if self.browser:
                self.browser.close()
                self.browser = None
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
        except Exception as e:
            self.logger.debug(f"Error during cleanup: {e}")
        
    def search_with_browser(self, keyword: str, location_filters: List[str]) -> List[Dict[str, Any]]:
        """Search using browser automation (for JavaScript-heavy sites)"""
        contracts = []
        
        try:
            # Setup browser
            browser, context, page = self.setup_browser()
            
            # Navigate to main page first (cookies don't work reliably with BidNet)
            self.logger.info("Navigating to main page (will auto-login if needed)...")
            page.goto(Config.BASE_URL)
            page.wait_for_load_state("networkidle")
            
            # Navigate to search page
            search_url = f"{Config.BASE_URL}private/supplier/solicitations/search"
            self.logger.info(f"Navigating to search page with browser: {search_url}")
            page.goto(search_url)
            
            # Wait for page to load
            page.wait_for_load_state("networkidle")
            
            # Check current URL and page content to detect if we're on login page
            current_url = page.url
            self.logger.info(f"Current URL after navigation: {current_url}")
            
            # Update the authenticator's page reference for auto-login
            self.authenticator.page = page
            self.authenticator.context = context
            self.authenticator.browser = browser
            
            # Check if we got redirected to login page and handle it
            if self.authenticator.is_login_page(page):
                self.logger.info("🔑 Login page detected - performing auto-login...")
                if not self.authenticator.auto_login_if_needed(page):
                    self.logger.error("❌ Auto-login failed")
                    return contracts
                
                # After successful login, navigate back to search page
                self.logger.info("✅ Auto-login successful, navigating to search page...")
                page.goto(search_url)
                page.wait_for_load_state("networkidle")
                
                # Verify we're now on the search page
                if self.authenticator.is_login_page(page):
                    self.logger.error("❌ Still on login page after auto-login attempt")
                    return contracts
                    
                self.logger.info("✅ Successfully reached search page after login")
            else:
                self.logger.info("✅ Already on search page, no login needed")
            
            # Look for search input fields
            search_element = None
            search_selectors = [
                'textarea#solicitationSingleBoxSearch',  # BidNet specific main search
                'textarea[name="keywords"]',              # BidNet specific
                'input[name*="search"]',
                'input[name*="keyword"]',
                'input[name*="query"]',
                'textarea[placeholder*="search"]',
                'textarea[placeholder*="keyword"]',
                'input[placeholder*="search"]',
                'input[placeholder*="keyword"]',
                '#search',
                '#searchText',
                '#keyword',
                '.search-input',
                'input[type="search"]'
            ]
            
            for selector in search_selectors:
                try:
                    if page.locator(selector).first.is_visible(timeout=5000):
                        search_element = page.locator(selector).first
                        break
                except:
                    continue
                    
            if search_element:
                self.logger.info(f"Found search field, entering keyword: {keyword}")
                # Clear and fill the search field
                try:
                    search_element.clear()
                    search_element.fill(keyword)
                except Exception as e:
                    self.logger.error(f"Failed to enter search term: {str(e)}")
                    # Try JavaScript input as fallback
                    page.evaluate(f"document.querySelector('{search_selectors[0]}').value = '{keyword}'")
                
                # For now, skip complex filter handling and just do basic search
                # (California filtering can be added back later once basic search works)
                self.logger.info("Skipping location filters for initial test - will search all locations")
                
                # Look for search button
                search_button_element = None
                button_selectors = [
                    'button#topSearchButton',                 # BidNet specific
                    'button.topSearch',                       # BidNet specific  
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'button:has-text("Search")',
                    '.search-button',
                    '#searchButton',
                    '[data-testid*="search"]'
                ]
                
                for selector in button_selectors:
                    try:
                        if page.locator(selector).first.is_visible(timeout=2000):
                            search_button_element = page.locator(selector).first
                            break
                    except:
                        continue
                
                if search_button_element:
                    self.logger.info("Clicking search button...")
                    search_button_element.click()
                else:
                    # Try pressing Enter on search field
                    if search_element:
                        search_element.press("Enter")
                
                # Wait for results to load 
                page.wait_for_load_state("networkidle")
                
                # Get all results across all pages
                contracts = self._get_all_paginated_results(page, keyword)
                
            else:
                self.logger.warning("Could not find search field on page")
                # Save the page for debugging
                page_html = page.content()
                debug_file = f"{Config.DATA_DIR}/debug_search_page_browser.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(page_html)
                self.logger.info(f"Saved search page HTML: {debug_file}")
                
        except Exception as e:
            self.logger.error(f"Browser search failed for '{keyword}': {str(e)}")
        
        finally:
            self.cleanup()
                
        return contracts
    
    def search_contracts(self, keywords: List[str] = None, location_filters: List[str] = None, 
                        max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Search for contracts on BidNet Direct
        
        Args:
            keywords: List of search keywords
            location_filters: List of location filters
            max_results: Maximum number of results to return
            
        Returns:
            List of contract dictionaries
        """
        self.logger.info("Starting contract search...")
        
        # Get authenticated session
        session = self.get_authenticated_session()
        
        # Use default keywords if none provided
        if keywords is None:
            keywords = Config.SEARCH_PARAMS["target_keywords"]
        if location_filters is None:
            location_filters = Config.SEARCH_PARAMS["location_filters"]
            
        all_contracts = []
        
        # Search with each keyword combination (use browser-based search for JavaScript sites)
        search_limit = min(len(keywords), 3)  # Limit to 3 for browser testing
        for keyword in tqdm(keywords[:search_limit], desc="Searching keywords"):
            self.logger.info(f"Searching for: {keyword}")
            
            # Use browser-based search instead of requests
            contracts = self.search_with_browser(keyword, location_filters)
            
            # Add unique contracts
            for contract in contracts:
                if not any(c.get('id') == contract.get('id') for c in all_contracts):
                    all_contracts.append(contract)
                    
            # Respect rate limits
            time.sleep(1)
            
            if len(all_contracts) >= max_results:
                break
                
        self.logger.info(f"Found {len(all_contracts)} total contracts")
        return all_contracts[:max_results]
    
    def _get_all_paginated_results(self, page, keyword: str) -> List[Dict[str, Any]]:
        """Get results from all pages of search results"""
        all_contracts = []
        page_num = 1
        max_pages = 20  # Safety limit
        
        while page_num <= max_pages:
            self.logger.info(f"Processing page {page_num} of results...")
            
            # Save current page source for debugging
            debug_file = f"{Config.DATA_DIR}/debug_browser_results_page_{page_num}.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(page.content())
            self.logger.info(f"Saved page {page_num} HTML: {debug_file}")
            
            # Parse results from current page
            page_contracts = self._parse_search_results(page.content(), keyword)
            
            # Debug: Check how many total rows exist vs how many we extracted
            try:
                all_rows = page.locator('tr[class*="mets-table-row"]').all()
                all_odd_rows = page.locator('tr.mets-table-row.odd').all()
                all_even_rows = page.locator('tr.mets-table-row.even').all()
                self.logger.info(f"📊 Page {page_num} debug - Total rows: {len(all_rows)}, Odd: {len(all_odd_rows)}, Even: {len(all_even_rows)}, Extracted: {len(page_contracts)}")
            except Exception as e:
                self.logger.debug(f"Could not count page rows: {e}")
            
            if not page_contracts:
                self.logger.info(f"No contracts found on page {page_num}, ending pagination")
                break
                
            all_contracts.extend(page_contracts)
            self.logger.info(f"Found {len(page_contracts)} contracts on page {page_num} (total: {len(all_contracts)})")
            
            # Look for next page button with more comprehensive selectors
            next_button = None
            next_selectors = [
                'a[rel="next"]',                                 # Most common "next" attribute
                'a[class*="next"]',                             # Class contains "next"
                'a[title*="Next"]',                             # Title contains "Next"
                'a[aria-label*="Next"]',                        # Aria label contains "Next"
                f'a[href*="pageNumber={page + 1}"]',           # Direct page number link
                '.mets-pagination-page-icon.next',             # BidNet specific pagination
                'a.next',                                       # Simple next class
                'button[title*="Next"]',
                '.pagination a:contains("Next")',
                '[data-testid="next"]'
            ]
            
            for selector in next_selectors:
                try:
                    if 'contains' in selector:
                        # Use text-based selector for Playwright
                        next_button = page.locator("text=Next").first
                    else:
                        next_button = page.locator(selector).first
                    
                    if next_button.is_visible(timeout=2000):
                        self.logger.info(f"Found next page button: {selector}")
                        break
                    else:
                        next_button = None
                except Exception as e:
                    self.logger.debug(f"Next button selector '{selector}' failed: {e}")
                    continue
            
            if next_button:
                try:
                    # Scroll to button and click
                    next_button.scroll_into_view_if_needed()
                    time.sleep(1)
                    
                    # Try clicking the button
                    next_button.click()
                    time.sleep(3)  # Wait for page to load
                    page_num += 1
                except Exception as e:
                    self.logger.error(f"Failed to click next page button: {e}")
                    break
            else:
                # Try alternative: look for direct page number links
                try:
                    next_page_link = page.locator(f"text={page_num + 1}").first
                    if next_page_link.is_visible(timeout=2000):
                        self.logger.info(f"Found direct page {page_num + 1} link")
                        next_page_link.scroll_into_view_if_needed()
                        time.sleep(1)
                        next_page_link.click()
                        time.sleep(3)
                        page_num += 1
                        continue
                except Exception as e:
                    self.logger.debug(f"No direct page link found: {e}")
                
                self.logger.info(f"No more pages found after page {page_num}")
                break
        
        self.logger.info(f"Pagination complete: collected {len(all_contracts)} contracts from {page_num} pages")
        return all_contracts
    

    def _search_single_keyword(self, session: requests.Session, keyword: str, 
                              location_filters: List[str]) -> List[Dict[str, Any]]:
        """
        Search for contracts with a single keyword
        
        Args:
            session: Authenticated requests session
            keyword: Search keyword
            location_filters: List of location filters
            
        Returns:
            List of contract dictionaries
        """
        contracts = []
        
        try:
            # First, let's navigate to the main search page to understand the structure
            main_search_url = f"{Config.BASE_URL}private/supplier/solicitations/search"
            self.logger.info(f"Accessing main search page: {main_search_url}")
            
            # Get the search page first
            initial_response = session.get(main_search_url)
            
            if initial_response.status_code != 200:
                self.logger.warning(f"Failed to access search page: {initial_response.status_code}")
                self.logger.info(f"Response URL: {initial_response.url}")
                return contracts
            
            # Parse the search page to understand the form structure
            soup = BeautifulSoup(initial_response.content, 'html.parser')
            
            # Look for search form
            search_forms = soup.find_all('form')
            search_form = None
            
            for form in search_forms:
                # Look for forms that might be search forms
                if any(field in str(form).lower() for field in ['search', 'keyword', 'query', 'solicitation']):
                    search_form = form
                    break
            
            if search_form:
                self.logger.info("Found search form, analyzing structure...")
                # Get form action
                form_action = search_form.get('action', main_search_url)
                if not form_action.startswith('http'):
                    if form_action.startswith('/'):
                        form_action = Config.BASE_URL.rstrip('/') + form_action
                    else:
                        form_action = main_search_url
                
                # Build search parameters based on form fields
                search_params = {}
                
                # Look for input fields
                inputs = search_form.find_all(['input', 'select', 'textarea'])
                for inp in inputs:
                    name = inp.get('name')
                    if name:
                        if 'keyword' in name.lower() or 'search' in name.lower() or 'query' in name.lower():
                            search_params[name] = keyword
                        elif 'location' in name.lower() and location_filters:
                            search_params[name] = location_filters[0]
                        elif 'category' in name.lower():
                            search_params[name] = 'Construction'
                        elif inp.get('type') == 'hidden':
                            # Include hidden fields with their default values
                            value = inp.get('value', '')
                            if value:
                                search_params[name] = value
                
                # If we didn't find specific fields, use common names
                if not any('keyword' in k.lower() or 'search' in k.lower() for k in search_params.keys()):
                    search_params.update({
                        'q': keyword,
                        'keyword': keyword,
                        'searchText': keyword,
                        'query': keyword
                    })
                
                # Make search request
                if search_form.get('method', '').lower() == 'post':
                    response = session.post(form_action, data=search_params)
                else:
                    response = session.get(form_action, params=search_params)
                    
                self.logger.info(f"Search request to: {form_action}")
                self.logger.info(f"Search params: {search_params}")
                
            else:
                # Fallback: try common search patterns
                self.logger.info("No search form found, trying direct search...")
                
                # Try various search parameter combinations
                search_variations = [
                    {'q': keyword},
                    {'keyword': keyword},
                    {'searchText': keyword}, 
                    {'query': keyword},
                    {'search': keyword},
                    {'keywords': keyword}
                ]
                
                response = None
                for params in search_variations:
                    if location_filters:
                        params['location'] = location_filters[0]
                    params['category'] = 'Construction'
                    
                    try:
                        test_response = session.get(main_search_url, params=params)
                        if test_response.status_code == 200 and 'saml' not in test_response.url.lower():
                            response = test_response
                            self.logger.info(f"Successful search with params: {params}")
                            break
                    except:
                        continue
                
                if not response:
                    response = session.get(main_search_url)
            
            if response.status_code != 200:
                self.logger.warning(f"Search request failed with status {response.status_code}")
                return contracts
                
            # Parse response
            contracts = self._parse_search_results(response.text, keyword)
            
        except Exception as e:
            self.logger.error(f"Error searching for '{keyword}': {str(e)}")
            
        return contracts
    
    def _parse_search_results(self, html_content: str, search_keyword: str) -> List[Dict[str, Any]]:
        """
        Parse search results from HTML content
        
        Args:
            html_content: HTML content from search page
            search_keyword: The keyword used for search
            
        Returns:
            List of contract dictionaries
        """
        contracts = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Save full HTML for debugging (first time only)
            if not hasattr(self, '_html_saved'):
                debug_file = f"{Config.DATA_DIR}/debug_search_page.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                self.logger.info(f"Saved full HTML for debugging: {debug_file}")
                self._html_saved = True
            
            # BidNet-specific selectors based on page inspector analysis
            contract_selectors = [
                # Primary: All table rows (both odd and even)
                'tr[class*="mets-table-row"]',               # Gets BOTH odd and even rows
                'tr.mets-table-row',                         # Any mets-table-row
                'tr.mets-table-row.odd, tr.mets-table-row.even',  # Explicit odd + even
                
                # Secondary: General table patterns
                'tbody tr',
                'table tr:has(td)',
                'tr[data-solicitation-id]',
                'tr[data-id]',
                
                # Tertiary: Div-based layouts  
                'div[class*="solicitation"]',
                'div[class*="opportunity"]',
                'div[data-solicitation-id]',
                'div:has(a[href*="solicitation"])',
                'div:has(a[href*="opportunity"])',
                
                # Fallback patterns
                '.search-result',
                '.result-item',
                '[class*="bid"]'
            ]
            
            contract_elements = []
            used_selector = None
            
            for selector in contract_selectors:
                try:
                    elements = soup.select(selector)
                    if elements and len(elements) > 1:  # Need multiple results to be meaningful
                        contract_elements = elements
                        used_selector = selector
                        self.logger.info(f"Found {len(elements)} contracts using selector: {selector}")
                        break
                except Exception as e:
                    self.logger.debug(f"Selector '{selector}' failed: {e}")
                    continue
                    
            if not contract_elements:
                # More aggressive fallback: look for any structure with multiple similar elements
                self.logger.info("No standard selectors found, analyzing page structure...")
                
                # Look for tables with multiple rows
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    if len(rows) > 3:  # Skip header rows
                        contract_elements = rows[1:]  # Skip header
                        used_selector = "table rows (fallback)"
                        self.logger.info(f"Found table with {len(contract_elements)} rows")
                        break
                
                # If still nothing, look for repeated div patterns
                if not contract_elements:
                    all_divs = soup.find_all('div')
                    # Group divs by class patterns
                    class_groups = {}
                    for div in all_divs:
                        classes = div.get('class', [])
                        if classes:
                            class_key = ' '.join(sorted(classes))
                            if class_key not in class_groups:
                                class_groups[class_key] = []
                            class_groups[class_key].append(div)
                    
                    # Find the largest group (likely the contract listing)
                    largest_group = max(class_groups.values(), key=len, default=[])
                    if len(largest_group) > 2:
                        contract_elements = largest_group
                        used_selector = f"div pattern (fallback) - {largest_group[0].get('class', [])}"
                        self.logger.info(f"Found repeated div pattern with {len(contract_elements)} elements")
                
            if contract_elements:
                self.logger.info(f"Processing {len(contract_elements)} elements with selector: {used_selector}")
                
            # Extract contract information
            for i, element in enumerate(contract_elements[:50]):
                contract = self._extract_contract_info(element, search_keyword, i)
                if contract:
                    contracts.append(contract)
                    self.logger.debug(f"Extracted: {contract.get('title', 'No title')[:100]}")
                    
        except Exception as e:
            self.logger.error(f"Error parsing search results: {str(e)}")
            
        return contracts
    
    def _extract_contract_info(self, element, search_keyword: str, index: int) -> Optional[Dict[str, Any]]:
        """
        Extract contract information from HTML element
        
        Args:
            element: BeautifulSoup element containing contract info
            search_keyword: The search keyword used
            index: Index of the contract in results
            
        Returns:
            Dictionary with contract information or None
        """
        try:
            element_text = element.get_text(strip=True)
            contract = {
                'id': f"{search_keyword}_{index}_{int(time.time())}",
                'search_keyword': search_keyword,
                'raw_html': str(element)[:1000],  # Store more HTML for debugging
                'full_text': element_text[:500]  # Store text content for analysis
            }
            
            # Enhanced title extraction - try multiple approaches
            title = None
            
            # Method 1: Look for strong/bold titles or headings
            title_selectors = [
                'h1', 'h2', 'h3', 'h4', 'h5',
                'strong', 'b',
                '.title', '.name', '.description', '.project-title',
                'a[href*="solicitation"]', 'a[href*="opportunity"]', 'a[href*="bid"]',
                'td:first-child', 'td:nth-child(1)',  # First column in table
                '[class*="title"]', '[class*="name"]', '[id*="title"]'
            ]
            
            for selector in title_selectors:
                try:
                    found = element.select_one(selector)
                    if found:
                        text = found.get_text(strip=True)
                        if text and len(text) > 10 and text != search_keyword:  # Avoid generic text
                            title = text
                            break
                except:
                    continue
            
            # Method 2: If no good title, look for the longest meaningful text block
            if not title:
                text_elements = element.find_all(['td', 'div', 'span', 'p'])
                for elem in text_elements:
                    text = elem.get_text(strip=True)
                    if text and len(text) > 15 and len(text) < 200:  # Reasonable title length
                        # Skip generic text
                        if not any(generic in text.lower() for generic in ['search', 'result', 'page', 'filter', 'sort']):
                            title = text
                            break
            
            contract['title'] = title or 'No title found'
            
            # Enhanced agency extraction
            agency_selectors = [
                '.agency', '.organization', '.client', '.issuer', '.owner',
                '[class*="agency"]', '[class*="organization"]', '[class*="client"]',
                'td:nth-child(2)', 'td:nth-child(3)',  # Common table columns
                '.entity-name', '.government-entity'
            ]
            
            agency = self._extract_text_by_selectors(element, agency_selectors)
            
            # Look for agency in text patterns
            if not agency:
                text = element.get_text()
                # Common agency patterns
                agency_patterns = [
                    r'(?i)(city of|county of|state of|university of|school district|[\w\s]+ county|[\w\s]+ city)[\w\s]+',
                    r'(?i)(department of|ministry of|office of)[\w\s]+',
                ]
                for pattern in agency_patterns:
                    matches = re.findall(pattern, text)
                    if matches:
                        agency = matches[0]
                        break
            
            contract['agency'] = agency or 'Unknown agency'
            
            # Enhanced location extraction
            location_selectors = [
                '.location', '.address', '.city', '.state', '.region',
                '[class*="location"]', '[class*="address"]', '[class*="city"]',
                '[data-location]', '[data-address]'
            ]
            
            location = self._extract_text_by_selectors(element, location_selectors)
            
            # Look for CA locations in text
            if not location:
                text = element.get_text()
                ca_patterns = [
                    r'(?i)([\w\s]+),\s*(ca|california)',
                    r'(?i)(los angeles|orange county|san diego|san bernardino|riverside|ventura|imperial)[\w\s]*county',
                ]
                for pattern in ca_patterns:
                    matches = re.findall(pattern, text)
                    if matches:
                        location = matches[0] if isinstance(matches[0], str) else ' '.join(matches[0])
                        break
            
            contract['location'] = location or 'Unknown location'
            
            # Enhanced date extraction
            date_selectors = [
                '.date', '.deadline', '.due-date', '.close-date', '.open-date',
                '[class*="date"]', '[class*="deadline"]', '[class*="due"]'
            ]
            
            dates = self._extract_text_by_selectors(element, date_selectors)
            
            # Look for date patterns in text
            if not dates:
                text = element.get_text()
                date_patterns = [
                    r'\d{1,2}/\d{1,2}/\d{4}',
                    r'\d{1,2}-\d{1,2}-\d{4}',
                    r'(?i)(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2},?\s+\d{4}',
                    r'(?i)due\s*:?\s*[\d/\-\w\s,]+',
                    r'(?i)close\s*:?\s*[\d/\-\w\s,]+',
                ]
                found_dates = []
                for pattern in date_patterns:
                    matches = re.findall(pattern, text)
                    found_dates.extend(matches)
                
                if found_dates:
                    dates = ' | '.join(found_dates[:3])  # Take first 3 dates
            
            contract['dates'] = dates or 'No dates found'
            
            # Enhanced link extraction
            links = element.find_all('a', href=True)
            best_link = None
            
            for link in links:
                href = link.get('href', '')
                if any(keyword in href.lower() for keyword in ['solicitation', 'opportunity', 'bid', 'rfp', 'rfq']):
                    best_link = href
                    break
            
            if not best_link and links:
                best_link = links[0].get('href', '')
            
            if best_link:
                if not best_link.startswith('http'):
                    if best_link.startswith('//'):
                        best_link = 'https:' + best_link
                    elif best_link.startswith('/'):
                        best_link = Config.BASE_URL.rstrip('/') + best_link
                    else:
                        best_link = Config.BASE_URL.rstrip('/') + '/' + best_link
                contract['url'] = best_link
            else:
                contract['url'] = None
                
            # Enhanced value extraction
            amount_patterns = [
                r'\$[\d,]+(?:\.\d{2})?',
                r'(?i)value[:\s]*\$?[\d,]+',
                r'(?i)amount[:\s]*\$?[\d,]+',
                r'(?i)budget[:\s]*\$?[\d,]+',
            ]
            
            amount_text = element.get_text()
            found_amounts = []
            
            for pattern in amount_patterns:
                matches = re.findall(pattern, amount_text)
                found_amounts.extend(matches)
            
            contract['estimated_value'] = found_amounts[0] if found_amounts else 'Not specified'
            
            return contract
            
        except Exception as e:
            self.logger.error(f"Error extracting contract info: {str(e)}")
            return None
    
    def _extract_text_by_selectors(self, element, selectors: List[str]) -> Optional[str]:
        """Extract text using multiple CSS selectors"""
        for selector in selectors:
            try:
                found = element.select_one(selector)
                if found:
                    text = found.get_text().strip()
                    if text:
                        return text
            except:
                continue
        return None
    
    def filter_hvac_contracts(self, contracts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter contracts to only include relevant HVAC opportunities
        
        Args:
            contracts: List of contract dictionaries
            
        Returns:
            Filtered list of HVAC contracts
        """
        self.logger.info("Filtering contracts for HVAC relevance...")
        
        hvac_contracts = []
        target_keywords = [kw.lower() for kw in Config.SEARCH_PARAMS["target_keywords"]]
        negative_keywords = [kw.lower() for kw in Config.SEARCH_PARAMS["negative_keywords"]]
        
        for contract in contracts:
            # Combine all text fields for analysis
            text_content = ' '.join([
                contract.get('title', ''),
                contract.get('agency', ''),
                contract.get('location', ''),
                contract.get('raw_html', '')
            ]).lower()
            
            self.logger.debug(f"\nAnalyzing: {contract.get('title', 'No title')[:100]}")
            
            # Check for negative keywords first (exclude these)
            matching_negative = [neg_kw for neg_kw in negative_keywords if neg_kw in text_content]
            if matching_negative:
                self.logger.info(f"Excluding '{contract.get('title', 'No title')[:50]}' due to: {matching_negative}")
                continue
            
            # Check for positive HVAC keywords (be more lenient)
            matching_positive = [pos_kw for pos_kw in target_keywords if pos_kw in text_content]
            
            # Also check if the search keyword is in the content (since we searched for HVAC terms)
            search_in_content = contract.get('search_keyword', '').lower() in text_content
            
            if matching_positive or search_in_content:
                contract['hvac_relevance_score'] = len(matching_positive)
                contract['matching_keywords'] = matching_positive
                hvac_contracts.append(contract)
                self.logger.info(f"✅ Kept '{contract.get('title', 'No title')[:50]}' - matches: {matching_positive}")
            else:
                self.logger.debug(f"No HVAC keywords found in: {contract.get('title', 'No title')[:50]}")
                
        self.logger.info(f"Filtered to {len(hvac_contracts)} HVAC-relevant contracts")
        return hvac_contracts
    
    def _calculate_relevance_score(self, text: str, target_keywords: List[str]) -> int:
        """Calculate relevance score based on keyword matches"""
        score = 0
        for keyword in target_keywords:
            if keyword in text:
                score += 1
        return score
    
    def save_contracts_to_csv(self, contracts: List[Dict[str, Any]], filename: str = None):
        """Save contracts to CSV file"""
        if not contracts:
            self.logger.warning("No contracts to save")
            return
            
        if filename is None:
            timestamp = int(time.time())
            filename = f"hvac_contracts_{timestamp}.csv"
            
        filepath = f"{Config.PROCESSED_DATA_DIR}/{filename}"
        
        # Convert to DataFrame
        df = pd.DataFrame(contracts)
        
        # Remove raw_html column for CSV (too long)
        if 'raw_html' in df.columns:
            df = df.drop('raw_html', axis=1)
            
        # Save to CSV
        df.to_csv(filepath, index=False)
        self.logger.info(f"Saved {len(contracts)} contracts to {filepath}")
        
        return filepath
    
    def save_contracts_to_excel(self, contracts: List[Dict[str, Any]], filename: str = None):
        """Save contracts to Excel file with better formatting"""
        if not contracts:
            self.logger.warning("No contracts to save")
            return
            
        if filename is None:
            timestamp = int(time.time())
            filename = f"hvac_contracts_{timestamp}.xlsx"
            
        filepath = f"{Config.PROCESSED_DATA_DIR}/{filename}"
        
        # Prepare data for Excel
        excel_data = []
        for contract in contracts:
            row = {
                'Title': contract.get('title', 'No title'),
                'Agency': contract.get('agency', 'Unknown'),
                'Location': contract.get('location', 'Unknown'),
                'Dates': contract.get('dates', 'No dates found'),
                'Estimated_Value': contract.get('estimated_value', 'Not specified'),
                'URL': contract.get('url', 'No URL'),
                'Search_Keyword': contract.get('search_keyword', ''),
                'HVAC_Relevance_Score': contract.get('hvac_relevance_score', 0),
                'Matching_Keywords': ', '.join(contract.get('matching_keywords', [])),
                'Contract_ID': contract.get('id', ''),
                'Raw_HTML_Preview': contract.get('raw_html', '')[:300] + '...' if contract.get('raw_html') else ''
            }
            excel_data.append(row)
        
        # Convert to DataFrame
        df = pd.DataFrame(excel_data)
        
        # Save to Excel with formatting
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='HVAC Contracts', index=False)
            
            # Get the workbook and worksheet
            workbook = writer.book
            worksheet = writer.sheets['HVAC Contracts']
            
            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                        
                adjusted_width = min(max_length + 2, 50)  # Cap at 50 characters
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        self.logger.info(f"Saved {len(contracts)} contracts to Excel file: {filepath}")
        return filepath