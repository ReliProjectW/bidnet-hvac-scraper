#!/usr/bin/env python3
"""
Simple test - just search for "HVAC" and see what we get
"""

import sys
import logging
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from scraper.bidnet_search import BidNetSearcher

def test_hvac_search():
    """Test simple HVAC search"""
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    searcher = BidNetSearcher()
    
    print("🔍 Searching for 'HVAC' contracts...")
    
    # Search for just "HVAC"
    contracts = searcher.search_with_browser("HVAC", [])
    
    print(f"\n✅ Found {len(contracts)} total contracts")
    
    if contracts:
        print("\n🏆 Contract results:")
        for i, contract in enumerate(contracts[:10], 1):  # Show first 10
            title = contract.get('title', 'No title')
            location = contract.get('location', 'No location')
            due_date = contract.get('due_date', 'No due date')
            
            print(f"\n{i}. {title}")
            print(f"   Location: {location}")
            print(f"   Due: {due_date}")
            
            # Show any other fields we captured
            for key, value in contract.items():
                if key not in ['title', 'location', 'due_date'] and value:
                    print(f"   {key.title()}: {value}")
    else:
        print("❌ No contracts found")
    
    return contracts

if __name__ == "__main__":
    test_hvac_search()