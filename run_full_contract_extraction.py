#!/usr/bin/env python3
"""
Run full contract detail extraction on all non-federal contracts
"""

import logging
from contract_detail_scraper import load_existing_contracts, is_federal_bid, scrape_contract_details, save_detailed_contracts

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Run full contract detail extraction"""
    logger.info("🚀 Starting FULL Contract Detail Extraction")
    
    # Load existing contracts
    existing_contracts = load_existing_contracts()
    
    if not existing_contracts:
        logger.error("❌ No existing contracts found.")
        return
    
    logger.info(f"📋 Loaded {len(existing_contracts)} existing contracts")
    
    # Filter out federal contracts (skip them as we don't have access)
    non_federal_contracts = [c for c in existing_contracts if not is_federal_bid(c)]
    federal_count = len(existing_contracts) - len(non_federal_contracts)
    
    logger.info(f"🚫 Skipping {federal_count} federal contracts (no access)")
    logger.info(f"✅ Processing {len(non_federal_contracts)} non-federal contracts")
    
    if not non_federal_contracts:
        logger.info("❌ No non-federal contracts to process")
        return
    
    # Scrape detailed information from ALL non-federal contracts
    detailed_contracts = scrape_contract_details(non_federal_contracts, max_contracts=None)  # No limit - process all
    
    # Save results
    save_detailed_contracts(detailed_contracts)
    
    logger.info("✅ FULL contract detail extraction complete!")
    logger.info(f"📊 Final Results: {len(detailed_contracts)} contracts processed with detailed information")

if __name__ == "__main__":
    main()