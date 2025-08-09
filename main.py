#!/usr/bin/env python3
"""
BidNet HVAC Scraper
Main entry point for scraping HVAC contracts from BidNet Direct
"""

import sys
import logging
import argparse
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from auth.bidnet_auth import BidNetAuthenticator
from scraper.bidnet_search import BidNetSearcher
from config import Config

def setup_logging():
    """Set up logging configuration"""
    log_dir = Path(Config.LOGS_DIR)
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,  # Back to INFO for cleaner output
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'bidnet_scraper.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def test_authentication():
    """Test the authentication process"""
    logger = logging.getLogger(__name__)
    logger.info("Testing BidNet Direct authentication...")
    
    try:
        authenticator = BidNetAuthenticator()
        
        # Try to get authenticated session (will use cookies first, then login if needed)
        session = authenticator.get_authenticated_session()
        
        if authenticator.authenticated:
            logger.info("✅ Authentication successful!")
            
            # Test authenticated session
            if authenticator.test_authentication():
                logger.info("✅ Authenticated session is working!")
                return True
            else:
                logger.error("❌ Authenticated session test failed")
                return False
        else:
            logger.error("❌ Authentication failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Authentication error: {str(e)}")
        return False

def search_hvac_contracts():
    """Search for HVAC contracts"""
    logger = logging.getLogger(__name__)
    logger.info("Starting HVAC contract search...")
    
    try:
        searcher = BidNetSearcher()
        
        # Search for contracts (more comprehensive search)
        logger.info("Searching for contracts...")
        contracts = searcher.search_contracts(max_results=200)  # Increased for comprehensive search
        
        if not contracts:
            logger.warning("❌ No contracts found")
            return False
            
        logger.info(f"Found {len(contracts)} initial contracts")
        
        # Show all contracts found for debugging
        logger.info("\n=== ALL CONTRACTS FOUND ===")
        for i, contract in enumerate(contracts):
            logger.info(f"{i+1}. {contract.get('title', 'No title')[:100]}")
            logger.info(f"   Search keyword: {contract.get('search_keyword', 'Unknown')}")
        
        # Save raw contracts first so you can review the data
        logger.info("Saving raw contracts for analysis...")
        raw_excel = searcher.save_contracts_to_excel(contracts, "raw_contracts_debug.xlsx")
        logger.info(f"✅ Raw contracts saved to: {raw_excel}")
        
        # Filter for HVAC relevance
        logger.info("Filtering for HVAC relevance...")
        hvac_contracts = searcher.filter_hvac_contracts(contracts)
        
        if not hvac_contracts:
            logger.warning("❌ No HVAC-relevant contracts found after filtering")
            logger.info(f"💡 Check the raw data in: {raw_excel}")
            logger.info("💡 This will help us improve the HTML parsing")
            return True  # Still return success so you can see the raw data
            
        logger.info(f"✅ Found {len(hvac_contracts)} HVAC-relevant contracts")
        
        # Save filtered results to both CSV and Excel
        csv_file = searcher.save_contracts_to_csv(hvac_contracts)
        excel_file = searcher.save_contracts_to_excel(hvac_contracts)
        logger.info(f"✅ Results saved to:")
        logger.info(f"   CSV: {csv_file}")
        logger.info(f"   Excel: {excel_file}")
        
        # Display sample results
        logger.info("\n=== SAMPLE RESULTS ===")
        for i, contract in enumerate(hvac_contracts[:5]):  # Show first 5
            logger.info(f"\n{i+1}. {contract.get('title', 'No title')}")
            logger.info(f"   Agency: {contract.get('agency', 'Unknown')}")
            logger.info(f"   Location: {contract.get('location', 'Unknown')}")
            logger.info(f"   Value: {contract.get('estimated_value', 'Not specified')}")
            logger.info(f"   Relevance Score: {contract.get('hvac_relevance_score', 0)}")
            logger.info(f"   Matching Keywords: {contract.get('matching_keywords', [])}")
            if contract.get('url'):
                logger.info(f"   URL: {contract.get('url')}")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Search error: {str(e)}")
        return False

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="BidNet HVAC Contract Scraper")
    parser.add_argument("--test-auth", action="store_true", 
                       help="Test authentication only")
    parser.add_argument("--search", action="store_true",
                       help="Search for HVAC contracts")
    parser.add_argument("--download", action="store_true", 
                       help="Download PDFs from search results")
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=== BidNet HVAC Scraper Started ===")
    
    # Validate configuration
    if not Config.USERNAME or not Config.PASSWORD:
        logger.error("❌ Please set BIDNET_USERNAME and BIDNET_PASSWORD environment variables")
        logger.info("💡 Copy .env.example to .env and fill in your credentials")
        return 1
    
    if args.test_auth:
        logger.info("Running authentication test...")
        success = test_authentication()
        return 0 if success else 1
    
    if args.search:
        logger.info("Running HVAC contract search...")
        success = search_hvac_contracts()
        return 0 if success else 1
        
    if args.download:
        logger.info("Download functionality not implemented yet") 
        logger.info("This will be implemented in Phase 3")
        return 0
    
    # Default action - show help
    parser.print_help()
    logger.info("\n💡 To get started:")
    logger.info("1. Copy .env.example to .env and add your BidNet credentials")
    logger.info("2. Run: python main.py --test-auth")
    
    return 0

if __name__ == "__main__":
    exit(main())