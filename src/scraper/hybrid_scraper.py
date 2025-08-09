import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import time

from ..database.models import (
    Contract, CityContract, CityPlatform, ProcessingStatus, 
    SourceType, GeographicRegion
)
from ..database.connection import db_manager
from ..geographic.filter import GeographicFilter
from ..ai_agents.browser_agent import BrowserUseAgent
from ..processing.queue_manager import QueueManager
from .bidnet_search import BidNetSearcher

class HybridScraper:
    """
    Hybrid AI + Traditional scraper that combines:
    1. AI discovery of site patterns (Phase 1)
    2. Fast traditional scraping (Phase 2) 
    3. AI re-analysis when sites change (Phase 3)
    """
    
    def __init__(self, ai_api_key: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self.geo_filter = GeographicFilter()
        self.ai_agent = BrowserUseAgent(ai_api_key)
        self.queue_manager = QueueManager()
        self.bidnet_searcher = BidNetSearcher()
        
        # Cost tracking
        self.total_ai_cost = 0.0
        self.contracts_processed = 0
        
    def discover_bidnet_patterns(self, credentials: Dict[str, str]) -> Dict[str, Any]:
        """
        Phase 1: Use AI to discover BidNet patterns
        
        Args:
            credentials: BidNet login credentials
            
        Returns:
            Discovered patterns and selectors
        """
        self.logger.info("🎯 Phase 1: AI discovery of BidNet patterns")
        
        try:
            patterns = self.ai_agent.analyze_bidnet_structure(credentials)
            
            # Store patterns in database for future use
            self._save_bidnet_patterns(patterns)
            
            cost = patterns.get('analysis_cost', 10.0)
            self.total_ai_cost += cost
            self.logger.info(f"💰 AI analysis cost: ${cost:.2f}")
            
            return patterns
            
        except Exception as e:
            self.logger.error(f"❌ BidNet pattern discovery failed: {e}")
            raise
    
    def search_contracts_traditional(self, use_ai_patterns: bool = True) -> List[Dict[str, Any]]:
        """
        Phase 2: Fast traditional scraping using AI-discovered patterns
        
        Args:
            use_ai_patterns: Whether to use AI-discovered patterns
            
        Returns:
            List of contracts found
        """
        self.logger.info("⚡ Phase 2: Traditional scraping with AI patterns")
        
        try:
            if use_ai_patterns:
                patterns = self._load_bidnet_patterns()
                if patterns:
                    # Use AI-discovered patterns for more efficient scraping
                    contracts = self._scrape_with_patterns(patterns)
                else:
                    self.logger.warning("No AI patterns found, falling back to default scraping")
                    contracts = self.bidnet_searcher.search_contracts()
            else:
                contracts = self.bidnet_searcher.search_contracts()
            
            # Apply geographic filtering to conserve credits
            in_region_contracts, out_of_region = self.geo_filter.filter_contracts_by_geography(contracts)
            
            self.logger.info(f"Geographic filtering: {len(in_region_contracts)} in-region, "
                           f"{len(out_of_region)} out-of-region")
            
            # Save contracts to database
            saved_contracts = self._save_contracts_to_db(in_region_contracts)
            
            self.logger.info(f"✅ Found and saved {len(saved_contracts)} contracts")
            return saved_contracts
            
        except Exception as e:
            self.logger.error(f"❌ Traditional scraping failed: {e}")
            
            # Phase 3: Auto-healing - trigger AI re-analysis
            self._trigger_auto_healing("bidnet", str(e))
            raise
    
    def process_city_contracts(self, contract_ids: List[int], 
                             selected_by: str = "system") -> int:
        """
        Process city-specific contract details
        
        Args:
            contract_ids: List of contract IDs to process
            selected_by: Who selected these contracts
            
        Returns:
            Number of contracts queued for processing
        """
        self.logger.info(f"🏙️ Processing {len(contract_ids)} city contracts")
        
        # Queue contracts for AI analysis
        queued_count = self.queue_manager.queue_selected_contracts_for_ai(
            contract_ids, selected_by
        )
        
        return queued_count
    
    def process_ai_queue_batch(self, batch_size: int = 3) -> Dict[str, Any]:
        """
        Process a batch of AI analysis tasks
        
        Args:
            batch_size: Number of contracts to process in this batch
            
        Returns:
            Processing results summary
        """
        self.logger.info(f"🤖 Processing AI queue batch (size: {batch_size})")
        
        # Get pending AI analysis tasks
        pending_tasks = self.queue_manager.get_pending_tasks("ai_analysis", batch_size)
        
        results = {
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "total_cost": 0.0,
            "contracts": []
        }
        
        for task in pending_tasks:
            self.queue_manager.mark_task_started(task.id)
            
            try:
                # Process the contract
                contract_id = task.config_data.get("contract_id")
                contract_result = self._process_single_contract_ai(contract_id)
                
                if contract_result["success"]:
                    self.queue_manager.mark_task_completed(task.id)
                    results["successful"] += 1
                    results["contracts"].append(contract_result)
                else:
                    self.queue_manager.mark_task_failed(task.id, contract_result["error"])
                    results["failed"] += 1
                
                results["total_cost"] += contract_result.get("cost", 0.0)
                results["processed"] += 1
                
            except Exception as e:
                self.queue_manager.mark_task_failed(task.id, str(e))
                results["failed"] += 1
                results["processed"] += 1
                self.logger.error(f"Failed to process task {task.id}: {e}")
        
        self.total_ai_cost += results["total_cost"]
        self.logger.info(f"💰 Batch processing cost: ${results['total_cost']:.2f}")
        self.logger.info(f"✅ Batch results: {results['successful']} successful, {results['failed']} failed")
        
        return results
    
    def get_manual_selection_candidates(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get contracts that are good candidates for manual AI processing"""
        return self.queue_manager.get_manual_selection_candidates(limit)
    
    def _save_bidnet_patterns(self, patterns: Dict[str, Any]):
        """Save BidNet patterns to database"""
        with db_manager.get_session() as session:
            # Store as a special city platform entry for BidNet
            bidnet_platform = session.query(CityPlatform).filter(
                CityPlatform.city_name == "BidNet_Main"
            ).first()
            
            if not bidnet_platform:
                bidnet_platform = CityPlatform(
                    city_name="BidNet_Main",
                    platform_type="bidnet",
                    base_url="https://bidnetdirect.com"
                )
                session.add(bidnet_platform)
            
            bidnet_platform.search_selectors = patterns.get("search", {})
            bidnet_platform.contract_selectors = patterns.get("contract_listing", {})
            bidnet_platform.last_ai_analysis = datetime.utcnow()
            
            session.commit()
    
    def _load_bidnet_patterns(self) -> Optional[Dict[str, Any]]:
        """Load BidNet patterns from database"""
        with db_manager.get_session() as session:
            bidnet_platform = session.query(CityPlatform).filter(
                CityPlatform.city_name == "BidNet_Main"
            ).first()
            
            if bidnet_platform:
                return {
                    "search": bidnet_platform.search_selectors,
                    "contract_listing": bidnet_platform.contract_selectors,
                    "last_updated": bidnet_platform.last_ai_analysis
                }
            
            return None
    
    def _scrape_with_patterns(self, patterns: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Use AI-discovered patterns for scraping"""
        # This would enhance the existing BidNetSearcher with AI patterns
        # For now, delegate to existing scraper but could be optimized
        return self.bidnet_searcher.search_contracts()
    
    def _save_contracts_to_db(self, contracts: List[Dict[str, Any]]) -> List[Contract]:
        """Save contracts to database"""
        saved_contracts = []
        
        with db_manager.get_session() as session:
            for contract_data in contracts:
                # Check if contract already exists
                existing = session.query(Contract).filter(
                    Contract.external_id == contract_data.get('id')
                ).first()
                
                if existing:
                    continue
                
                # Determine geographic region
                location = contract_data.get('location', '')
                is_in_region, region = self.geo_filter.is_in_target_region(location)
                
                contract = Contract(
                    external_id=contract_data.get('id'),
                    source_type=SourceType.BIDNET,
                    source_url=contract_data.get('url'),
                    title=contract_data.get('title', 'No title'),
                    agency=contract_data.get('agency', 'Unknown'),
                    location=location,
                    geographic_region=region,
                    estimated_value=contract_data.get('estimated_value'),
                    hvac_relevance_score=contract_data.get('hvac_relevance_score', 0),
                    matching_keywords=contract_data.get('matching_keywords', []),
                    processing_status=ProcessingStatus.PENDING,
                    raw_data=contract_data
                )
                
                # Add in_target_region flag for easy filtering  
                if contract.raw_data is None:
                    contract.raw_data = {}
                contract.raw_data['in_target_region'] = is_in_region
                
                session.add(contract)
                saved_contracts.append(contract)
            
            session.commit()
        
        return saved_contracts
    
    def _process_single_contract_ai(self, contract_id: int) -> Dict[str, Any]:
        """Process a single contract with AI"""
        try:
            with db_manager.get_session() as session:
                contract = session.query(Contract).filter(Contract.id == contract_id).first()
                if not contract:
                    return {"success": False, "error": "Contract not found"}
                
                # Extract RFP URL from contract data
                rfp_url = contract.raw_data.get('url') if contract.raw_data else None
                if not rfp_url:
                    return {"success": False, "error": "No RFP URL found"}
                
                # Determine city name from agency
                city_name = self._extract_city_name(contract.agency or contract.location)
                
                # Check if we have patterns for this city platform
                city_platform = session.query(CityPlatform).filter(
                    CityPlatform.city_name == city_name
                ).first()
                
                if not city_platform:
                    # Use AI to analyze this city's platform
                    self.logger.info(f"🤖 Analyzing new city platform: {city_name}")
                    patterns = self.ai_agent.analyze_city_platform(
                        city_name, rfp_url, registration_required=False
                    )
                    
                    # Save the discovered patterns
                    city_platform = CityPlatform(
                        city_name=city_name,
                        platform_type=patterns.get("platform_type", "unknown"),
                        base_url=patterns.get("base_url", rfp_url),
                        search_selectors=patterns.get("search", {}),
                        contract_selectors=patterns.get("contract_listing", {}),
                        last_ai_analysis=datetime.utcnow(),
                        total_scrapes=1,
                        successful_scrapes=1
                    )
                    session.add(city_platform)
                
                # Create city contract entry
                city_contract = CityContract(
                    contract_id=contract.id,
                    city_name=city_name,
                    rfp_url=rfp_url,
                    city_platform=city_platform.platform_type,
                    detail_extraction_status=ProcessingStatus.COMPLETED,
                    last_scraped=datetime.utcnow()
                )
                session.add(city_contract)
                
                # Update contract status
                contract.processing_status = ProcessingStatus.COMPLETED
                
                session.commit()
                
                return {
                    "success": True,
                    "contract_id": contract_id,
                    "city_name": city_name,
                    "rfp_url": rfp_url,
                    "cost": 3.0  # Estimated cost for city analysis
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _extract_city_name(self, text: str) -> str:
        """Extract city name from agency or location text"""
        if not text:
            return "Unknown"
        
        # Common patterns for city names
        import re
        
        patterns = [
            r'(?i)city of ([^,\n]+)',
            r'(?i)([^,\n]+) city',
            r'(?i)([^,\n]+),\s*ca',
            r'(?i)([^,\n]+),\s*california'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                city_name = match.group(1).strip()
                if len(city_name) > 2:  # Avoid single letters
                    return city_name.title()
        
        # Fallback: take first meaningful word
        words = text.split()
        for word in words:
            if len(word) > 3 and word.lower() not in ['the', 'and', 'county', 'district']:
                return word.title()
        
        return "Unknown"
    
    def _trigger_auto_healing(self, target_type: str, error_details: str):
        """Phase 3: Trigger AI re-analysis when scraping fails"""
        self.logger.info(f"🔄 Triggering auto-healing for {target_type}")
        
        try:
            # Queue for AI re-analysis
            self.queue_manager.add_to_queue(
                task_type="ai_reanalysis",
                target_id=f"{target_type}_failure",
                config_data={
                    "target_type": target_type,
                    "error_details": error_details,
                    "timestamp": datetime.utcnow().isoformat()
                },
                priority=5  # Medium priority
            )
            
            self.logger.info("✅ Auto-healing queued")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to trigger auto-healing: {e}")
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary for tracking"""
        return {
            "total_ai_cost": self.total_ai_cost,
            "contracts_processed": self.contracts_processed,
            "cost_per_contract": self.total_ai_cost / max(self.contracts_processed, 1),
            "estimated_monthly_cost": self.total_ai_cost * 30 if self.contracts_processed > 0 else 0
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        queue_status = self.queue_manager.get_queue_status()
        cost_summary = self.get_cost_summary()
        
        with db_manager.get_session() as session:
            # Contract counts by status
            contract_counts = {}
            for status in ProcessingStatus:
                count = session.query(Contract).filter(
                    Contract.processing_status == status
                ).count()
                contract_counts[status.value] = count
            
            # City platform counts
            platform_count = session.query(CityPlatform).count()
            
        return {
            "queue_status": queue_status,
            "cost_summary": cost_summary,
            "contract_counts": contract_counts,
            "city_platforms_discovered": platform_count,
            "last_updated": datetime.utcnow().isoformat()
        }