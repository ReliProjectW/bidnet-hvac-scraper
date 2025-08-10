#!/usr/bin/env python3
"""
Test 1: BidNet Login Functionality
Tests the login process without relying on cookies
"""

import logging
from config import Config
from src.auth.bidnet_auth import BidNetAuthenticator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_bidnet_login():
    """Test BidNet login process"""
    logger.info("🧪 Starting Test 1: BidNet Login")
    
    # Initialize authenticator
    authenticator = BidNetAuthenticator()
    
    try:
        # Attempt login
        logger.info("Attempting login...")
        success = authenticator.login()
        
        if success:
            logger.info("✅ Login test PASSED")
            
            # Test authentication by accessing a protected page
            logger.info("Testing authentication...")
            if authenticator.test_authentication():
                logger.info("✅ Authentication test PASSED")
            else:
                logger.error("❌ Authentication test FAILED")
                
        else:
            logger.error("❌ Login test FAILED")
            
    except Exception as e:
        logger.error(f"❌ Login test ERROR: {str(e)}")
    
    finally:
        # Clean up
        authenticator.cleanup()
        logger.info("Test 1 complete")

if __name__ == "__main__":
    test_bidnet_login()