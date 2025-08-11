#!/usr/bin/env python3
"""
Test the sample URLs provided by the user
"""

import logging
from contract_detail_scraper import scrape_contract_details, save_detailed_contracts

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Test with sample URLs provided by user"""
    
    # Sample contracts from the user's URLs
    sample_contracts = [
        {
            'title': 'Sample Contract 1',
            'primary_agency': 'Unknown Agency',
            'secondary_agency': 'State & Local Bids',
            'format_type': 'standard',
            'bidnet_url': 'https://www.bidnetdirect.com/private/supplier/interception/view-notice/443612578366'
        },
        {
            'title': 'Sample Contract 2', 
            'primary_agency': 'Unknown Agency',
            'secondary_agency': 'State & Local Bids',
            'format_type': 'standard',
            'bidnet_url': 'https://www.bidnetdirect.com/private/supplier/interception/view-notice/443612145885'
        },
        {
            'title': 'Sample Contract 3',
            'primary_agency': 'Unknown Agency', 
            'secondary_agency': 'State & Local Bids',
            'format_type': 'standard',
            'bidnet_url': 'https://www.bidnetdirect.com/private/supplier/interception/view-notice/2623753697'
        },
        {
            'title': 'Sample Contract 4',
            'primary_agency': 'Unknown Agency',
            'secondary_agency': 'State & Local Bids', 
            'format_type': 'standard',
            'bidnet_url': 'https://www.bidnetdirect.com/private/supplier/interception/view-notice/2622696722'
        },
        {
            'title': 'Sample Contract 5',
            'primary_agency': 'Unknown Agency',
            'secondary_agency': 'State & Local Bids',
            'format_type': 'standard', 
            'bidnet_url': 'https://www.bidnetdirect.com/private/supplier/interception/view-notice/443606116157'
        }
    ]
    
    logger.info(f"🧪 Testing with {len(sample_contracts)} sample URLs")
    
    # Scrape detailed information
    detailed_contracts = scrape_contract_details(sample_contracts, max_contracts=5)
    
    # Save results
    save_detailed_contracts(detailed_contracts)
    
    logger.info("✅ Sample URL testing complete!")

if __name__ == "__main__":
    main()