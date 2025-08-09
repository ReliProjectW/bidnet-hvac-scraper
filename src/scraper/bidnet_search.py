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
from auth.bidnet_auth import BidNetAuthenticator

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

class BidNetSearcher:
    def __init__(self):
        self.authenticator = BidNetAuthenticator()
        self.session = None
        self.driver = None
        self.logger = logging.getLogger(__name__)
        
    def get_authenticated_session(self):
        """Get authenticated session"""
        if not self.session:
            self.session = self.authenticator.get_authenticated_session()
        return self.session
    
    def setup_browser(self):
        """Set up Selenium browser for JavaScript-heavy pages"""
        if self.driver:
            return self.driver
            
        chrome_options = Options()
        if Config.BROWSER_SETTINGS.get("headless", False):  # Set to False for debugging
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.implicitly_wait(10)
        
        return self.driver
        
    def search_with_browser(self, keyword: str, location_filters: List[str]) -> List[Dict[str, Any]]:
        """Search using browser automation (for JavaScript-heavy sites)"""
        contracts = []
        
        try:
            # Setup browser
            browser = self.setup_browser()
            
            # Navigate to main page first, then load cookies
            self.logger.info("Loading authentication cookies in browser...")
            browser.get(Config.BASE_URL)
            
            # Load cookies from authentication
            if hasattr(self.authenticator, 'load_cookies_to_selenium'):
                # Update load_cookies_to_selenium to work with this driver
                self.authenticator.driver = browser
                self.authenticator.load_cookies_to_selenium()
            
            # Navigate to search page
            search_url = f"{Config.BASE_URL}private/supplier/solicitations/search"
            self.logger.info(f"Navigating to search page with browser: {search_url}")
            browser.get(search_url)
            
            # Wait for page to load (reduced timeout)
            wait = WebDriverWait(browser, 5)
            
            # Look for search input fields
            search_field = None
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
                'input[type="search"]'
            ]
            
            for selector in search_selectors:
                try:
                    search_field = browser.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue
                    
            if search_field:
                self.logger.info(f"Found search field, entering keyword: {keyword}")
                search_field.clear()
                search_field.send_keys(keyword)
                
                # Look for search button
                search_button = None
                button_selectors = [
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'button:contains("Search")',
                    '.search-button',
                    '#searchButton',
                    '[data-testid*="search"]'
                ]
                
                for selector in button_selectors:
                    try:
                        if 'contains' in selector:
                            search_button = browser.find_element(By.XPATH, "//button[contains(text(), 'Search')]")
                        else:
                            search_button = browser.find_element(By.CSS_SELECTOR, selector)
                        break
                    except NoSuchElementException:
                        continue
                
                if search_button:
                    self.logger.info("Clicking search button...")
                    search_button.click()
                else:
                    # Try pressing Enter
                    from selenium.webdriver.common.keys import Keys
                    search_field.send_keys(Keys.RETURN)
                
                # Wait for results to load (reduced)
                time.sleep(2)
                
                # Save the results page
                results_html = browser.page_source
                debug_file = f"{Config.DATA_DIR}/debug_browser_results.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(results_html)
                self.logger.info(f"Saved browser results HTML: {debug_file}")
                
                # Parse results with our existing parser
                contracts = self._parse_search_results(results_html, keyword)
                
            else:
                self.logger.warning("Could not find search field on page")
                # Save the page for debugging
                page_html = browser.page_source
                debug_file = f"{Config.DATA_DIR}/debug_search_page_browser.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(page_html)
                self.logger.info(f"Saved search page HTML: {debug_file}")
                
        except Exception as e:
            self.logger.error(f"Browser search failed for '{keyword}': {str(e)}")
        
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None
                
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
                # Primary: Table rows found by inspector (most likely contract listings)
                'tr.mets-table-row.odd',
                'tr.even.mets-table-row', 
                'tr[class*="mets-table-row"]',
                
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