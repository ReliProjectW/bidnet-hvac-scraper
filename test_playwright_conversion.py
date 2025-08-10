#!/usr/bin/env python3
"""
Test script to verify Playwright conversion is working correctly.
"""

import logging
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_imports():
    """Test that all modules can be imported."""
    logger.info("🧪 Testing module imports...")
    
    try:
        from config import Config
        logger.info("✅ Config imported")
        
        from src.auth.bidnet_auth import BidNetAuthenticator
        logger.info("✅ BidNetAuthenticator imported")
        
        from src.scraper.bidnet_search import BidNetSearcher
        logger.info("✅ BidNetSearcher imported")
        
        return True
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        return False

def test_browser_initialization():
    """Test that browser setup works without errors."""
    logger.info("🧪 Testing browser initialization...")
    
    try:
        from src.auth.bidnet_auth import BidNetAuthenticator
        
        # Test auth browser setup
        auth = BidNetAuthenticator()
        browser, context, page = auth.setup_browser()
        auth.cleanup()
        logger.info("✅ Authentication browser setup/cleanup successful")
        
        # Test search browser setup
        from src.scraper.bidnet_search import BidNetSearcher
        searcher = BidNetSearcher()
        browser, context, page = searcher.setup_browser()
        searcher.cleanup()
        logger.info("✅ Search browser setup/cleanup successful")
        
        return True
    except Exception as e:
        logger.error(f"❌ Browser setup failed: {e}")
        return False

def test_basic_functionality():
    """Test basic functionality without requiring credentials."""
    logger.info("🧪 Testing basic functionality...")
    
    try:
        from src.auth.bidnet_auth import BidNetAuthenticator
        from src.scraper.bidnet_search import BidNetSearcher
        
        # Test that authenticator methods exist
        auth = BidNetAuthenticator()
        assert hasattr(auth, 'setup_browser'), "setup_browser method missing"
        assert hasattr(auth, 'cleanup'), "cleanup method missing"
        assert hasattr(auth, 'save_cookies'), "save_cookies method missing"
        assert hasattr(auth, 'load_cookies'), "load_cookies method missing"
        logger.info("✅ Authentication methods exist")
        
        # Test that searcher methods exist
        searcher = BidNetSearcher()
        assert hasattr(searcher, 'search_contracts'), "search_contracts method missing"
        assert hasattr(searcher, 'search_with_browser'), "search_with_browser method missing"
        assert hasattr(searcher, 'filter_hvac_contracts'), "filter_hvac_contracts method missing"
        logger.info("✅ Search methods exist")
        
        return True
    except Exception as e:
        logger.error(f"❌ Basic functionality test failed: {e}")
        return False

def main():
    """Run all tests."""
    logger.info("🚀 Starting Playwright conversion test suite...")
    
    tests = [
        test_imports,
        test_browser_initialization, 
        test_basic_functionality
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        
    logger.info(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Playwright conversion is working correctly.")
        return 0
    else:
        logger.error("❌ Some tests failed. Please check the conversion.")
        return 1

if __name__ == "__main__":
    sys.exit(main())