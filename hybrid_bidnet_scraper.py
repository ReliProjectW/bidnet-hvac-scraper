#!/usr/bin/env python3
"""
Hybrid BidNet Scraper - Phase 2 Implementation
==============================================

This extends the working bidnet_hvac_scraper_complete.py with:
1. Geographic filtering for LA region + south to Mexico border
2. SQLite database persistence with contract tracking  
3. Integration layer for future AI pattern discovery
4. Manual selection interface preparation

This preserves the 100% working BidNet scraper while adding Phase 2 capabilities.
"""

import logging
import sys
import os
from datetime import datetime
from typing import List, Dict, Any, Tuple

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from src.auth.bidnet_auth import BidNetAuthenticator
from src.scraper.bidnet_search import BidNetSearcher
from src.geographic.filter import GeographicFilter
from src.database.connection import DatabaseManager
from src.database.models import Contract, ProcessingStatus, SourceType, GeographicRegion
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import pandas as pd

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HybridBidNetScraper:
    """
    Hybrid scraper that combines the working BidNet extraction 
    with geographic filtering and database persistence
    """
    
    def __init__(self):
        self.config = Config()
        self.authenticator = BidNetAuthenticator()
        self.searcher = BidNetSearcher()
        self.geo_filter = GeographicFilter()
        self.db = DatabaseManager()
        
        logger.info("🤖 Initialized Hybrid BidNet Scraper")
    
    def run_hybrid_extraction(self) -> Dict[str, Any]:
        """
        Run the complete hybrid extraction pipeline:
        1. Use existing BidNet scraper to get all contracts
        2. Apply geographic filtering for LA region
        3. Store results in database with proper tracking
        4. Prepare for manual selection interface
        """
        logger.info("🚀 Starting Hybrid BidNet Extraction Pipeline")
        
        results = {
            'total_found': 0,
            'in_region': 0,
            'out_of_region': 0,
            'saved_to_db': 0,
            'errors': []
        }
        
        try:
            # Step 1: Run the proven BidNet extraction
            logger.info("📥 Step 1: Running BidNet extraction...")
            raw_contracts = self._extract_bidnet_contracts()
            results['total_found'] = len(raw_contracts)
            logger.info(f"✅ Extracted {len(raw_contracts)} contracts from BidNet")
            
            # Step 2: Apply geographic filtering
            logger.info("🗺️ Step 2: Applying geographic filtering...")
            in_region_contracts, out_region_contracts = self.geo_filter.filter_contracts_by_geography(raw_contracts)
            results['in_region'] = len(in_region_contracts)
            results['out_of_region'] = len(out_region_contracts)
            
            logger.info(f"✅ Geographic filtering: {results['in_region']} in LA region, {results['out_of_region']} out of region")
            
            # Step 3: Save to database for tracking and manual selection
            logger.info("💾 Step 3: Saving contracts to database...")
            saved_count = self._save_contracts_to_database(in_region_contracts)
            results['saved_to_db'] = saved_count
            
            logger.info(f"✅ Saved {saved_count} contracts to database")
            
            # Step 4: Generate summary reports
            logger.info("📊 Step 4: Generating reports...")
            self._generate_hybrid_reports(in_region_contracts, out_region_contracts)
            
            logger.info("🎉 Hybrid extraction pipeline completed successfully!")
            return results
            
        except Exception as e:
            logger.error(f"❌ Error in hybrid extraction pipeline: {e}")
            results['errors'].append(str(e))
            raise
    
    def _extract_bidnet_contracts(self) -> List[Dict[str, Any]]:
        """Extract contracts using the proven BidNet scraper logic"""
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            
            try:
                # Step 1: Authenticate (using working auth logic)
                logger.info("🔐 Authenticating with BidNet...")
                login_success = self.authenticator.login(page)
                if not login_success:
                    raise Exception("Authentication failed")
                logger.info("✅ Authentication successful")
                
                # Step 2: Search for HVAC contracts (using working search logic)
                logger.info("🔍 Searching for HVAC contracts...")
                search_success = self.searcher.search_hvac_contracts(page)
                if not search_success:
                    raise Exception("HVAC search failed")
                logger.info("✅ HVAC search successful")
                
                # Step 3: Extract all results with pagination
                logger.info("📋 Extracting all contract results...")
                contracts = self._extract_all_results_with_pagination(page)
                logger.info(f"✅ Extracted {len(contracts)} total contracts")
                
                return contracts
                
            finally:
                context.close()
                browser.close()
    
    def _extract_all_results_with_pagination(self, page) -> List[Dict[str, Any]]:
        """Extract all contract results with pagination (proven working logic)"""
        all_contracts = []
        page_num = 1
        
        while True:
            logger.info(f"📄 Processing page {page_num}...")
            
            # Wait for results to load
            page.wait_for_selector('.search-results-list', timeout=10000)
            
            # Extract contracts from current page
            page_contracts = self._extract_contracts_from_page(page, page_num)
            
            if not page_contracts:
                logger.info(f"No contracts found on page {page_num}, stopping pagination")
                break
            
            all_contracts.extend(page_contracts)
            logger.info(f"✅ Page {page_num}: Extracted {len(page_contracts)} contracts (running total: {len(all_contracts)})")
            
            # Check for next page
            if not self._navigate_to_next_page(page):
                logger.info("No more pages available, pagination complete")
                break
            
            page_num += 1
        
        # Remove duplicates based on title and agency
        logger.info("🔄 Removing duplicates...")
        unique_contracts = self._remove_duplicates(all_contracts)
        logger.info(f"✅ After deduplication: {len(unique_contracts)} unique contracts")
        
        return unique_contracts
    
    def _extract_contracts_from_page(self, page, page_num: int) -> List[Dict[str, Any]]:
        """Extract contract information from a single page"""
        try:
            html_content = page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all contract rows
            contract_rows = soup.find_all('tr', {'data-bid-id': True})
            contracts = []
            
            for row in contract_rows:
                try:
                    contract = self._parse_contract_row(row)
                    if contract and self._is_valid_contract(contract):
                        contracts.append(contract)
                except Exception as e:
                    logger.debug(f"Error parsing contract row: {e}")
                    continue
            
            return contracts
            
        except Exception as e:
            logger.error(f"Error extracting contracts from page {page_num}: {e}")
            return []
    
    def _parse_contract_row(self, row) -> Dict[str, Any]:
        """Parse individual contract row into structured data"""
        try:
            # Extract basic information
            title_elem = row.find('td', class_='title')
            agency_elem = row.find('td', class_='agency')
            location_elem = row.find('td', class_='location')
            due_date_elem = row.find('td', class_='due-date')
            
            contract = {
                'external_id': row.get('data-bid-id', ''),
                'title': title_elem.get_text(strip=True) if title_elem else '',
                'agency': agency_elem.get_text(strip=True) if agency_elem else '',
                'location': location_elem.get_text(strip=True) if location_elem else '',
                'due_date': due_date_elem.get_text(strip=True) if due_date_elem else '',
                'source_type': SourceType.BIDNET.value,
                'source_url': f"https://bidnetdirect.com/bid/{row.get('data-bid-id', '')}",
                'discovered_at': datetime.utcnow().isoformat(),
                'raw_data': {'html_row': str(row)}
            }
            
            return contract
            
        except Exception as e:
            logger.debug(f"Error parsing contract row: {e}")
            return {}
    
    def _is_valid_contract(self, contract: Dict[str, Any]) -> bool:
        """Validate contract data quality"""
        if not contract.get('title') or not contract.get('agency'):
            return False
        
        # Filter out "No results found" or similar messages
        title_lower = contract['title'].lower()
        if any(phrase in title_lower for phrase in ['no results', 'no records', 'not found']):
            return False
        
        return True
    
    def _navigate_to_next_page(self, page) -> bool:
        """Navigate to next page if available"""
        try:
            # Look for next page button
            next_button = page.query_selector('a.next-page, .pagination a.next')
            if next_button and not next_button.get_attribute('disabled'):
                next_button.click()
                page.wait_for_load_state('networkidle')
                return True
            return False
        except:
            return False
    
    def _remove_duplicates(self, contracts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate contracts based on title and agency"""
        seen = set()
        unique_contracts = []
        
        for contract in contracts:
            # Create unique key based on title and agency
            key = f"{contract.get('title', '').strip()}|{contract.get('agency', '').strip()}"
            
            if key not in seen:
                seen.add(key)
                unique_contracts.append(contract)
        
        return unique_contracts
    
    def _save_contracts_to_database(self, contracts: List[Dict[str, Any]]) -> int:
        """Save filtered contracts to database with proper tracking"""
        saved_count = 0
        
        with self.db.get_session() as session:
            for contract_data in contracts:
                try:
                    # Check if contract already exists
                    existing = session.query(Contract).filter_by(
                        external_id=contract_data['external_id']
                    ).first()
                    
                    if existing:
                        # Update existing contract
                        existing.last_updated = datetime.utcnow()
                        existing.geographic_region = GeographicRegion(contract_data.get('geographic_region', 'out_of_region'))
                        logger.debug(f"Updated existing contract: {contract_data['title'][:50]}")
                    else:
                        # Create new contract
                        contract = Contract(
                            external_id=contract_data['external_id'],
                            source_type=SourceType.BIDNET,
                            source_url=contract_data.get('source_url'),
                            title=contract_data['title'],
                            agency=contract_data.get('agency'),
                            location=contract_data.get('location'),
                            geographic_region=GeographicRegion(contract_data.get('geographic_region', 'out_of_region')),
                            processing_status=ProcessingStatus.PENDING,
                            discovered_at=datetime.utcnow(),
                            raw_data=contract_data.get('raw_data', {})
                        )
                        session.add(contract)
                        logger.debug(f"Added new contract: {contract_data['title'][:50]}")
                    
                    saved_count += 1
                    
                except Exception as e:
                    logger.error(f"Error saving contract {contract_data.get('title', 'Unknown')}: {e}")
                    continue
            
            session.commit()
        
        return saved_count
    
    def _generate_hybrid_reports(self, in_region_contracts: List[Dict[str, Any]], out_region_contracts: List[Dict[str, Any]]):
        """Generate Excel/CSV reports with geographic classification"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create output directory in Documents/hvacscraper
        output_dir = "/Users/christophernguyen/Documents/hvacscraper"
        os.makedirs(output_dir, exist_ok=True)
        
        # Save in-region contracts (priority for AI processing)
        if in_region_contracts:
            in_region_df = pd.DataFrame(in_region_contracts)
            in_region_file = os.path.join(output_dir, f"hybrid_bidnet_la_region_{timestamp}.xlsx")
            in_region_df.to_excel(in_region_file, index=False)
            logger.info(f"💾 Saved LA region contracts: {in_region_file}")
        
        # Save all contracts (for reference)
        all_contracts = in_region_contracts + out_region_contracts
        if all_contracts:
            all_df = pd.DataFrame(all_contracts)
            all_file = os.path.join(output_dir, f"hybrid_bidnet_all_contracts_{timestamp}.xlsx")
            all_df.to_excel(all_file, index=False)
            logger.info(f"💾 Saved all contracts: {all_file}")

def main():
    """Run the hybrid BidNet scraper"""
    try:
        scraper = HybridBidNetScraper()
        results = scraper.run_hybrid_extraction()
        
        print("\n" + "="*60)
        print("🎉 HYBRID BIDNET EXTRACTION RESULTS")
        print("="*60)
        print(f"📊 Total contracts found: {results['total_found']}")
        print(f"🗺️ In LA region: {results['in_region']}")
        print(f"❌ Out of region: {results['out_of_region']}")  
        print(f"💾 Saved to database: {results['saved_to_db']}")
        print("="*60)
        
        if results['errors']:
            print("⚠️ Errors encountered:")
            for error in results['errors']:
                print(f"  - {error}")
        
        print("✅ Ready for Phase 2B: AI Pattern Discovery!")
        print("✅ Ready for Phase 2C: Manual Selection Interface!")
        
    except Exception as e:
        logger.error(f"❌ Hybrid extraction failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()