#!/usr/bin/env python3
"""
Load HVAC contracts from BidNet into SQLite database for visualization
"""

import logging
import sys
import os
from datetime import datetime
from typing import List, Dict, Any
import pandas as pd

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.connection import DatabaseManager
from src.database.models import Contract, SourceType, GeographicRegion, ProcessingStatus
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import time

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_contract_details(result_element, page):
    """Extract details from a contract result element"""
    try:
        # Get title
        title_elem = result_element.query_selector('a[href*="/private/solicitation/"]')
        title = title_elem.inner_text().strip() if title_elem else "Unknown Title"
        
        # Get BidNet URL
        source_url = title_elem.get_attribute('href') if title_elem else None
        if source_url and not source_url.startswith('http'):
            source_url = f"https://www.bidnetdirect.com{source_url}"
            
        # Get agency/organization
        agency_elem = result_element.query_selector('.table-cell:nth-child(2)')
        agency = agency_elem.inner_text().strip() if agency_elem else "Unknown Agency"
        
        # Get location
        location_elem = result_element.query_selector('.table-cell:nth-child(3)')
        location = location_elem.inner_text().strip() if location_elem else "Unknown Location"
        
        # Get bid due date
        due_date_elem = result_element.query_selector('.table-cell:nth-child(4)')
        due_date_str = due_date_elem.inner_text().strip() if due_date_elem else ""
        
        # Parse due date
        bid_due_date = None
        if due_date_str:
            try:
                bid_due_date = datetime.strptime(due_date_str, '%m/%d/%Y').date()
            except:
                try:
                    bid_due_date = datetime.strptime(due_date_str, '%m-%d-%Y').date()
                except:
                    logger.warning(f"Could not parse due date: {due_date_str}")
        
        return {
            'title': title,
            'agency': agency,
            'location': location,
            'source_url': source_url,
            'bid_due_date': bid_due_date,
            'estimated_value': None,  # Not always visible in search results
            'contract_type': 'HVAC',
            'source_type': SourceType.BIDNET,
            'geographic_region': GeographicRegion.LA_REGION,
            'processing_status': ProcessingStatus.PENDING,
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        }
    except Exception as e:
        logger.error(f"Error extracting contract details: {e}")
        return None

def load_hvac_contracts():
    """Load HVAC contracts from BidNet into database"""
    logger.info("🚀 Starting HVAC contract loading")
    
    db_manager = DatabaseManager()
    contracts_loaded = 0
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            # Login to BidNet
            logger.info("🔐 Authenticating with BidNet...")
            page.goto("https://www.bidnetdirect.com/public/authentication/login")
            page.wait_for_timeout(3000)
            
            # Enter credentials
            page.fill('input[name="j_username"]', 'christophernguyen1@gmail.com')
            page.fill('input[name="j_password"]', 'K1rby123!')
            page.click('button[type="submit"]')
            page.wait_for_timeout(10000)
            
            logger.info("✅ Login completed")
            
            # Navigate to search
            logger.info("🔍 Navigating to search page...")
            page.goto("https://www.bidnetdirect.com/private/supplier/solicitations/search")
            page.wait_for_timeout(5000)
            
            # Search for HVAC contracts
            logger.info("🏢 Searching for HVAC contracts...")
            search_field = page.wait_for_selector("textarea#solicitationSingleBoxSearch", timeout=10000)
            search_field.fill("hvac")
            
            search_button = page.wait_for_selector("button#topSearchButton", timeout=10000)
            search_button.click()
            page.wait_for_timeout(5000)
            
            # Extract results
            logger.info("📋 Extracting contract results...")
            results = page.query_selector_all('[class*="table-row"]:not(.table-header)')
            logger.info(f"Found {len(results)} potential HVAC contracts")
            
            # Process each result
            for i, result in enumerate(results):
                try:
                    contract_data = extract_contract_details(result, page)
                    if contract_data and contract_data['title'] != "Unknown Title":
                        
                        # Check if contract already exists
                        existing = db_manager.session.query(Contract).filter_by(
                            source_url=contract_data['source_url']
                        ).first()
                        
                        if not existing:
                            contract = Contract(**contract_data)
                            db_manager.session.add(contract)
                            contracts_loaded += 1
                            logger.info(f"✅ Added contract {i+1}: {contract_data['title'][:60]}...")
                        else:
                            logger.info(f"⏭️  Contract {i+1} already exists: {contract_data['title'][:60]}...")
                            
                except Exception as e:
                    logger.error(f"❌ Error processing contract {i+1}: {e}")
                    continue
            
            # Commit all changes
            db_manager.session.commit()
            logger.info(f"💾 Committed {contracts_loaded} new contracts to database")
            
        except Exception as e:
            logger.error(f"❌ Error during extraction: {e}")
            db_manager.session.rollback()
        finally:
            browser.close()
            db_manager.close()
    
    # Add terminal bell alert
    print("\\a")  # Terminal bell
    logger.info(f"🎉 Contract loading complete! Added {contracts_loaded} new contracts")
    return contracts_loaded

if __name__ == "__main__":
    load_hvac_contracts()