#!/usr/bin/env python3
"""
BidNet Status Checker
Quick check to see if login cookies are working
"""

import sys
import json
import time
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import requests
from config import Config

def check_cookies():
    """Check if saved cookies are working"""
    cookies_file = Path(Config.DATA_DIR) / "bidnet_cookies.json"
    
    print("🔍 BidNet Status Checker")
    print("=" * 25)
    
    if not cookies_file.exists():
        print("❌ No saved cookies found")
        print("💡 Run: python login_only.py")
        return False
    
    try:
        with open(cookies_file, 'r') as f:
            cookie_data = json.load(f)
        
        # Check age
        cookie_age = time.time() - cookie_data.get("timestamp", 0)
        age_hours = cookie_age / 3600
        
        print(f"📅 Cookie age: {age_hours:.1f} hours")
        
        if cookie_age > 86400:
            print("⚠️ Cookies are over 24 hours old")
        else:
            print("✅ Cookies are fresh")
        
        # Test cookies
        session = requests.Session()
        
        for name, value in cookie_data.get("requests_cookies", {}).items():
            session.cookies.set(name, value)
        
        print("🧪 Testing authentication...")
        
        test_url = f"{Config.BASE_URL}private/supplier/solicitations/search"
        response = session.get(test_url, timeout=10)
        
        if response.status_code == 200 and 'login' not in response.url.lower():
            print("✅ Authentication is working!")
            print("🎉 You can use the page reader tools")
            return True
        else:
            print("❌ Authentication test failed")
            print("💡 Run: python login_only.py")
            return False
            
    except Exception as e:
        print(f"❌ Error checking status: {e}")
        print("💡 Run: python login_only.py")
        return False

def main():
    """Main status checker"""
    success = check_cookies()
    
    if success:
        print("\n🚀 Ready to use:")
        print("   python page_reader.py")
    else:
        print("\n🔧 Next step:")
        print("   python login_only.py")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())