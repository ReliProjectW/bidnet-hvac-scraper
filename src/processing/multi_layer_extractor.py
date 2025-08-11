"""
Multi-Layer Extraction Pipeline
==============================

Orchestrates the complete extraction process:
1. BidNet contracts (using existing working scraper)
2. City RFP website navigation and detailed extraction
3. PDF document download and processing

Features:
- Seamless integration with existing BidNet scraper
- AI pattern-based city website extraction  
- Cost-controlled processing with manual selection
- PDF download and text extraction
- Database persistence and progress tracking
"""

import logging
import time
import os
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urljoin, urlparse
import requests
from pathlib import Path

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import PyPDF2
import pandas as pd

from ..database.connection import DatabaseManager
from ..database.models import (
    Contract, CityContract, CityPlatform, PlanDownload, 
    ProcessingStatus, ProcessingQueue
)
from ..ai_agents.pattern_discovery_agent import PatternDiscoveryAgent
from ..pdf.downloader import PDFDownloader
from ..portal.credential_manager import CredentialManager
from ..portal.pattern_library import PortalPatternLibrary

logger = logging.getLogger(__name__)

class MultiLayerExtractor:
    """
    Orchestrates multi-layer extraction: BidNet → City RFP → PDF
    """
    
    def __init__(self):
        self.db = DatabaseManager()
        self.ai_agent = PatternDiscoveryAgent()
        self.pdf_downloader = PDFDownloader()
        self.credential_manager = CredentialManager()
        self.pattern_library = PortalPatternLibrary()
        
        # Processing statistics
        self.stats = {
            'contracts_processed': 0,
            'city_details_extracted': 0,
            'pdfs_downloaded': 0,
            'portal_logins': 0,
            'flags_created': 0,
            'errors': []
        }
        
        logger.info("🏗️ Enhanced Multi-Layer Extractor with portal support initialized")
    
    def extract_contract_details(self, contract_id: int, city_url: str, 
                                contract_title: str = None, agency: str = None) -> Dict[str, Any]:
        """
        Extract RFP details for a single contract using progressive harvest approach
        
        Args:
            contract_id: Contract ID from database
            city_url: City website URL to search for RFP
            contract_title: Contract title to search for
            agency: Agency name
            
        Returns:
            Extraction result with documents found or error details
        """
        logger.debug(f"🔍 Extracting contract details for ID {contract_id} from {city_url}")
        
        extraction_result = {
            'success': False,
            'contract_id': contract_id,
            'city_url': city_url,
            'documents': [],
            'rfp_page_url': None,
            'portal_detected': False,
            'portal_type': None,
            'authentication_required': False,
            'error': None,
            'processing_time': 0.0,
            'cost_estimate': 0.0
        }
        
        start_time = time.time()
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                # Step 1: Navigate to city website
                try:
                    page.goto(city_url, timeout=10000)
                    page.wait_for_load_state('networkidle', timeout=5000)
                except Exception as e:
                    extraction_result['error'] = f"Failed to load city website: {str(e)}"
                    return extraction_result
                
                # Step 2: Look for procurement/RFP section
                rfp_page_url = self._find_rfp_page(page, city_url, contract_title)
                extraction_result['rfp_page_url'] = rfp_page_url
                
                if not rfp_page_url:
                    extraction_result['error'] = "Could not find procurement/RFP section on city website"
                    return extraction_result
                
                # Step 3: Navigate to RFP page if different from main page
                if rfp_page_url != city_url:
                    try:
                        page.goto(rfp_page_url, timeout=10000)
                        page.wait_for_load_state('networkidle', timeout=5000)
                    except Exception as e:
                        extraction_result['error'] = f"Failed to load RFP page: {str(e)}"
                        return extraction_result
                
                # Step 4: Search for the specific contract
                contract_found = self._search_for_contract(page, contract_title, agency)
                
                if not contract_found:
                    extraction_result['error'] = f"Contract '{contract_title[:50]}...' not found on RFP page"
                    return extraction_result
                
                # Step 5: Extract document links
                documents = self._extract_document_links(page, contract_title)
                extraction_result['documents'] = documents
                
                if documents:
                    extraction_result['success'] = True
                    logger.debug(f"✅ Found {len(documents)} documents for contract {contract_id}")
                else:
                    extraction_result['error'] = "No downloadable documents found for this contract"
                
                context.close()
                browser.close()
        
        except Exception as e:
            logger.error(f"Error during contract extraction: {e}")
            extraction_result['error'] = f"Technical error: {str(e)}"
        
        finally:
            extraction_result['processing_time'] = time.time() - start_time
        
        return extraction_result
    
    def _find_rfp_page(self, page, base_url: str, contract_title: str = None) -> Optional[str]:
        """Find the procurement/RFP section on the city website"""
        # Common procurement page indicators
        procurement_selectors = [
            'a[href*="procurement"]',
            'a[href*="bid"]', 
            'a[href*="rfp"]',
            'a[href*="contract"]',
            'a[href*="business"]',
            'a:contains("Procurement")',
            'a:contains("Bids")',
            'a:contains("RFP")', 
            'a:contains("Contracts")',
            'a:contains("Business")'
        ]
        
        for selector in procurement_selectors:
            try:
                elements = page.query_selector_all(selector)
                for element in elements[:3]:  # Check first 3 matches
                    href = element.get_attribute('href')
                    text = element.text_content() or ''
                    
                    if href and any(keyword in text.lower() for keyword in ['procurement', 'bid', 'rfp', 'contract']):
                        # Convert relative URLs to absolute
                        if href.startswith('/'):
                            href = urljoin(base_url, href)
                        elif not href.startswith('http'):
                            continue
                        
                        return href
            except Exception as e:
                logger.debug(f"Error with selector {selector}: {e}")
                continue
        
        # If no specific procurement page found, return base URL
        return base_url
    
    def _search_for_contract(self, page, contract_title: str, agency: str = None) -> bool:
        """Search for the specific contract on the RFP page"""
        if not contract_title:
            return True  # Can't search without title, assume it's there
        
        # Extract key words from contract title for searching
        title_words = contract_title.lower().split()
        key_words = [word for word in title_words if len(word) > 3][:5]  # Top 5 significant words
        
        # Get page content
        page_content = page.content().lower()
        
        # Check if enough key words are present
        matches = sum(1 for word in key_words if word in page_content)
        match_ratio = matches / len(key_words) if key_words else 0
        
        # Consider it found if at least 60% of key words match
        found = match_ratio >= 0.6
        
        if found:
            logger.debug(f"Contract match: {matches}/{len(key_words)} key words found")
        else:
            logger.debug(f"Contract not found: only {matches}/{len(key_words)} key words matched")
        
        return found
    
    def _extract_document_links(self, page, contract_title: str = None) -> List[Dict[str, Any]]:
        """Extract downloadable document links from the RFP page"""
        documents = []
        
        # Document link selectors
        document_selectors = [
            'a[href$=".pdf"]',
            'a[href*=".pdf"]',
            'a[href$=".doc"]',
            'a[href$=".docx"]', 
            'a[href$=".xlsx"]',
            'a[href*="download"]',
            'a:contains("PDF")',
            'a:contains("Download")',
            'a:contains("Document")',
            '.download-link',
            '.document-link',
            '.attachment'
        ]
        
        for selector in document_selectors:
            try:
                elements = page.query_selector_all(selector)
                for element in elements:
                    href = element.get_attribute('href')
                    text = element.text_content() or ''
                    
                    if href and any(ext in href.lower() for ext in ['.pdf', '.doc', '.xlsx', 'download']):
                        # Convert relative URLs to absolute
                        if href.startswith('/'):
                            base_url = page.url
                            href = urljoin(base_url, href)
                        elif not href.startswith('http'):
                            continue
                        
                        # Determine file type
                        file_type = 'pdf'
                        if '.doc' in href.lower():
                            file_type = 'document'
                        elif '.xls' in href.lower():
                            file_type = 'spreadsheet'
                        
                        document = {
                            'url': href,
                            'text': text.strip(),
                            'filename': os.path.basename(urlparse(href).path) or 'document',
                            'type': file_type,
                            'size_estimate': None
                        }
                        
                        # Avoid duplicates
                        if not any(doc['url'] == href for doc in documents):
                            documents.append(document)
                        
            except Exception as e:
                logger.debug(f"Error with document selector {selector}: {e}")
                continue
        
        logger.debug(f"Found {len(documents)} potential documents")
        return documents
    
    def process_selected_contracts(self, max_contracts: int = 10, cost_limit: float = 5.0) -> Dict[str, Any]:
        """
        Process contracts selected for deep extraction
        
        Args:
            max_contracts: Maximum number of contracts to process
            cost_limit: Maximum cost limit for AI processing
            
        Returns:
            Processing results and statistics
        """
        logger.info(f"🚀 Starting multi-layer extraction (max: {max_contracts}, cost limit: ${cost_limit:.2f})")
        
        with self.db.get_session() as session:
            # Get selected contracts from processing queue
            queue_items = session.query(ProcessingQueue).filter(
                ProcessingQueue.task_type == "ai_analysis",
                ProcessingQueue.status == ProcessingStatus.PENDING,
                ProcessingQueue.manually_selected == True
            ).order_by(ProcessingQueue.priority.desc()).limit(max_contracts).all()
            
            if not queue_items:
                logger.warning("📭 No contracts selected for processing")
                return self._get_processing_results()
            
            logger.info(f"📋 Processing {len(queue_items)} selected contracts")
            
            current_cost = 0.0
            
            for queue_item in queue_items:
                if current_cost >= cost_limit:
                    logger.warning(f"💰 Cost limit reached (${current_cost:.2f}/${cost_limit:.2f})")
                    break
                
                try:
                    # Mark as in progress
                    queue_item.status = ProcessingStatus.IN_PROGRESS
                    queue_item.started_at = datetime.utcnow()
                    session.commit()
                    
                    # Process the contract
                    contract_id = int(queue_item.target_id)
                    processing_cost = self._process_single_contract(session, contract_id)
                    current_cost += processing_cost
                    
                    # Mark as completed
                    queue_item.status = ProcessingStatus.COMPLETED
                    queue_item.completed_at = datetime.utcnow()
                    session.commit()
                    
                    logger.info(f"✅ Completed contract {contract_id} (+${processing_cost:.2f})")
                    
                except Exception as e:
                    logger.error(f"❌ Error processing contract {queue_item.target_id}: {e}")
                    
                    # Mark as failed
                    queue_item.status = ProcessingStatus.FAILED
                    queue_item.error_message = str(e)
                    queue_item.completed_at = datetime.utcnow()
                    session.commit()
                    
                    self.stats['errors'].append({
                        'contract_id': queue_item.target_id,
                        'error': str(e)
                    })
                
                # Brief pause between contracts
                time.sleep(1)
        
        results = self._get_processing_results()
        results['total_cost'] = current_cost
        
        logger.info(f"📊 Multi-layer extraction completed: {self.stats}")
        
        return results
    
    def _process_single_contract(self, session, contract_id: int) -> float:
        """
        Process a single contract through all extraction layers
        
        Returns:
            Estimated processing cost
        """
        logger.debug(f"🔍 Processing contract {contract_id}")
        
        # Get contract from database
        contract = session.query(Contract).get(contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")
        
        processing_cost = 0.0
        self.stats['contracts_processed'] += 1
        
        # Layer 1: Already have BidNet data (contract object)
        logger.debug(f"📥 Layer 1: BidNet data available for {contract.title[:50]}")
        
        # Layer 2: Extract detailed city RFP information
        if contract.source_url:
            city_cost = self._extract_city_rfp_details(session, contract)
            processing_cost += city_cost
        
        # Layer 3: Download and process PDF documents
        pdf_cost = self._process_contract_documents(session, contract)
        processing_cost += pdf_cost
        
        # Update contract processing status
        contract.processing_status = ProcessingStatus.COMPLETED
        contract.last_updated = datetime.utcnow()
        session.commit()
        
        return processing_cost
    
    def _extract_city_rfp_details(self, session, contract: Contract) -> float:
        """
        Extract detailed RFP information from city websites
        
        Returns:
            Estimated processing cost
        """
        logger.debug(f"🏛️ Layer 2: Extracting city RFP details for {contract.title[:50]}")
        
        try:
            # Determine city from contract data
            city_name = self._extract_city_name(contract)
            if not city_name:
                logger.debug("Could not determine city name")
                return 0.0
            
            # Check if we have city platform patterns
            city_platform = session.query(CityPlatform).filter_by(city_name=city_name).first()
            
            # If no patterns exist, discover them with AI
            if not city_platform:
                city_website = self._discover_city_website(city_name)
                if city_website:
                    logger.info(f"🤖 Discovering patterns for {city_name}")
                    analysis_result = self.ai_agent.analyze_city_website(city_name, city_website)
                    
                    if analysis_result['success']:
                        city_platform = session.query(CityPlatform).filter_by(city_name=city_name).first()
                        logger.info(f"✅ AI pattern discovery successful for {city_name}")
                        self._extract_with_patterns(session, contract, city_platform)
                        self.stats['city_details_extracted'] += 1
                        return analysis_result.get('cost_estimate', 0.5)  # AI analysis cost
                    else:
                        logger.warning(f"❌ AI pattern discovery failed for {city_name}")
                        return 0.1  # Minimal cost for failed attempt
            else:
                # Use existing patterns for extraction
                logger.debug(f"📋 Using existing patterns for {city_name}")
                self._extract_with_patterns(session, contract, city_platform)
                self.stats['city_details_extracted'] += 1
                return 0.0  # No AI cost for existing patterns
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error extracting city RFP details: {e}")
            return 0.0
    
    def _extract_city_name(self, contract: Contract) -> Optional[str]:
        """Extract city name from contract data"""
        # Try to extract city from location field
        location = contract.location or ''
        agency = contract.agency or ''
        
        # Common city extraction patterns
        text_to_search = f"{location} {agency}".lower()
        
        # List of major California cities in our target region
        cities = [
            'los angeles', 'santa monica', 'beverly hills', 'pasadena', 'glendale',
            'anaheim', 'santa ana', 'irvine', 'huntington beach', 'orange',
            'san diego', 'chula vista', 'oceanside', 'escondido', 'carlsbad',
            'riverside', 'corona', 'temecula', 'murrieta', 'palm springs',
            'fontana', 'rancho cucamonga', 'ontario', 'victorville', 'redlands',
            'ventura', 'oxnard', 'thousand oaks', 'simi valley', 'camarillo'
        ]
        
        for city in cities:
            if city in text_to_search:
                return city.title()
        
        return None
    
    def _discover_city_website(self, city_name: str) -> Optional[str]:
        """Discover the official website for a city"""
        # Common city website patterns
        city_slug = city_name.lower().replace(' ', '')
        potential_urls = [
            f"https://www.{city_slug}.gov",
            f"https://www.{city_slug}.ca.gov", 
            f"https://{city_slug}.gov",
            f"https://www.ci.{city_slug}.ca.us",
            f"https://www.cityof{city_slug}.org"
        ]
        
        for url in potential_urls:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    logger.debug(f"🔍 Found city website: {url}")
                    return url
            except:
                continue
        
        logger.debug(f"❌ Could not find website for {city_name}")
        return None
    
    def _extract_with_patterns(self, session, contract: Contract, city_platform: CityPlatform):
        """Extract detailed contract information using discovered patterns"""
        logger.debug(f"📋 Extracting details using patterns for {city_platform.city_name}")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Navigate to contract source URL
                if contract.source_url:
                    page.goto(contract.source_url, timeout=10000)
                    
                    # Use stored patterns to extract additional details
                    selectors = city_platform.contract_selectors or {}
                    
                    extracted_data = {}
                    
                    # Extract additional fields if selectors exist
                    if 'contact_info' in selectors:
                        contact_elem = page.query_selector(selectors['contact_info'])
                        if contact_elem:
                            extracted_data['contact_info'] = contact_elem.text_content()
                    
                    if 'detailed_description' in selectors:
                        desc_elem = page.query_selector(selectors['detailed_description'])
                        if desc_elem:
                            extracted_data['detailed_description'] = desc_elem.text_content()
                    
                    if 'project_value' in selectors:
                        value_elem = page.query_selector(selectors['project_value'])
                        if value_elem:
                            extracted_data['project_value'] = value_elem.text_content()
                    
                    # Create or update city contract record
                    city_contract = session.query(CityContract).filter_by(contract_id=contract.id).first()
                    
                    if not city_contract:
                        city_contract = CityContract(
                            contract_id=contract.id,
                            city_name=city_platform.city_name,
                            rfp_url=contract.source_url,
                            city_platform=city_platform.platform_type,
                            detail_extraction_status=ProcessingStatus.COMPLETED,
                            last_scraped=datetime.utcnow(),
                            contact_info=extracted_data.get('contact_info', {}),
                            additional_details=extracted_data
                        )
                        session.add(city_contract)
                    else:
                        city_contract.additional_details = extracted_data
                        city_contract.last_scraped = datetime.utcnow()
                        city_contract.detail_extraction_status = ProcessingStatus.COMPLETED
                    
                    session.commit()
                    logger.debug(f"✅ Extracted city details for contract {contract.id}")
                
                browser.close()
                
        except Exception as e:
            logger.error(f"Error extracting with patterns: {e}")
    
    def _process_contract_documents(self, session, contract: Contract) -> float:
        """
        Download and process PDF documents for a contract
        
        Returns:
            Estimated processing cost (minimal for PDF processing)
        """
        logger.debug(f"📄 Layer 3: Processing documents for {contract.title[:50]}")
        
        try:
            # Look for document download links
            pdf_urls = self._find_pdf_links(contract)
            
            if not pdf_urls:
                logger.debug("No PDF links found")
                return 0.0
            
            # Create download directory
            download_dir = Path(f"data/downloads/{contract.external_id}")
            download_dir.mkdir(parents=True, exist_ok=True)
            
            for pdf_url in pdf_urls[:3]:  # Limit to 3 PDFs per contract
                try:
                    # Download PDF
                    filename = self._extract_filename_from_url(pdf_url)
                    file_path = download_dir / filename
                    
                    success = self.pdf_downloader.download_pdf(pdf_url, str(file_path))
                    
                    if success:
                        # Extract text from PDF
                        text_content = self._extract_pdf_text(file_path)
                        file_size_mb = file_path.stat().st_size / (1024 * 1024)
                        
                        # Create download record
                        download_record = PlanDownload(
                            contract_id=contract.id,
                            filename=filename,
                            original_url=pdf_url,
                            file_path=str(file_path),
                            file_size_mb=file_size_mb,
                            download_status=ProcessingStatus.COMPLETED,
                            download_date=datetime.utcnow(),
                            pdf_extracted=bool(text_content),
                            text_content=text_content[:10000] if text_content else None  # Limit text size
                        )
                        session.add(download_record)
                        self.stats['pdfs_downloaded'] += 1
                        
                        logger.debug(f"✅ Downloaded and processed: {filename}")
                    
                except Exception as e:
                    logger.error(f"Error processing PDF {pdf_url}: {e}")
                    continue
            
            session.commit()
            return 0.05  # Minimal cost for PDF processing
            
        except Exception as e:
            logger.error(f"Error processing documents: {e}")
            return 0.0
    
    def _find_pdf_links(self, contract: Contract) -> List[str]:
        """Find PDF download links related to a contract"""
        pdf_links = []
        
        if not contract.source_url:
            return pdf_links
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(contract.source_url, timeout=10000)
                
                # Look for PDF links
                pdf_selectors = [
                    'a[href$=".pdf"]',
                    'a[href*=".pdf"]',
                    '.download-link',
                    '.documents a',
                    '.attachments a'
                ]
                
                for selector in pdf_selectors:
                    elements = page.query_selector_all(selector)
                    for element in elements:
                        href = element.get_attribute('href')
                        if href:
                            # Convert relative URLs to absolute
                            if href.startswith('/'):
                                base_url = f"{urlparse(contract.source_url).scheme}://{urlparse(contract.source_url).netloc}"
                                href = base_url + href
                            elif not href.startswith('http'):
                                href = urljoin(contract.source_url, href)
                            
                            if href.lower().endswith('.pdf') and href not in pdf_links:
                                pdf_links.append(href)
                
                browser.close()
                
        except Exception as e:
            logger.debug(f"Error finding PDF links: {e}")
        
        return pdf_links
    
    def _extract_filename_from_url(self, url: str) -> str:
        """Extract filename from PDF URL"""
        from urllib.parse import urlparse, unquote
        
        parsed = urlparse(unquote(url))
        filename = os.path.basename(parsed.path)
        
        if not filename or not filename.endswith('.pdf'):
            # Generate filename based on URL hash
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            filename = f"document_{url_hash}.pdf"
        
        # Sanitize filename
        filename = "".join(c for c in filename if c.isalnum() or c in "._-")
        
        return filename
    
    def _extract_pdf_text(self, file_path: Path) -> Optional[str]:
        """Extract text content from PDF file"""
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text_parts = []
                
                # Extract text from first few pages (limit for cost control)
                max_pages = min(len(reader.pages), 5)
                
                for page_num in range(max_pages):
                    page = reader.pages[page_num]
                    text_parts.append(page.extract_text())
                
                return '\n'.join(text_parts)
                
        except Exception as e:
            logger.debug(f"Error extracting PDF text from {file_path}: {e}")
            return None
    
    def _get_processing_results(self) -> Dict[str, Any]:
        """Get current processing statistics"""
        return {
            'contracts_processed': self.stats['contracts_processed'],
            'city_details_extracted': self.stats['city_details_extracted'],
            'pdfs_downloaded': self.stats['pdfs_downloaded'],
            'errors': self.stats['errors'],
            'success_rate': (
                self.stats['contracts_processed'] - len(self.stats['errors'])
            ) / max(self.stats['contracts_processed'], 1)
        }
    
    def generate_extraction_report(self, output_dir: str = "data/reports") -> str:
        """Generate comprehensive extraction report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        with self.db.get_session() as session:
            # Get contracts with city details and PDFs
            query = """
            SELECT 
                c.id,
                c.title,
                c.agency,
                c.location,
                c.geographic_region,
                c.processing_status,
                cc.city_name,
                cc.additional_details,
                COUNT(pd.id) as pdf_count,
                SUM(pd.file_size_mb) as total_pdf_size_mb
            FROM contracts c
            LEFT JOIN city_contracts cc ON c.id = cc.contract_id
            LEFT JOIN plan_downloads pd ON c.id = pd.contract_id
            WHERE c.processing_status = 'completed'
            GROUP BY c.id, c.title, c.agency, c.location, c.geographic_region, 
                     c.processing_status, cc.city_name, cc.additional_details
            """
            
            df = pd.read_sql(query, session.bind)
            
            # Save report
            os.makedirs(output_dir, exist_ok=True)
            report_file = os.path.join(output_dir, f"extraction_report_{timestamp}.xlsx")
            df.to_excel(report_file, index=False)
            
            logger.info(f"📊 Generated extraction report: {report_file}")
            
            return report_file

def main():
    """Example usage of the Multi-Layer Extractor"""
    extractor = MultiLayerExtractor()
    
    # Process selected contracts
    results = extractor.process_selected_contracts(max_contracts=5, cost_limit=3.0)
    
    print("\n" + "="*50)
    print("🏗️ MULTI-LAYER EXTRACTION RESULTS")
    print("="*50)
    print(f"📋 Contracts processed: {results['contracts_processed']}")
    print(f"🏛️ City details extracted: {results['city_details_extracted']}")
    print(f"📄 PDFs downloaded: {results['pdfs_downloaded']}")
    print(f"✅ Success rate: {results['success_rate']:.1%}")
    print(f"💰 Total cost: ${results.get('total_cost', 0.0):.2f}")
    
    if results['errors']:
        print(f"⚠️ Errors: {len(results['errors'])}")
        for error in results['errors'][:3]:  # Show first 3 errors
            print(f"  - Contract {error['contract_id']}: {error['error']}")
    
    print("="*50)

if __name__ == "__main__":
    main()