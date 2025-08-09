import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # BidNet Direct URLs
    BASE_URL = "https://www.bidnetdirect.com/"
    LOGIN_URL = "https://idp.bidnetdirect.com/profile/SAML2/POST/SSO?execution=e1s1"
    SEARCH_URL = "https://bidnetdirect.com/search"
    
    # Authentication credentials (from environment variables)
    USERNAME = os.getenv("BIDNET_USERNAME")
    PASSWORD = os.getenv("BIDNET_PASSWORD")
    
    # Search parameters for Southern California HVAC contracts
    SEARCH_PARAMS = {
        "location_filters": [
            "Los Angeles County, CA",
            "Orange County, CA", 
            "San Bernardino County, CA",
            "Riverside County, CA",
            "San Diego County, CA",
            "Ventura County, CA",
            "Imperial County, CA"
        ],
        "target_keywords": [
            # HVAC Systems
            "HVAC system replacement",
            "HVAC system installation", 
            "HVAC installation",
            "HVAC replacement",
            
            # Specific Equipment
            "split system",
            "heat pump",
            "heat pump replacement",
            "heat pump installation",
            "air conditioner",
            "air conditioning unit",
            "AC unit",
            "mini-split",
            "mini split",
            "furnace",
            "air handler",
            
            # Installation/Replacement Terms
            "install",
            "installation", 
            "replace",
            "replacement",
            "new HVAC",
            "HVAC upgrade"
        ],
        "negative_keywords": [
            # Geothermal (exclude)
            "geothermal",
            "ground source",
            "earth source",
            
            # Maintenance/Service (exclude)
            "maintenance",
            "service",
            "repair",
            "service contract",
            "maintenance contract",
            "service agreement",
            "ongoing maintenance",
            "preventive maintenance",
            "routine maintenance",
            "annual service",
            "service call",
            "troubleshoot"
        ],
        "industry_categories": [
            "Construction",
            "Building Services", 
            "Mechanical Services",
            "HVAC",
            "Electrical & Mechanical"
        ]
    }
    
    # File paths
    DATA_DIR = "data"
    RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
    PROCESSED_DATA_DIR = os.path.join(DATA_DIR, "processed") 
    LOGS_DIR = "logs"
    
    # Download settings
    MAX_PDF_SIZE_MB = 200
    DOWNLOAD_TIMEOUT = 300  # 5 minutes
    
    # Browser settings for Selenium
    BROWSER_SETTINGS = {
        "headless": False,  # Set to False for troubleshooting
        "window_size": (1920, 1080),
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }