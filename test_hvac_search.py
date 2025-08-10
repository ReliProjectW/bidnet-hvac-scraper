#!/usr/bin/env python3
"""
Test script to search for HVAC contracts using the converted Playwright scraper.
"""

import logging
import sys
from pathlib import Path
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_hvac_search():
    """Test searching for HVAC contracts."""
    logger.info("🔍 Starting HVAC search test...")
    
    try:
        from src.scraper.bidnet_search import BidNetSearcher
        
        # Initialize searcher
        searcher = BidNetSearcher()
        logger.info("✅ Searcher initialized")
        
        # Test search with just "HVAC" keyword
        keywords = ["HVAC"]
        location_filters = []  # No location filter for this test
        
        logger.info(f"🔍 Searching for contracts with keyword: {keywords[0]}")
        
        # Perform search
        contracts = searcher.search_contracts(
            keywords=keywords,
            location_filters=location_filters,
            max_results=10  # Limit results for testing
        )
        
        logger.info(f"📋 Found {len(contracts)} contracts")
        
        if contracts:
            logger.info("✅ Search successful! Here are the first few results:")
            for i, contract in enumerate(contracts[:3]):
                logger.info(f"  {i+1}. {contract.get('title', 'No title')[:100]}")
                logger.info(f"     Agency: {contract.get('agency', 'Unknown')}")
                logger.info(f"     Location: {contract.get('location', 'Unknown')}")
                logger.info(f"     URL: {contract.get('url', 'No URL')}")
                logger.info("")
            
            # Filter for HVAC relevance
            hvac_contracts = searcher.filter_hvac_contracts(contracts)
            logger.info(f"🎯 {len(hvac_contracts)} contracts are HVAC-relevant")
            
            # Save results to a test file
            if hvac_contracts:
                output_file = searcher.save_contracts_to_excel(
                    hvac_contracts, 
                    "test_hvac_results.xlsx"
                )
                logger.info(f"💾 Results saved to: {output_file}")
                
        else:
            logger.warning("⚠️ No contracts found. This could indicate:")
            logger.warning("  - Authentication issues")
            logger.warning("  - Changes in the site structure")
            logger.warning("  - Network connectivity problems")
            
        return len(contracts) > 0
        
    except Exception as e:
        logger.error(f"❌ HVAC search test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the HVAC search test."""
    logger.info("🚀 Starting HVAC search test with Playwright...")
    
    success = test_hvac_search()
    
    if success:
        logger.info("🎉 HVAC search test completed successfully!")
        return 0
    else:
        logger.error("❌ HVAC search test failed.")
        return 1

if __name__ == "__main__":
    sys.exit(main())