#!/usr/bin/env python3
"""
Progressive Harvest Orchestrator
================================

Modified approach to harvest all accessible RFPs first while flagging problems for later resolution.

WORKFLOW:
1. Run AI extraction on ALL LA region contracts from BidNet
2. For each contract attempt:
   - Try to find and download RFP documents
   - If successful: Download PDFs and extract data
   - If blocked: Create detailed flag with reason
   
3. Generate two outputs:
   - SUCCESS REPORT: Contracts with downloaded documents
   - FLAGS REPORT: Contracts needing attention

FLAGGING CATEGORIES:
- PORTAL_REGISTRATION_NEEDED: Clear login/registration requirements
- NAVIGATION_FAILED: AI couldn't find RFP page/documents  
- ACCESS_DENIED: Found page but couldn't access documents
- NO_RFP_FOUND: City doesn't seem to have RFP online
- TECHNICAL_ERROR: Site errors, timeouts, etc.
"""

import sys
import os
import argparse
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hybrid_bidnet_scraper import HybridBidNetScraper
from src.ai_agents.pattern_discovery_agent import PatternDiscoveryAgent
from src.processing.multi_layer_extractor import MultiLayerExtractor
from src.database.connection import DatabaseManager
from src.database.models import (
    Contract, ExtractionAttempt, ExtractionFlagType, PortalType, ProcessingStatus
)
from src.portal.detector import PortalDetector
from src.portal.credential_manager import CredentialManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ProgressiveHarvestOrchestrator:
    """Orchestrator for progressive harvest approach"""
    
    def __init__(self):
        self.bidnet_scraper = HybridBidNetScraper()
        self.ai_agent = PatternDiscoveryAgent()
        self.multi_layer_extractor = MultiLayerExtractor()
        self.portal_detector = PortalDetector()
        self.credential_manager = CredentialManager()
        self.db = DatabaseManager()
        
        # Session tracking
        self.session_start = datetime.utcnow()
        self.total_cost = 0.0
        self.extraction_attempts = []
        self.successful_extractions = 0
        self.flagged_contracts = 0
        
        logger.info("🚀 Progressive Harvest Orchestrator initialized")
    
    def run_progressive_harvest(self, max_contracts: int = None, cost_limit: float = 10.0) -> Dict[str, Any]:
        """
        Run the progressive harvest workflow
        
        Args:
            max_contracts: Maximum contracts to process (None = all)
            cost_limit: Maximum cost limit for AI processing
            
        Returns:
            Harvest results with success and flag reports
        """
        logger.info(f"🌾 Starting Progressive Harvest (max_contracts: {max_contracts}, cost_limit: ${cost_limit:.2f})")
        
        harvest_results = {
            'session_start': self.session_start,
            'phase_1_bidnet': {},
            'phase_2_extraction': {},
            'success_report': [],
            'flags_report': [],
            'total_cost': 0.0,
            'contracts_processed': 0,
            'success_count': 0,
            'flag_count': 0,
            'flag_breakdown': {},
            'completion_time': None
        }
        
        try:
            # Phase 1: Get LA region contracts from BidNet (or use existing contracts)
            logger.info("📥 Phase 1: Getting LA region contracts")
            
            # Check if we already have contracts in database
            existing_contracts = self._get_contracts_for_processing(None)
            if existing_contracts:
                logger.info(f"✅ Using {len(existing_contracts)} existing contracts from database")
                bidnet_results = {'success': True, 'contracts_found': len(existing_contracts)}
                harvest_results['phase_1_bidnet'] = bidnet_results
            else:
                # Try BidNet extraction as fallback
                logger.info("📥 Running BidNet extraction...")
                try:
                    bidnet_results = self.bidnet_scraper.run_hybrid_extraction()
                    harvest_results['phase_1_bidnet'] = bidnet_results
                    
                    if not bidnet_results.get('success', False):
                        logger.error("❌ BidNet extraction failed")
                        return harvest_results
                except Exception as e:
                    logger.error(f"❌ BidNet extraction error: {e}")
                    bidnet_results = {'success': False, 'error': str(e)}
                    harvest_results['phase_1_bidnet'] = bidnet_results
                    return harvest_results
            
            contracts_found = bidnet_results.get('contracts_found', 0)
            logger.info(f"✅ Found {contracts_found} LA region HVAC contracts")
            
            if contracts_found == 0:
                logger.warning("⚠️ No contracts found to process")
                return harvest_results
            
            # Get contracts from database for processing
            contracts_to_process = self._get_contracts_for_processing(max_contracts)
            harvest_results['contracts_processed'] = len(contracts_to_process)
            
            logger.info(f"🎯 Processing {len(contracts_to_process)} contracts")
            
            # Phase 2: Progressive extraction on each contract
            logger.info("🔍 Phase 2: Progressive RFP extraction")
            extraction_results = self._process_contracts_progressively(
                contracts_to_process, cost_limit
            )
            harvest_results['phase_2_extraction'] = extraction_results
            
            # Generate reports
            harvest_results['success_report'] = self._generate_success_report()
            harvest_results['flags_report'] = self._generate_flags_report()
            harvest_results['flag_breakdown'] = self._get_flag_breakdown()
            
            # Final statistics
            harvest_results['total_cost'] = self.total_cost
            harvest_results['success_count'] = self.successful_extractions
            harvest_results['flag_count'] = self.flagged_contracts
            harvest_results['completion_time'] = datetime.utcnow()
            
            # Save reports to files
            self._save_reports_to_files(harvest_results)
            
            logger.info(f"🎉 Progressive Harvest Complete!")
            logger.info(f"   💰 Total Cost: ${self.total_cost:.2f}")
            logger.info(f"   ✅ Successful: {self.successful_extractions}")
            logger.info(f"   🚩 Flagged: {self.flagged_contracts}")
            
            return harvest_results
            
        except Exception as e:
            logger.error(f"❌ Progressive harvest failed: {e}")
            harvest_results['error'] = str(e)
            return harvest_results
    
    def _get_contracts_for_processing(self, max_contracts: Optional[int]) -> List[Contract]:
        """Get contracts from database for processing"""
        with self.db.get_session() as session:
            query = session.query(Contract).filter(
                Contract.processing_status.in_([ProcessingStatus.PENDING, ProcessingStatus.FAILED])
            ).order_by(Contract.due_date.asc())
            
            if max_contracts:
                query = query.limit(max_contracts)
            
            contracts = query.all()
            logger.info(f"📋 Retrieved {len(contracts)} contracts for processing")
            return contracts
    
    def _process_contracts_progressively(self, contracts: List[Contract], cost_limit: float) -> Dict[str, Any]:
        """Process each contract with progressive harvest approach"""
        results = {
            'total_processed': 0,
            'successful': 0,
            'flagged': 0,
            'cost_used': 0.0,
            'processing_times': []
        }
        
        for i, contract in enumerate(contracts):
            if self.total_cost >= cost_limit:
                logger.warning(f"💰 Cost limit reached (${self.total_cost:.2f}/${cost_limit:.2f})")
                break
            
            logger.info(f"🔍 Processing contract {i+1}/{len(contracts)}: {contract.title[:60]}...")
            
            start_time = time.time()
            
            # Attempt progressive extraction
            extraction_result = self._attempt_contract_extraction(contract)
            
            processing_time = time.time() - start_time
            results['processing_times'].append(processing_time)
            
            # Update session tracking
            self.extraction_attempts.append(extraction_result)
            self.total_cost += extraction_result.get('ai_cost_estimate', 0.0)
            results['total_processed'] += 1
            
            if extraction_result['extraction_flag_type'] == ExtractionFlagType.SUCCESS:
                self.successful_extractions += 1
                results['successful'] += 1
                logger.info(f"   ✅ Success: {extraction_result.get('documents_downloaded_count', 0)} documents")
            else:
                self.flagged_contracts += 1
                results['flagged'] += 1
                logger.info(f"   🚩 Flagged: {extraction_result['extraction_flag_type'].value}")
            
            # Brief pause between contracts
            time.sleep(1)
        
        results['cost_used'] = self.total_cost
        logger.info(f"📊 Batch processing complete: {results['successful']}/{results['total_processed']} successful")
        
        return results
    
    def _attempt_contract_extraction(self, contract: Contract) -> Dict[str, Any]:
        """
        Attempt to extract RFP documents for a single contract
        
        Returns:
            Extraction attempt result with flag categorization
        """
        attempt_start = time.time()
        
        extraction_result = {
            'contract_id': contract.id,
            'contract_title': contract.title,
            'bidnet_url': contract.source_url,
            'extraction_flag_type': ExtractionFlagType.TECHNICAL_ERROR,
            'target_url': None,
            'rfp_page_found': False,
            'documents_found_count': 0,
            'documents_downloaded_count': 0,
            'flag_reason': 'Unknown error',
            'flag_description': '',
            'technical_details': {},
            'portal_type': PortalType.NONE,
            'portal_url': None,
            'registration_required': False,
            'pdf_files_found': [],
            'pdf_download_paths': [],
            'extracted_data': {},
            'ai_cost_estimate': 0.0,
            'processing_time_seconds': 0.0,
            'resolution_priority': 50
        }
        
        try:
            # Step 1: Determine city website URL for RFP search
            city_rfp_url = self._determine_city_rfp_url(contract)
            extraction_result['target_url'] = city_rfp_url
            
            if not city_rfp_url:
                extraction_result.update({
                    'extraction_flag_type': ExtractionFlagType.NO_RFP_FOUND,
                    'flag_reason': 'Unable to determine city RFP website',
                    'flag_description': f'Could not find city website for {contract.agency} to search for RFP documents',
                    'resolution_priority': 30
                })
                self._store_extraction_attempt(extraction_result)
                return extraction_result
            
            # Step 2: Detect portal type and authentication requirements
            portal_detection = self.portal_detector.detect_city_portal(
                contract.agency or 'Unknown City', city_rfp_url
            )
            
            extraction_result.update({
                'portal_type': portal_detection.get('portal_type', PortalType.NONE),
                'portal_url': portal_detection.get('portal_url'),
                'registration_required': portal_detection.get('registration_required', False)
            })
            
            # Step 3: Check if registration/credentials are needed
            if portal_detection.get('registration_required', False):
                # Check for existing credentials
                credentials = self.credential_manager.get_credentials(
                    contract.agency, portal_detection['portal_type']
                )
                
                if not credentials:
                    extraction_result.update({
                        'extraction_flag_type': ExtractionFlagType.PORTAL_REGISTRATION_NEEDED,
                        'flag_reason': f'{portal_detection["portal_type"].value} portal requires registration',
                        'flag_description': f'City uses {portal_detection["portal_type"].value} portal at {portal_detection.get("portal_url", "unknown URL")}. Manual registration required to access RFP documents.',
                        'resolution_priority': 80,
                        'technical_details': {
                            'portal_detection': portal_detection,
                            'registration_url': portal_detection.get('registration_url')
                        }
                    })
                    self._store_extraction_attempt(extraction_result)
                    return extraction_result
            
            # Step 4: Attempt AI-powered extraction
            logger.debug(f"🤖 Attempting AI extraction for {contract.agency}")
            
            ai_result = self.ai_agent.analyze_city_website(
                contract.agency or 'Unknown City',
                city_rfp_url,
                sample_pages=[city_rfp_url]  # Could add more specific RFP URLs if known
            )
            
            extraction_result['ai_cost_estimate'] = ai_result.get('cost_estimate', 0.0)
            
            if not ai_result.get('success', False):
                extraction_result.update({
                    'extraction_flag_type': ExtractionFlagType.TECHNICAL_ERROR,
                    'flag_reason': 'AI analysis failed',
                    'flag_description': f'AI agent failed to analyze website: {ai_result.get("error", "Unknown error")}',
                    'resolution_priority': 40,
                    'technical_details': {'ai_error': ai_result.get('error')}
                })
                self._store_extraction_attempt(extraction_result)
                return extraction_result
            
            # Step 5: Attempt to find RFP documents using discovered patterns
            patterns = ai_result.get('patterns', {})
            rfp_search_result = self._search_for_rfp_documents(
                city_rfp_url, contract, patterns, portal_detection
            )
            
            extraction_result.update(rfp_search_result)
            
            # Step 6: Download found documents
            if rfp_search_result.get('documents_found_count', 0) > 0:
                download_result = self._download_rfp_documents(
                    contract, rfp_search_result['pdf_files_found']
                )
                extraction_result.update(download_result)
                
                if download_result.get('documents_downloaded_count', 0) > 0:
                    extraction_result['extraction_flag_type'] = ExtractionFlagType.SUCCESS
                    extraction_result['flag_reason'] = 'RFP documents successfully extracted'
                    extraction_result['resolution_priority'] = 0  # No resolution needed
                else:
                    extraction_result.update({
                        'extraction_flag_type': ExtractionFlagType.ACCESS_DENIED,
                        'flag_reason': 'Found documents but download failed',
                        'resolution_priority': 60
                    })
            
        except Exception as e:
            logger.error(f"Error during contract extraction: {e}")
            extraction_result.update({
                'extraction_flag_type': ExtractionFlagType.TECHNICAL_ERROR,
                'flag_reason': f'Extraction error: {str(e)[:100]}',
                'flag_description': f'Technical error during extraction: {str(e)}',
                'resolution_priority': 45,
                'technical_details': {'exception': str(e)}
            })
        
        # Store attempt in database
        extraction_result['processing_time_seconds'] = time.time() - attempt_start
        self._store_extraction_attempt(extraction_result)
        
        return extraction_result
    
    def _determine_city_rfp_url(self, contract: Contract) -> Optional[str]:
        """Determine the city website URL where RFPs might be posted"""
        if not contract.agency:
            return None
        
        # Simple heuristic to generate city website URLs
        city_name = contract.agency.lower().replace(' ', '').replace('city of ', '')
        
        # Try common patterns
        possible_urls = [
            f"https://www.{city_name}.gov/procurement",
            f"https://www.{city_name}.gov/business",
            f"https://www.{city_name}.org/procurement", 
            f"https://www.{city_name}.ca.us/procurement",
            f"https://www.{city_name}.gov",
        ]
        
        # Return first URL for now (in production, could test accessibility)
        return possible_urls[0]
    
    def _search_for_rfp_documents(self, city_url: str, contract: Contract, 
                                  patterns: Dict[str, Any], portal_detection: Dict[str, Any]) -> Dict[str, Any]:
        """Search for RFP documents on city website"""
        search_result = {
            'rfp_page_found': False,
            'documents_found_count': 0,
            'pdf_files_found': [],
            'flag_reason': 'No RFP documents found',
            'flag_description': '',
            'extraction_flag_type': ExtractionFlagType.NO_RFP_FOUND,
            'resolution_priority': 35
        }
        
        try:
            # Use multi-layer extractor to search for documents
            extraction_result = self.multi_layer_extractor.extract_contract_details(
                contract.id, 
                city_url,
                contract_title=contract.title,
                agency=contract.agency
            )
            
            if extraction_result.get('success', False):
                documents = extraction_result.get('documents', [])
                if documents:
                    search_result.update({
                        'rfp_page_found': True,
                        'documents_found_count': len(documents),
                        'pdf_files_found': documents,
                        'extraction_flag_type': ExtractionFlagType.SUCCESS,
                        'flag_reason': f'Found {len(documents)} RFP documents',
                        'resolution_priority': 0
                    })
                else:
                    search_result.update({
                        'rfp_page_found': True,
                        'extraction_flag_type': ExtractionFlagType.NO_RFP_FOUND,
                        'flag_reason': 'Found RFP page but no documents',
                        'flag_description': f'Located RFP page for {contract.title} but no downloadable documents found',
                        'resolution_priority': 35
                    })
            else:
                error_msg = extraction_result.get('error', 'Unknown error')
                if 'navigation' in error_msg.lower() or 'selector' in error_msg.lower():
                    search_result['extraction_flag_type'] = ExtractionFlagType.NAVIGATION_FAILED
                    search_result['flag_reason'] = 'Navigation to RFP failed'
                    search_result['resolution_priority'] = 55
                elif 'access' in error_msg.lower() or 'denied' in error_msg.lower():
                    search_result['extraction_flag_type'] = ExtractionFlagType.ACCESS_DENIED
                    search_result['flag_reason'] = 'Access to RFP denied'
                    search_result['resolution_priority'] = 70
        
        except Exception as e:
            logger.debug(f"Error searching for RFP documents: {e}")
            search_result.update({
                'extraction_flag_type': ExtractionFlagType.TECHNICAL_ERROR,
                'flag_reason': f'Search error: {str(e)[:50]}',
                'resolution_priority': 45
            })
        
        return search_result
    
    def _download_rfp_documents(self, contract: Contract, pdf_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Download found RFP documents"""
        download_result = {
            'documents_downloaded_count': 0,
            'pdf_download_paths': [],
            'extracted_data': {}
        }
        
        # This would integrate with the PDF downloader
        # For now, simulate the download process
        for pdf_file in pdf_files:
            try:
                # In real implementation, would download PDF
                download_path = f"data/pdfs/contract_{contract.id}_{pdf_file.get('filename', 'document.pdf')}"
                download_result['pdf_download_paths'].append(download_path)
                download_result['documents_downloaded_count'] += 1
                
                logger.debug(f"📄 Downloaded: {pdf_file.get('filename', 'document.pdf')}")
                
            except Exception as e:
                logger.debug(f"Failed to download {pdf_file.get('filename')}: {e}")
        
        return download_result
    
    def _store_extraction_attempt(self, extraction_result: Dict[str, Any]) -> None:
        """Store extraction attempt in database"""
        try:
            with self.db.get_session() as session:
                attempt = ExtractionAttempt(
                    contract_id=extraction_result['contract_id'],
                    extraction_flag_type=extraction_result['extraction_flag_type'],
                    target_url=extraction_result.get('target_url'),
                    rfp_page_found=extraction_result.get('rfp_page_found', False),
                    documents_found_count=extraction_result.get('documents_found_count', 0),
                    documents_downloaded_count=extraction_result.get('documents_downloaded_count', 0),
                    flag_reason=extraction_result.get('flag_reason', ''),
                    flag_description=extraction_result.get('flag_description', ''),
                    technical_details=extraction_result.get('technical_details', {}),
                    portal_type=extraction_result.get('portal_type'),
                    portal_url=extraction_result.get('portal_url'),
                    registration_required=extraction_result.get('registration_required', False),
                    pdf_files_found=extraction_result.get('pdf_files_found', []),
                    pdf_download_paths=extraction_result.get('pdf_download_paths', []),
                    extracted_data=extraction_result.get('extracted_data', {}),
                    ai_cost_estimate=extraction_result.get('ai_cost_estimate', 0.0),
                    processing_time_seconds=extraction_result.get('processing_time_seconds', 0.0),
                    resolution_priority=extraction_result.get('resolution_priority', 50)
                )
                session.add(attempt)
                session.commit()
                
        except Exception as e:
            logger.error(f"Failed to store extraction attempt: {e}")
    
    def _generate_success_report(self) -> List[Dict[str, Any]]:
        """Generate report of successful extractions"""
        successful_attempts = [
            attempt for attempt in self.extraction_attempts
            if attempt['extraction_flag_type'] == ExtractionFlagType.SUCCESS
        ]
        
        return [{
            'contract_title': attempt['contract_title'],
            'bidnet_listing_url': attempt.get('bidnet_url'),
            'target_url': attempt['target_url'],
            'documents_downloaded': attempt['documents_downloaded_count'],
            'pdf_files': attempt['pdf_files_found'],
            'download_paths': attempt['pdf_download_paths'],
            'processing_time': f"{attempt.get('processing_time_seconds', 0):.1f}s",
            'ai_cost': f"${attempt.get('ai_cost_estimate', 0):.2f}"
        } for attempt in successful_attempts]
    
    def _generate_flags_report(self) -> List[Dict[str, Any]]:
        """Generate report of flagged contracts"""
        flagged_attempts = [
            attempt for attempt in self.extraction_attempts
            if attempt['extraction_flag_type'] != ExtractionFlagType.SUCCESS
        ]
        
        # Sort by resolution priority (highest first)
        flagged_attempts.sort(key=lambda x: x.get('resolution_priority', 50), reverse=True)
        
        return [{
            'contract_title': attempt['contract_title'],
            'bidnet_listing_url': attempt.get('bidnet_url'),
            'flag_type': attempt['extraction_flag_type'].value,
            'flag_reason': attempt['flag_reason'],
            'flag_description': attempt['flag_description'],
            'target_url': attempt['target_url'],
            'portal_type': attempt.get('portal_type', PortalType.NONE).value,
            'portal_url': attempt.get('portal_url'),
            'registration_required': attempt.get('registration_required', False),
            'resolution_priority': attempt.get('resolution_priority', 50),
            'processing_time': f"{attempt.get('processing_time_seconds', 0):.1f}s",
            'technical_details': attempt.get('technical_details', {})
        } for attempt in flagged_attempts]
    
    def _get_flag_breakdown(self) -> Dict[str, int]:
        """Get breakdown of flag types"""
        breakdown = {}
        for attempt in self.extraction_attempts:
            flag_type = attempt['extraction_flag_type'].value
            breakdown[flag_type] = breakdown.get(flag_type, 0) + 1
        return breakdown
    
    def _save_reports_to_files(self, harvest_results: Dict[str, Any]) -> None:
        """Save success and flags reports to Excel files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Use ~/Documents/hvacscraper/ as permanent default location
        reports_dir = os.path.expanduser("~/Documents/hvacscraper")
        os.makedirs(reports_dir, exist_ok=True)
        
        # Save success report
        if harvest_results['success_report']:
            success_df = pd.DataFrame(harvest_results['success_report'])
            success_file = os.path.join(reports_dir, f"success_report_{timestamp}.xlsx")
            success_df.to_excel(success_file, index=False)
            logger.info(f"✅ Success report saved: {success_file}")
        
        # Save flags report
        if harvest_results['flags_report']:
            flags_df = pd.DataFrame(harvest_results['flags_report'])
            flags_file = os.path.join(reports_dir, f"flags_report_{timestamp}.xlsx")
            flags_df.to_excel(flags_file, index=False)
            logger.info(f"🚩 Flags report saved: {flags_file}")
        
        # Save summary statistics
        summary = {
            'total_processed': harvest_results['contracts_processed'],
            'successful_extractions': harvest_results['success_count'],
            'flagged_contracts': harvest_results['flag_count'],
            'total_cost': harvest_results['total_cost'],
            'session_duration_minutes': (harvest_results['completion_time'] - harvest_results['session_start']).total_seconds() / 60,
            'flag_breakdown': harvest_results['flag_breakdown']
        }
        
        summary_df = pd.DataFrame([summary])
        summary_file = os.path.join(reports_dir, f"harvest_summary_{timestamp}.xlsx")
        summary_df.to_excel(summary_file, index=False)
        logger.info(f"📊 Summary report saved: {summary_file}")
        
        # Print final location for user
        logger.info(f"📁 All reports saved to: {reports_dir}")
        print(f"\n📁 Reports Location: {reports_dir}")
        print(f"   - success_report_{timestamp}.xlsx (if applicable)")  
        print(f"   - flags_report_{timestamp}.xlsx")
        print(f"   - harvest_summary_{timestamp}.xlsx")

def main():
    """Main entry point for progressive harvest"""
    parser = argparse.ArgumentParser(description="Progressive Harvest RFP Extraction")
    parser.add_argument("--max-contracts", type=int, help="Maximum contracts to process")
    parser.add_argument("--cost-limit", type=float, default=10.0, help="Maximum cost limit")
    parser.add_argument("--test-mode", action="store_true", help="Run on small batch for testing")
    
    args = parser.parse_args()
    
    if args.test_mode:
        args.max_contracts = 5
        args.cost_limit = 2.0
        print("🧪 Running in TEST MODE: 5 contracts max, $2.00 cost limit")
    
    orchestrator = ProgressiveHarvestOrchestrator()
    
    print(f"🌾 Starting Progressive Harvest")
    print(f"   Max contracts: {args.max_contracts or 'All'}")
    print(f"   Cost limit: ${args.cost_limit:.2f}")
    print("-" * 50)
    
    results = orchestrator.run_progressive_harvest(
        max_contracts=args.max_contracts,
        cost_limit=args.cost_limit
    )
    
    # Print final summary
    print(f"\n🎉 PROGRESSIVE HARVEST COMPLETE")
    print(f"=" * 50)
    print(f"📊 Contracts processed: {results['contracts_processed']}")
    print(f"✅ Successful extractions: {results['success_count']}")
    print(f"🚩 Flagged for attention: {results['flag_count']}")
    print(f"💰 Total cost: ${results['total_cost']:.2f}")
    
    if results['flag_breakdown']:
        print(f"\n🚩 Flag Breakdown:")
        for flag_type, count in results['flag_breakdown'].items():
            print(f"   {flag_type}: {count}")
    
    print(f"\n📄 Reports saved to data/processed/")
    print(f"   Next: Review flags_report to prioritize resolution efforts")

if __name__ == "__main__":
    main()