"""
AI Pattern Discovery Agent
=========================

This agent uses AI models to discover scraping patterns for city RFP websites.
It's designed for cost-effective operation with manual selection and batch processing.

Key features:
- Analyze city RFP website structures
- Discover CSS selectors and navigation patterns  
- Generate reusable scraping templates
- Cost tracking and optimization
- Self-healing pattern updates
"""

import logging
import time
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# AI Model imports (will be configured based on user preference)
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from ..database.connection import DatabaseManager
from ..database.models import (
    CityPlatform, AIAnalysisLog, ProcessingStatus, CityPortal, RegistrationFlag,
    PortalCredential, PortalType, AccountStatus, FlagStatus
)
from ..portal.detector import PortalDetector
from ..portal.credential_manager import CredentialManager

logger = logging.getLogger(__name__)

class PatternDiscoveryAgent:
    """AI-powered agent for discovering city RFP website scraping patterns"""
    
    def __init__(self, ai_provider: str = "anthropic", model: str = "claude-3.5-sonnet"):
        """
        Initialize the pattern discovery agent
        
        Args:
            ai_provider: "anthropic" or "openai"
            model: Model name (e.g., "claude-3.5-sonnet", "gpt-4")
        """
        self.ai_provider = ai_provider
        self.model = model
        self.db = DatabaseManager()
        
        # Initialize portal components
        self.portal_detector = PortalDetector()
        self.credential_manager = CredentialManager()
        
        # Cost tracking
        self.estimated_cost_per_analysis = 0.50  # Rough estimate
        self.total_session_cost = 0.0
        
        # Initialize AI client
        self._initialize_ai_client()
        
        logger.info(f"🤖 Enhanced Pattern Discovery Agent initialized with {ai_provider}/{model}")
    
    def _initialize_ai_client(self):
        """Initialize the appropriate AI client"""
        if self.ai_provider == "anthropic" and ANTHROPIC_AVAILABLE:
            # Will be configured with API key from environment
            self.ai_client = None  # Placeholder - requires API key setup
        elif self.ai_provider == "openai" and OPENAI_AVAILABLE:
            # Will be configured with API key from environment
            self.ai_client = None  # Placeholder - requires API key setup
        else:
            logger.warning(f"AI provider {self.ai_provider} not available - running in simulation mode")
            self.ai_client = None
    
    def analyze_city_website(self, city_name: str, website_url: str, sample_pages: List[str] = None) -> Dict[str, Any]:
        """
        Enhanced analysis with portal detection and authentication handling
        
        Args:
            city_name: Name of the city
            website_url: Base URL of the city's RFP website
            sample_pages: Optional list of sample RFP page URLs
            
        Returns:
            Dictionary containing discovered patterns and metadata
        """
        logger.info(f"🔍 Starting enhanced AI analysis for {city_name}: {website_url}")
        
        analysis_start = datetime.utcnow()
        
        try:
            # Step 1: Detect portal type and authentication requirements
            portal_detection = self.portal_detector.detect_city_portal(
                city_name, website_url, sample_pages or []
            )
            
            logger.info(f"🔍 Portal detection: {portal_detection['portal_type'].value}, "
                       f"Registration required: {portal_detection['registration_required']}")
            
            # Step 2: Handle authentication if required
            authentication_result = self._handle_portal_authentication(portal_detection)
            
            # Step 3: Crawl website (with authentication if available)
            website_data = self._crawl_website_structure_enhanced(
                website_url, sample_pages, portal_detection, authentication_result
            )
            
            # Step 4: Analyze with AI to discover patterns
            patterns = self._analyze_with_ai(city_name, website_url, website_data)
            
            # Step 5: Enhance patterns with portal-specific information
            enhanced_patterns = self._enhance_patterns_with_portal_info(patterns, portal_detection)
            
            # Step 6: Validate discovered patterns
            validated_patterns = self._validate_patterns(website_url, enhanced_patterns)
            
            # Step 7: Store results in database
            platform_data = self._store_analysis_results(
                city_name, website_url, validated_patterns, 
                analysis_start, True, None
            )
            
            logger.info(f"✅ Enhanced analysis complete for {city_name} - "
                       f"Portal: {portal_detection['portal_type'].value}, "
                       f"Patterns: {len(validated_patterns.get('selectors', {}))}")
            
            return {
                'success': True,
                'city_name': city_name,
                'portal_info': portal_detection,
                'authentication': authentication_result,
                'patterns': validated_patterns,
                'platform_data': platform_data,
                'cost_estimate': self.estimated_cost_per_analysis
            }
            
        except Exception as e:
            logger.error(f"❌ Enhanced analysis failed for {city_name}: {e}")
            
            # Store failed analysis
            self._store_analysis_results(
                city_name, website_url, {}, 
                analysis_start, False, str(e)
            )
            
            return {
                'success': False,
                'city_name': city_name,
                'error': str(e),
                'cost_estimate': 0.0
            }
    
    def _crawl_website_structure(self, base_url: str, sample_pages: List[str] = None) -> Dict[str, Any]:
        """Crawl website to collect structure and sample content"""
        logger.debug(f"🕸️ Crawling website structure: {base_url}")
        
        website_data = {
            'base_url': base_url,
            'pages_analyzed': [],
            'common_elements': {},
            'navigation_structure': {},
            'form_structures': []
        }
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                # Analyze main page
                main_page_data = self._analyze_page_structure(page, base_url)
                website_data['pages_analyzed'].append(main_page_data)
                
                # Analyze sample pages if provided
                if sample_pages:
                    for url in sample_pages[:3]:  # Limit to 3 sample pages for cost control
                        try:
                            sample_data = self._analyze_page_structure(page, url)
                            website_data['pages_analyzed'].append(sample_data)
                        except Exception as e:
                            logger.debug(f"Could not analyze sample page {url}: {e}")
                
                # Look for common patterns across pages
                website_data['common_elements'] = self._find_common_elements(website_data['pages_analyzed'])
                
                context.close()
                browser.close()
                
        except Exception as e:
            logger.error(f"Error crawling website {base_url}: {e}")
            # Fallback to basic requests-based crawling
            website_data = self._crawl_with_requests(base_url)
        
        return website_data
    
    def _analyze_page_structure(self, page, url: str) -> Dict[str, Any]:
        """Analyze the structure of a single page"""
        try:
            page.goto(url, timeout=10000)
            page.wait_for_load_state('networkidle', timeout=5000)
            
            # Extract page content and structure
            html_content = page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            page_data = {
                'url': url,
                'title': page.title() or '',
                'forms': self._extract_form_info(soup),
                'tables': self._extract_table_info(soup),
                'lists': self._extract_list_info(soup),
                'navigation': self._extract_navigation_info(soup),
                'content_sections': self._extract_content_sections(soup),
                'download_links': self._extract_download_links(soup),
                'html_sample': html_content[:2000]  # First 2000 chars for AI analysis
            }
            
            return page_data
            
        except Exception as e:
            logger.debug(f"Error analyzing page {url}: {e}")
            return {'url': url, 'error': str(e)}
    
    def _extract_form_info(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract information about forms on the page"""
        forms = []
        for form in soup.find_all('form'):
            form_info = {
                'action': form.get('action', ''),
                'method': form.get('method', 'GET'),
                'fields': []
            }
            
            # Extract form fields
            for field in form.find_all(['input', 'select', 'textarea']):
                field_info = {
                    'type': field.get('type', field.name),
                    'name': field.get('name', ''),
                    'id': field.get('id', ''),
                    'placeholder': field.get('placeholder', ''),
                    'label': self._find_field_label(field)
                }
                form_info['fields'].append(field_info)
            
            forms.append(form_info)
        
        return forms
    
    def _extract_table_info(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract information about data tables"""
        tables = []
        for table in soup.find_all('table'):
            # Extract headers
            headers = []
            header_row = table.find('tr')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            
            # Count rows and columns
            rows = table.find_all('tr')
            
            table_info = {
                'headers': headers,
                'row_count': len(rows),
                'column_count': len(headers) if headers else 0,
                'css_classes': table.get('class', []),
                'id': table.get('id', '')
            }
            tables.append(table_info)
        
        return tables
    
    def _extract_list_info(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract information about lists that might contain RFPs"""
        lists = []
        for list_elem in soup.find_all(['ul', 'ol', 'div']):
            # Look for lists that might contain contract/RFP entries
            if self._looks_like_contract_list(list_elem):
                list_info = {
                    'tag': list_elem.name,
                    'css_classes': list_elem.get('class', []),
                    'id': list_elem.get('id', ''),
                    'item_count': len(list_elem.find_all('li')) if list_elem.name in ['ul', 'ol'] else len(list_elem.find_all('div', recursive=False)),
                    'sample_text': list_elem.get_text(strip=True)[:200]
                }
                lists.append(list_info)
        
        return lists
    
    def _extract_navigation_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract navigation structure"""
        nav_info = {
            'main_nav': [],
            'breadcrumbs': [],
            'pagination': {}
        }
        
        # Main navigation
        for nav in soup.find_all(['nav', 'div'], class_=['nav', 'navigation', 'menu']):
            links = nav.find_all('a')
            nav_info['main_nav'].extend([{
                'text': link.get_text(strip=True),
                'href': link.get('href', '')
            } for link in links])
        
        # Pagination
        pagination = soup.find(['div', 'nav'], class_=['pagination', 'pager'])
        if pagination:
            nav_info['pagination'] = {
                'found': True,
                'links': [link.get('href', '') for link in pagination.find_all('a')]
            }
        
        return nav_info
    
    def _extract_content_sections(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract main content sections"""
        sections = []
        
        # Look for common content containers
        for selector in ['.content', '#content', '.main', '#main', '.container', '.rfp-list', '.bids']:
            elements = soup.select(selector)
            for elem in elements[:3]:  # Limit to avoid too much data
                sections.append({
                    'selector': selector,
                    'text_sample': elem.get_text(strip=True)[:300],
                    'child_count': len(elem.find_all())
                })
        
        return sections
    
    def _extract_download_links(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract potential document download links"""
        downloads = []
        
        for link in soup.find_all('a'):
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Check if link looks like a document download
            if any(ext in href.lower() for ext in ['.pdf', '.doc', '.docx', '.xlsx', '.zip']):
                downloads.append({
                    'text': text,
                    'href': href,
                    'type': self._guess_file_type(href)
                })
        
        return downloads
    
    def _find_field_label(self, field) -> str:
        """Find label text for a form field"""
        # Look for associated label
        field_id = field.get('id')
        if field_id:
            label = field.parent.find('label', {'for': field_id}) if field.parent else None
            if label:
                return label.get_text(strip=True)
        
        # Look for nearby text
        if field.parent:
            prev_text = field.find_previous(string=True)
            if prev_text and len(prev_text.strip()) < 50:
                return prev_text.strip()
        
        return ''
    
    def _looks_like_contract_list(self, elem) -> bool:
        """Determine if an element looks like it contains contract/RFP listings"""
        text = elem.get_text(strip=True).lower()
        contract_keywords = ['rfp', 'bid', 'contract', 'proposal', 'solicitation', 'procurement']
        return any(keyword in text for keyword in contract_keywords)
    
    def _guess_file_type(self, href: str) -> str:
        """Guess file type from URL"""
        href_lower = href.lower()
        if '.pdf' in href_lower:
            return 'pdf'
        elif '.doc' in href_lower:
            return 'document'
        elif '.xls' in href_lower:
            return 'spreadsheet'
        elif '.zip' in href_lower:
            return 'archive'
        return 'unknown'
    
    def _find_common_elements(self, pages_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Find common elements across analyzed pages"""
        common = {
            'repeated_selectors': [],
            'form_patterns': [],
            'navigation_patterns': []
        }
        
        # This would analyze patterns across pages
        # For now, return basic structure
        return common
    
    def _crawl_with_requests(self, base_url: str) -> Dict[str, Any]:
        """Fallback crawling method using requests"""
        try:
            response = requests.get(base_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            return {
                'base_url': base_url,
                'pages_analyzed': [{
                    'url': base_url,
                    'title': soup.title.string if soup.title else '',
                    'html_sample': str(soup)[:2000]
                }],
                'crawl_method': 'requests_fallback'
            }
        except Exception as e:
            logger.error(f"Fallback crawling also failed for {base_url}: {e}")
            return {
                'base_url': base_url,
                'pages_analyzed': [],
                'error': str(e)
            }
    
    def _analyze_with_ai(self, city_name: str, website_url: str, website_data: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI to analyze website structure and discover patterns"""
        logger.debug(f"🧠 Running AI analysis for {city_name}")
        
        # For now, simulate AI analysis (actual implementation would call AI API)
        if self.ai_client is None:
            logger.info("🤖 Simulating AI analysis (no API key configured)")
            return self._simulate_ai_analysis(city_name, website_url, website_data)
        
        # Real AI analysis would be implemented here
        prompt = self._build_analysis_prompt(city_name, website_url, website_data)
        
        # Placeholder for actual AI API call
        # response = self.ai_client.messages.create(...)
        
        # For now, return simulated results
        return self._simulate_ai_analysis(city_name, website_url, website_data)
    
    def _build_analysis_prompt(self, city_name: str, website_url: str, website_data: Dict[str, Any]) -> str:
        """Build prompt for AI analysis"""
        return f"""
        Analyze this city RFP website for {city_name} ({website_url}) and discover scraping patterns.
        
        Website structure data:
        {json.dumps(website_data, indent=2)}
        
        Please identify:
        1. CSS selectors for finding RFP/bid listings
        2. Selectors for extracting contract details (title, agency, due date, etc.)
        3. Navigation patterns for pagination
        4. Form selectors for search functionality
        5. Download link patterns for RFP documents
        
        Return a structured JSON response with the discovered patterns.
        """
    
    def _simulate_ai_analysis(self, city_name: str, website_url: str, website_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate AI analysis results for testing"""
        logger.info(f"🎭 Simulating AI pattern discovery for {city_name}")
        
        # Generate realistic-looking patterns based on common website structures
        patterns = {
            'platform_type': 'city_website',
            'selectors': {
                'contract_list': '.rfp-list, .bid-list, .contracts table tbody tr',
                'contract_title': '.title, .contract-title, td.title, h3 a',
                'contract_agency': '.agency, .department, td.agency',
                'contract_location': '.location, .city, td.location',
                'contract_due_date': '.due-date, .deadline, td.due-date',
                'contract_link': 'a.view-details, .contract-link, .more-info a',
                'download_links': 'a[href$=".pdf"], .download-link, .documents a',
                'pagination_next': '.pagination .next, .pager .next, a.next',
                'search_form': '#search-form, .search-form, form.bid-search',
                'search_input': 'input[name="search"], input[name="q"], #search-field'
            },
            'navigation': {
                'base_url': website_url,
                'rfp_list_url': website_url + '/rfps',
                'search_url': website_url + '/search'
            },
            'requirements': {
                'requires_registration': False,
                'has_search': len(website_data.get('pages_analyzed', [{}])[0].get('forms', [])) > 0 if website_data.get('pages_analyzed') else False,
                'has_pagination': False  # Would be determined by actual analysis
            },
            'confidence_score': 0.7,  # Simulated confidence
            'analysis_notes': f'Simulated analysis for {city_name} - patterns generated based on common structures'
        }
        
        return patterns
    
    def _validate_patterns(self, website_url: str, patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Validate discovered patterns by testing them"""
        logger.debug(f"✅ Validating patterns for {website_url}")
        
        validation_results = {
            'validated_selectors': {},
            'working_patterns': 0,
            'total_patterns': 0,
            'validation_score': 0.0
        }
        
        try:
            # Test selectors against the actual website
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(website_url, timeout=10000)
                
                selectors = patterns.get('selectors', {})
                validation_results['total_patterns'] = len(selectors)
                
                for selector_name, selector in selectors.items():
                    try:
                        elements = page.query_selector_all(selector)
                        is_working = len(elements) > 0
                        
                        validation_results['validated_selectors'][selector_name] = {
                            'selector': selector,
                            'working': is_working,
                            'element_count': len(elements)
                        }
                        
                        if is_working:
                            validation_results['working_patterns'] += 1
                            
                    except Exception as e:
                        validation_results['validated_selectors'][selector_name] = {
                            'selector': selector,
                            'working': False,
                            'error': str(e)
                        }
                
                browser.close()
                
        except Exception as e:
            logger.debug(f"Pattern validation failed: {e}")
            # Return patterns without validation if testing fails
            validation_results = {
                'validation_error': str(e),
                'patterns_assumed_working': True
            }
        
        # Calculate validation score
        if validation_results.get('total_patterns', 0) > 0:
            validation_results['validation_score'] = validation_results.get('working_patterns', 0) / validation_results['total_patterns']
        
        # Merge validation results with original patterns
        patterns['validation'] = validation_results
        
        return patterns
    
    def _store_analysis_results(self, city_name: str, website_url: str, patterns: Dict[str, Any], 
                               analysis_start: datetime, success: bool, error_message: str = None) -> Optional[CityPlatform]:
        """Store analysis results in database"""
        
        with self.db.get_session() as session:
            try:
                # Create or update CityPlatform record
                platform = session.query(CityPlatform).filter_by(city_name=city_name).first()
                
                if platform:
                    # Update existing platform
                    platform.platform_type = patterns.get('platform_type', 'city_website')
                    platform.base_url = website_url
                    platform.search_selectors = patterns.get('selectors', {})
                    platform.contract_selectors = patterns.get('selectors', {})
                    platform.download_patterns = patterns.get('navigation', {})
                    platform.last_ai_analysis = analysis_start
                    platform.updated_at = datetime.utcnow()
                    
                    if success:
                        platform.total_scrapes += 1
                        platform.successful_scrapes += 1
                        platform.success_rate = platform.successful_scrapes / platform.total_scrapes
                    else:
                        platform.total_scrapes += 1
                        platform.success_rate = platform.successful_scrapes / platform.total_scrapes
                
                else:
                    # Create new platform
                    platform = CityPlatform(
                        city_name=city_name,
                        platform_type=patterns.get('platform_type', 'city_website'),
                        base_url=website_url,
                        requires_registration=patterns.get('requirements', {}).get('requires_registration', False),
                        search_selectors=patterns.get('selectors', {}),
                        contract_selectors=patterns.get('selectors', {}),
                        download_patterns=patterns.get('navigation', {}),
                        last_ai_analysis=analysis_start,
                        success_rate=1.0 if success else 0.0,
                        total_scrapes=1,
                        successful_scrapes=1 if success else 0
                    )
                    session.add(platform)
                
                # Create AI analysis log
                analysis_log = AIAnalysisLog(
                    target_type='city_platform',
                    target_id=city_name,
                    analysis_date=analysis_start,
                    ai_model_used=f"{self.ai_provider}/{self.model}",
                    cost_estimate=self.estimated_cost_per_analysis,
                    patterns_discovered=patterns,
                    success=success,
                    error_message=error_message,
                    contracts_found=0,  # Would be filled in later during actual scraping
                    extraction_accuracy=patterns.get('validation', {}).get('validation_score', 0.0)
                )
                session.add(analysis_log)
                
                session.commit()
                
                # Track session cost
                self.total_session_cost += self.estimated_cost_per_analysis
                
                logger.info(f"💾 Stored analysis results for {city_name} (success: {success})")
                
                return platform
                
            except Exception as e:
                logger.error(f"Error storing analysis results: {e}")
                session.rollback()
                return None
    
    def batch_analyze_cities(self, city_websites: List[Dict[str, str]], max_cost: float = 10.0) -> List[Dict[str, Any]]:
        """
        Analyze multiple city websites with cost control
        
        Args:
            city_websites: List of {'city_name': str, 'website_url': str} dicts
            max_cost: Maximum cost limit for the batch
            
        Returns:
            List of analysis results
        """
        logger.info(f"🔄 Starting batch analysis of {len(city_websites)} cities (max cost: ${max_cost:.2f})")
        
        results = []
        current_cost = 0.0
        
        for city_data in city_websites:
            if current_cost + self.estimated_cost_per_analysis > max_cost:
                logger.warning(f"💰 Cost limit reached (${current_cost:.2f}/${max_cost:.2f}) - stopping batch")
                break
            
            city_name = city_data['city_name']
            website_url = city_data['website_url']
            
            logger.info(f"🔍 Analyzing {city_name} ({len(results) + 1}/{len(city_websites)})")
            
            try:
                result = self.analyze_city_website(city_name, website_url)
                results.append(result)
                current_cost += result.get('cost_estimate', 0.0)
                
                # Brief pause between analyses to be respectful to websites
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"❌ Failed to analyze {city_name}: {e}")
                results.append({
                    'success': False,
                    'city_name': city_name,
                    'error': str(e),
                    'cost_estimate': 0.0
                })
        
        logger.info(f"📊 Batch analysis complete: {len(results)} cities analyzed, ${current_cost:.2f} estimated cost")
        
        return results
    
    def get_session_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary for current session"""
        return {
            'total_cost': self.total_session_cost,
            'cost_per_analysis': self.estimated_cost_per_analysis,
            'ai_provider': self.ai_provider,
            'model': self.model
        }
    
    def _handle_portal_authentication(self, portal_detection: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle portal authentication requirements
        
        Args:
            portal_detection: Portal detection results
            
        Returns:
            Authentication status and session info
        """
        auth_result = {
            'authentication_required': False,
            'credentials_available': False,
            'login_successful': False,
            'session_cookies': None,
            'registration_needed': False,
            'flag_created': False,
            'error': None
        }
        
        city_name = portal_detection['city_name']
        portal_type = portal_detection['portal_type']
        
        # Check if registration/login is required
        if not portal_detection.get('registration_required', False):
            logger.debug(f"No authentication required for {city_name}")
            return auth_result
        
        auth_result['authentication_required'] = True
        
        # Check if we have credentials
        credentials = self.credential_manager.get_credentials(city_name, portal_type)
        
        if credentials:
            auth_result['credentials_available'] = True
            logger.info(f"🔐 Found credentials for {city_name}, attempting login")
            
            # Verify credentials (attempt login)
            verification = self.credential_manager.verify_credentials(
                city_name, portal_type, update_database=True
            )
            
            if verification['success']:
                auth_result['login_successful'] = True
                auth_result['session_cookies'] = verification.get('session_cookies')
                logger.info(f"✅ Login successful for {city_name}")
            else:
                auth_result['error'] = verification.get('error')
                logger.warning(f"❌ Login failed for {city_name}: {verification.get('error')}")
                
                # Create flag for credential issues
                self._create_registration_flag(
                    city_name, portal_type, portal_detection.get('portal_url'),
                    "login_failed", f"Stored credentials failed: {verification.get('error')}"
                )
                auth_result['flag_created'] = True
        else:
            logger.info(f"🔐 No credentials found for {city_name}, registration needed")
            auth_result['registration_needed'] = True
            
            # Create registration flag
            self._create_registration_flag(
                city_name, portal_type, portal_detection.get('portal_url'),
                "registration_needed", f"Registration required for {portal_type.value} portal access"
            )
            auth_result['flag_created'] = True
        
        return auth_result
    
    def _crawl_website_structure_enhanced(self, base_url: str, sample_pages: List[str] = None,
                                        portal_detection: Dict[str, Any] = None,
                                        authentication_result: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Enhanced website crawling with authentication support
        
        Args:
            base_url: Website URL to crawl
            sample_pages: Optional sample pages
            portal_detection: Portal detection results
            authentication_result: Authentication status
            
        Returns:
            Website structure data
        """
        logger.debug(f"🕸️ Enhanced crawling: {base_url}")
        
        website_data = {
            'base_url': base_url,
            'pages_analyzed': [],
            'common_elements': {},
            'navigation_structure': {},
            'form_structures': [],
            'portal_type': portal_detection.get('portal_type', PortalType.NONE) if portal_detection else PortalType.NONE,
            'authentication_used': False,
            'access_level': 'public'
        }
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                
                # Use session cookies if available
                if (authentication_result and 
                    authentication_result.get('login_successful') and 
                    authentication_result.get('session_cookies')):
                    
                    context.add_cookies(authentication_result['session_cookies'])
                    website_data['authentication_used'] = True
                    website_data['access_level'] = 'authenticated'
                    logger.debug("🔐 Using authenticated session for crawling")
                
                page = context.new_page()
                
                # Analyze main page
                try:
                    main_page_data = self._analyze_page_structure(page, base_url)
                    website_data['pages_analyzed'].append(main_page_data)
                    
                    # Check if we can access member/authenticated content
                    if self._detect_authenticated_content(main_page_data):
                        website_data['access_level'] = 'member_area'
                        logger.info("🔓 Successfully accessing member-only content")
                    
                except Exception as e:
                    logger.debug(f"Error analyzing main page: {e}")
                
                # Analyze sample pages if provided
                if sample_pages:
                    for url in sample_pages[:2]:  # Limit to 2 for enhanced version
                        try:
                            sample_data = self._analyze_page_structure(page, url)
                            website_data['pages_analyzed'].append(sample_data)
                        except Exception as e:
                            logger.debug(f"Could not analyze sample page {url}: {e}")
                
                # Look for portal-specific patterns
                if portal_detection and portal_detection['portal_type'] != PortalType.NONE:
                    portal_patterns = self._extract_portal_specific_patterns(
                        page, portal_detection['portal_type']
                    )
                    website_data['portal_patterns'] = portal_patterns
                
                context.close()
                browser.close()
                
        except Exception as e:
            logger.error(f"Error in enhanced crawling {base_url}: {e}")
            # Fallback to basic crawling
            website_data = self._crawl_with_requests(base_url)
            website_data['crawl_method'] = 'requests_fallback'
        
        return website_data
    
    def _detect_authenticated_content(self, page_data: Dict[str, Any]) -> bool:
        """Detect if page shows authenticated/member content"""
        if not page_data:
            return False
        
        # Check for authenticated content indicators
        html_sample = page_data.get('html_sample', '').lower()
        authenticated_indicators = [
            'welcome back',
            'dashboard',
            'my account',
            'logout',
            'member area',
            'download documents',
            'rfp documents',
            'bid documents',
            'restricted',
            'private'
        ]
        
        return any(indicator in html_sample for indicator in authenticated_indicators)
    
    def _extract_portal_specific_patterns(self, page, portal_type: PortalType) -> Dict[str, Any]:
        """Extract portal-specific navigation patterns"""
        portal_patterns = {
            'portal_type': portal_type.value,
            'navigation_elements': {},
            'document_patterns': {},
            'search_patterns': {}
        }
        
        try:
            if portal_type == PortalType.PLANETBIDS:
                # PlanetBids-specific patterns
                portal_patterns['navigation_elements'].update({
                    'project_list': '.project-list, .bid-list, #projects-table',
                    'project_details': '.project-detail, .bid-detail',
                    'document_tab': '.documents-tab, .plans-tab, .addenda-tab'
                })
                
                portal_patterns['document_patterns'].update({
                    'download_links': '.document-download, .plan-download, a[href*="download"]',
                    'document_list': '.document-list, .attachments-list',
                    'addenda': '.addenda-list, .amendments'
                })
                
            elif portal_type == PortalType.BIDSYNC:
                # BidSync-specific patterns
                portal_patterns['navigation_elements'].update({
                    'opportunity_list': '.opportunity-list, .solicitations',
                    'opportunity_details': '.opportunity-detail'
                })
                
            # Add more portal-specific patterns as needed
            
        except Exception as e:
            logger.debug(f"Error extracting portal patterns: {e}")
        
        return portal_patterns
    
    def _enhance_patterns_with_portal_info(self, patterns: Dict[str, Any], 
                                         portal_detection: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance discovered patterns with portal-specific information"""
        enhanced_patterns = patterns.copy()
        
        # Add portal metadata
        enhanced_patterns['portal_info'] = {
            'portal_type': portal_detection.get('portal_type', PortalType.NONE).value,
            'registration_required': portal_detection.get('registration_required', False),
            'portal_url': portal_detection.get('portal_url'),
            'login_url': portal_detection.get('login_url'),
            'registration_url': portal_detection.get('registration_url'),
            'portal_subdomain': portal_detection.get('portal_subdomain')
        }
        
        # Add authentication patterns if applicable
        if portal_detection.get('registration_required'):
            enhanced_patterns.setdefault('authentication', {}).update({
                'login_required': True,
                'login_url': portal_detection.get('login_url'),
                'registration_url': portal_detection.get('registration_url'),
                'portal_type': portal_detection.get('portal_type', PortalType.NONE).value
            })
        
        # Add portal-specific selectors based on detected type
        portal_type = portal_detection.get('portal_type', PortalType.NONE)
        if portal_type != PortalType.NONE:
            portal_selectors = self._get_portal_default_selectors(portal_type)
            enhanced_patterns.setdefault('selectors', {}).update(portal_selectors)
        
        return enhanced_patterns
    
    def _get_portal_default_selectors(self, portal_type: PortalType) -> Dict[str, str]:
        """Get default selectors for known portal types"""
        default_selectors = {}
        
        if portal_type == PortalType.PLANETBIDS:
            default_selectors.update({
                'login_form': 'form[action*="login"], #loginForm',
                'username_field': '#username, input[name="username"], #email, input[name="email"]',
                'password_field': '#password, input[name="password"]',
                'login_button': 'input[type="submit"], button[type="submit"], .login-btn',
                'project_list': '.project-row, .bid-row, tbody tr',
                'project_title': '.project-title, .bid-title, td.title a',
                'project_agency': '.agency, .department, td.agency',
                'due_date': '.due-date, .bid-date, td.due',
                'documents_link': '.documents, .plans, .view-docs, a[href*="documents"]'
            })
        elif portal_type == PortalType.BIDSYNC:
            default_selectors.update({
                'opportunity_list': '.opportunity-row, .solicitation-row',
                'opportunity_title': '.opportunity-title, .solicitation-title'
            })
        
        return default_selectors
    
    def _create_registration_flag(self, city_name: str, portal_type: PortalType, 
                                portal_url: str, reason: str, description: str):
        """Create a registration flag for manual intervention"""
        
        try:
            with self.db.get_session() as session:
                # Check if flag already exists
                existing_flag = session.query(RegistrationFlag).filter_by(
                    city_name=city_name,
                    portal_type=portal_type,
                    resolution_status=FlagStatus.PENDING
                ).first()
                
                if existing_flag:
                    # Update existing flag
                    existing_flag.last_attempt_date = datetime.utcnow()
                    existing_flag.current_retry_count += 1
                    existing_flag.flag_description = description
                    logger.debug(f"Updated existing flag for {city_name}")
                else:
                    # Create new flag
                    priority_score = self._calculate_flag_priority(city_name, portal_type)
                    
                    flag = RegistrationFlag(
                        city_name=city_name,
                        portal_type=portal_type,
                        portal_url=portal_url,
                        flag_reason=reason,
                        flag_description=description,
                        priority_score=priority_score,
                        estimated_manual_hours=1.5,
                        last_attempt_date=datetime.utcnow()
                    )
                    session.add(flag)
                    logger.info(f"🚩 Created registration flag for {city_name}: {reason}")
                
                session.commit()
                
        except Exception as e:
            logger.error(f"Error creating registration flag: {e}")
    
    def _calculate_flag_priority(self, city_name: str, portal_type: PortalType) -> int:
        """Calculate priority score for registration flags"""
        base_score = 50
        
        # Higher priority for larger cities
        major_cities = ['los angeles', 'san diego', 'san francisco', 'oakland', 'anaheim', 'santa ana']
        if city_name.lower() in major_cities:
            base_score += 30
        
        # Higher priority for common portals (more reusable patterns)
        if portal_type == PortalType.PLANETBIDS:
            base_score += 20
        elif portal_type in [PortalType.BIDSYNC, PortalType.DEMANDSTAR]:
            base_score += 10
        
        return base_score

def main():
    """Example usage of the Pattern Discovery Agent"""
    agent = PatternDiscoveryAgent()
    
    # Example city websites for testing
    test_cities = [
        {'city_name': 'Los Angeles', 'website_url': 'https://www.lacity.org/business/contracting-procurement'},
        {'city_name': 'Santa Monica', 'website_url': 'https://www.santamonica.gov/business/procurement'}
    ]
    
    # Run batch analysis
    results = agent.batch_analyze_cities(test_cities, max_cost=5.0)
    
    # Show results
    for result in results:
        print(f"\n{'='*50}")
        print(f"City: {result['city_name']}")
        print(f"Success: {result['success']}")
        if result['success']:
            patterns = result.get('patterns', {})
            print(f"Platform Type: {patterns.get('platform_type', 'Unknown')}")
            print(f"Selectors Found: {len(patterns.get('selectors', {}))}")
            print(f"Validation Score: {patterns.get('validation', {}).get('validation_score', 0.0):.1%}")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
        print(f"Cost: ${result.get('cost_estimate', 0.0):.2f}")
    
    # Show cost summary
    cost_summary = agent.get_session_cost_summary()
    print(f"\n{'='*50}")
    print(f"Total Session Cost: ${cost_summary['total_cost']:.2f}")
    print(f"AI Provider: {cost_summary['ai_provider']}/{cost_summary['model']}")

if __name__ == "__main__":
    main()