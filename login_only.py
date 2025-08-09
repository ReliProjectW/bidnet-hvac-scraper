#!/usr/bin/env python3
"""
BidNet Login Only
Simple, focused login that saves cookies for later use
Based on the original working authentication code
"""

import sys
import logging
import time
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from auth.bidnet_auth import BidNetAuthenticator
from config import Config

def setup_logging():
    """Set up simple logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def login_and_save_cookies():
    """Login to BidNet and save cookies - that's it!"""
    logger = logging.getLogger(__name__)
    
    # Check credentials
    if not Config.USERNAME or not Config.PASSWORD:
        logger.error("❌ Please set BIDNET_USERNAME and BIDNET_PASSWORD in .env file")
        return False
    
    logger.info("🔐 Starting BidNet login process...")
    
    try:
        # Create authenticator (using our working code)
        authenticator = BidNetAuthenticator()
        
        # Attempt login using original working method
        logger.info("🌐 Opening browser and attempting login...")
        success = authenticator.login()
        
        if success:
            logger.info("✅ Login successful!")
            logger.info("💾 Cookies have been saved for future use")
            
            # Test the saved session
            logger.info("🧪 Testing saved session...")
            if authenticator.test_authentication():
                logger.info("✅ Saved session is working!")
                logger.info("🎉 Login module complete - you can now use other tools")
                return True
            else:
                logger.warning("⚠️ Login succeeded but session test failed")
                return False
        else:
            logger.error("❌ Login failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Login error: {str(e)}")
        return False

def main():
    """Main entry point"""
    setup_logging()
    
    print("🔐 BidNet Login Module")
    print("=" * 30)
    print("This module ONLY handles login and saves cookies.")
    print("After successful login, use other tools for searching.\n")
    
    success = login_and_save_cookies()
    
    if success:
        print("\n✅ SUCCESS! Next steps:")
        print("   1. Login cookies are saved")
        print("   2. You can now use the search tools")
        print("   3. Future logins will be much faster (2 seconds)")
    else:
        print("\n❌ LOGIN FAILED")
        print("   - Check your credentials in .env file")
        print("   - Make sure you can login manually to BidNet")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())