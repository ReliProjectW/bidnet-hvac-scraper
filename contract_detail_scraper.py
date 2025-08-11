#!/usr/bin/env python3
"""
BidNet Contract Detail Scraper
Extracts detailed information from individual BidNet contract listing pages
Skips federal bids and focuses on extracting:
- Basic Details: reference number, issuing organization, solicitation type, etc.
- Details: location, purchase type, piggyback contract
- Dates: publication, closing date
- Contact Information
- Description
"""

import logging
import time
import subprocess
import os
import json
from datetime import datetime
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import pandas as pd

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def play_alert(message="Task complete"):
    """Play terminal bell and system notification"""
    print("\a", end="", flush=True)
    try:
        subprocess.run(['osascript', '-e', f'display notification "{message}" with title "Contract Detail Scraper"'], 
                      capture_output=True, check=False)
    except:
        pass

def handle_cookie_banner(page):
    """Handle cookie banner if present"""
    try:
        cookie_banner = page.query_selector('.cookie-banner')
        if cookie_banner:
            cookie_accept = page.query_selector('.cookie-banner button')
            if cookie_accept:
                logger.info("🍪 Accepting cookie banner...")
                cookie_accept.click()
                page.wait_for_timeout(1000)
                return True
    except:
        pass
    return False

def check_for_federal_access_restriction(page):
    """Check if page shows Federal Registration modal requiring upgrade"""
    try:
        # Wait a moment for any modals to appear
        page.wait_for_timeout(2000)
        
        # Look for Federal Registration modal indicators
        federal_modal_selectors = [
            'text="Federal Registration"',
            'text="Upgrade to Federal Notification"',
            'text="California Purchasing Group"',
            '.modal:has-text("Federal Registration")',
            'div:has-text("Federal Notification")',
            'text="An action is required before access to this content is granted"'
        ]
        
        for selector in federal_modal_selectors:
            try:
                element = page.query_selector(selector)
                if element and element.is_visible():
                    logger.debug(f"Found federal restriction with selector: {selector}")
                    # Close the modal if possible
                    close_button = page.query_selector('button:has-text("Cancel"), button:has-text("Close"), .modal-close, [aria-label="Close"]')
                    if close_button:
                        close_button.click()
                        page.wait_for_timeout(1000)
                    return True
            except:
                continue
        
        # Also check for generic access restriction message
        access_restriction_text = page.text_content("body").lower()
        if "action is required before access" in access_restriction_text or "federal notification" in access_restriction_text:
            return True
            
        return False
        
    except Exception as e:
        logger.debug(f"Error checking federal restriction: {e}")
        return False

def extract_bidnet_field_value(page, label_variations):
    """Extract field value from BidNet's .mets-field structure"""
    try:
        for label_text in label_variations:
            # Look for the specific BidNet field pattern
            selectors_to_try = [
                f'.mets-field-label:has-text("{label_text}") + .mets-field-body p',
                f'.mets-field-label:has-text("{label_text}") ~ .mets-field-body p',
                f'.mets-field:has(.mets-field-label:has-text("{label_text}")) .mets-field-body p',
                f'span:has-text("{label_text}") ~ div p',
                f'span:has-text("{label_text}") + div p'
            ]
            
            for selector in selectors_to_try:
                try:
                    element = page.query_selector(selector)
                    if element and element.is_visible():
                        text = element.inner_text().strip()
                        # Clean up the text - remove extra dashes and whitespace
                        if text and text != "--" and len(text) > 0:
                            # Remove leading/trailing dashes and extra whitespace
                            text = text.strip('- \t\n')
                            if text and len(text) > 0:
                                logger.debug(f"Found {label_text}: {text[:50]}...")
                                return text
                except Exception as e:
                    logger.debug(f"Error with selector {selector}: {e}")
                    continue
        
        return None
        
    except Exception as e:
        logger.debug(f"Error extracting field for labels {label_variations}: {e}")
        return None

def extract_contract_details(page, contract_url, original_contract_data):
    """Extract detailed information from a BidNet contract listing page"""
    try:
        logger.info(f"📄 Extracting details from: {contract_url}")
        
        # Navigate to the contract page
        page.goto(contract_url)
        page.wait_for_timeout(3000)
        
        handle_cookie_banner(page)
        
        # Check for Federal Registration modal (access restriction)
        if check_for_federal_access_restriction(page):
            logger.info(f"🚫 Federal access restriction detected - skipping contract")
            return None
        
        # Wait for page to load
        page.wait_for_selector('body', timeout=10000)
        
        # Initialize details dictionary with original data
        details = {
            'original_title': original_contract_data.get('title', ''),
            'original_agency': original_contract_data.get('primary_agency', ''),
            'original_url': contract_url,
            'scraped_at': datetime.now().isoformat()
        }
        
        # Extract Basic Details
        details.update(extract_basic_details(page))
        
        # Extract Additional Details  
        details.update(extract_additional_details(page))
        
        # Extract Dates
        details.update(extract_dates(page))
        
        # Extract Contact Information
        details.update(extract_contact_info(page))
        
        # Extract Description
        details.update(extract_description(page))
        
        logger.info(f"✅ Successfully extracted details for: {details.get('title', 'Unknown')[:50]}...")
        return details
        
    except Exception as e:
        logger.error(f"❌ Error extracting details from {contract_url}: {e}")
        return None

def extract_basic_details(page):
    """Extract basic contract details"""
    details = {}
    
    try:
        # BidNet-specific field extraction using their .mets-field structure
        bidnet_field_map = {
            'reference_number': ['Reference Number', 'Reference'],
            'issuing_organization': ['Issuing Organization', 'Agency'],
            'solicitation_type': ['Solicitation Type', 'Type', 'Contract Type'],
            'solicitation_number': ['Solicitation Number', 'Number'],
            'title': ['Title'],
            'source_id': ['Source ID', 'Source'],
            'project_number': ['Project Number', 'Project'],
            'category': ['Category', 'Classification']
        }
        
        # Extract fields using BidNet's specific structure
        for field_name, label_variations in bidnet_field_map.items():
            value = extract_bidnet_field_value(page, label_variations)
            details[field_name] = value if value else "Not Available"
        
        # Extract title from page heading if not found in fields
        if details.get('title') == "Not Available":
            title_selectors = ['h1', 'h2.page-title', '.solicitation-title']
            for selector in title_selectors:
                try:
                    title_element = page.query_selector(selector)
                    if title_element:
                        title_text = title_element.inner_text().strip()
                        if title_text and len(title_text) > 5:
                            details['title'] = title_text
                            break
                except:
                    continue
                    
    except Exception as e:
        logger.error(f"Error extracting basic details: {e}")
    
    return details

def extract_additional_details(page):
    """Extract location, purchase type, piggyback info"""
    details = {}
    
    try:
        # BidNet-specific field extraction
        additional_field_map = {
            'location': ['Location', 'Delivery Location', 'Work Location'],
            'purchase_type': ['Purchase Type', 'Contract Type', 'Solicitation Type'],
            'piggyback_contract': ['Piggyback', 'Piggyback Contract'],
            'prebid_conference': ['Prebid Conference', 'Pre-Bid Conference', 'Pre-bid Meeting'],
            'estimated_value': ['Estimated Value', 'Contract Value', 'Budget'],
            'duration': ['Duration', 'Contract Duration', 'Term']
        }
        
        for field_name, label_variations in additional_field_map.items():
            value = extract_bidnet_field_value(page, label_variations)
            if field_name == 'piggyback_contract':
                details[field_name] = value if value else "No"
            else:
                details[field_name] = value if value else "Not Available"
            
    except Exception as e:
        logger.error(f"Error extracting additional details: {e}")
    
    return details

def extract_dates(page):
    """Extract publication and closing dates"""
    details = {}
    
    try:
        # BidNet-specific date extraction
        date_field_map = {
            'publication_date': ['Publication', 'Publication Date', 'Published Date', 'Published'],
            'closing_date': ['Closing Date', 'Due Date', 'Response Due Date', 'Bid Due Date'],
            'prebid_date': ['Prebid Date', 'Pre-Bid Date', 'Pre-bid Conference Date'],
            'opening_date': ['Opening Date', 'Bid Opening Date', 'Public Opening']
        }
        
        for field_name, label_variations in date_field_map.items():
            value = extract_bidnet_field_value(page, label_variations)
            details[field_name] = value if value else "Not Available"
            
    except Exception as e:
        logger.error(f"Error extracting dates: {e}")
    
    return details

def extract_contact_info(page):
    """Extract contact information"""
    details = {}
    
    try:
        # BidNet-specific contact extraction
        contact_field_map = {
            'contact_name': ['Contact Name', 'Contact Person', 'Contact'],
            'contact_title': ['Contact Title', 'Title'],
            'contact_email': ['Contact Email', 'Email', 'E-mail'],
            'contact_phone': ['Contact Phone', 'Phone', 'Telephone', 'Tel'],
            'contact_fax': ['Contact Fax', 'Fax']
        }
        
        for field_name, label_variations in contact_field_map.items():
            value = extract_bidnet_field_value(page, label_variations)
            details[field_name] = value if value else "Not Available"
        
        # Also try to extract emails from mailto links
        if details.get('contact_email') == "Not Available":
            try:
                mailto_links = page.query_selector_all('a[href^="mailto:"]')
                for link in mailto_links:
                    href = link.get_attribute('href')
                    if href:
                        email = href.replace('mailto:', '').strip()
                        if '@' in email and '.' in email:
                            details['contact_email'] = email
                            break
            except:
                pass
        
        # Try to extract contact info from .no-label fields under Contact Information section
        try:
            contact_section = page.query_selector('h3:has-text("Contact Information")')
            if contact_section:
                # Get the parent section
                contact_container = contact_section.query_selector('xpath=..')
                if contact_container:
                    no_label_fields = contact_container.query_selector_all('.mets-field.no-label .mets-field-body p')
                    
                    contact_info_text = []
                    for field in no_label_fields:
                        text = field.inner_text().strip()
                        if text and text not in ['', ' ']:
                            contact_info_text.append(text)
                    
                    # Try to identify phone, email, name from the collected text
                    for text in contact_info_text:
                        # Phone number pattern
                        if any(char.isdigit() for char in text) and ('-' in text or '(' in text or len([c for c in text if c.isdigit()]) >= 7):
                            if details.get('contact_phone') == "Not Available":
                                details['contact_phone'] = text
                        # Email pattern
                        elif '@' in text and '.' in text:
                            if details.get('contact_email') == "Not Available":
                                details['contact_email'] = text
                        # Name pattern (text without numbers, not too short, not too long)
                        elif len(text) > 5 and len(text) < 50 and not any(char.isdigit() for char in text):
                            if details.get('contact_name') == "Not Available":
                                details['contact_name'] = text
        except Exception as e:
            logger.debug(f"Error extracting no-label contact info: {e}")
            
    except Exception as e:
        logger.error(f"Error extracting contact info: {e}")
    
    return details

def extract_description(page):
    """Extract contract description"""
    details = {}
    
    try:
        # BidNet-specific description extraction
        description_field_map = {
            'description': ['Description', 'Project Description', 'Scope of Work', 'Work Description'],
            'specifications': ['Specifications', 'Technical Specifications'],
            'requirements': ['Requirements', 'Project Requirements'],
            'scope_of_work': ['Scope of Work', 'Scope', 'Work Scope']
        }
        
        for field_name, label_variations in description_field_map.items():
            value = extract_bidnet_field_value(page, label_variations)
            if value and len(value) > 20:  # Only accept substantial descriptions
                details[field_name] = value
            else:
                details[field_name] = "Not Available"
        
        # Enhanced description extraction to capture all related content
        main_description = details.get('description', "")
        additional_info = []
        external_rfp_link = None
        
        # Look for additional description content in .noticeExternalUrl and extract the link
        try:
            external_url_section = page.query_selector('.noticeExternalUrl')
            if external_url_section:
                external_text = external_url_section.inner_text().strip()
                
                # Extract the actual URL link from this section
                link_element = external_url_section.query_selector('a')
                if link_element:
                    external_rfp_link = link_element.get_attribute('href')
                    logger.debug(f"Found external RFP link: {external_rfp_link}")
                
                if external_text and len(external_text) > 10:
                    additional_info.append(external_text)
        except:
            pass
        
        # Look for other description-related sections
        try:
            additional_sections = page.query_selector_all('.content-block .mets-field-body')
            for section in additional_sections:
                section_text = section.inner_text().strip()
                if (len(section_text) > 50 and 
                    section_text not in [main_description] and
                    any(keyword in section_text.lower() for keyword in [
                        'for more information', 'additional details', 'please', 'click', 'link',
                        'specifications', 'requirements', 'scope'
                    ])):
                    additional_info.append(section_text)
        except:
            pass
        
        # Combine main description with additional information (excluding the link part)
        if main_description and main_description != "Not Available":
            full_description = main_description
            # Add additional info but exclude the "For more information..." section since we have the link separately
            filtered_additional_info = []
            for info in additional_info:
                if not ("for more information" in info.lower() and "click" in info.lower() and "link" in info.lower()):
                    filtered_additional_info.append(info)
            
            if filtered_additional_info:
                full_description += "\n\n" + "\n\n".join(filtered_additional_info)
            details['description'] = full_description
        elif additional_info:
            # Filter out the "For more information..." text from additional info
            filtered_additional_info = []
            for info in additional_info:
                if not ("for more information" in info.lower() and "click" in info.lower() and "link" in info.lower()):
                    filtered_additional_info.append(info)
            
            if filtered_additional_info:
                details['description'] = "\n\n".join(filtered_additional_info)
        
        # Add the external RFP link as a separate field
        details['external_rfp_link'] = external_rfp_link if external_rfp_link else "Not Available"
        
        # If still no description found, try content blocks as fallback
        if details.get('description') == "Not Available":
            try:
                content_sections = page.query_selector_all('.content-block')
                for section in content_sections:
                    section_text = section.inner_text().strip()
                    if len(section_text) > 100:
                        if any(keyword in section_text.lower() for keyword in [
                            'project', 'work', 'service', 'contract', 'construction', 
                            'installation', 'maintenance', 'repair', 'replacement'
                        ]):
                            details['description'] = section_text
                            break
            except:
                pass
            
    except Exception as e:
        logger.error(f"Error extracting description: {e}")
    
    return details


def is_federal_bid(contract_data):
    """Check if contract is a federal bid (to skip)"""
    if not contract_data:
        return False
    
    # Check various fields for federal indicators
    text_to_check = " ".join([
        str(contract_data.get('secondary_agency', '')),
        str(contract_data.get('primary_agency', '')),
        str(contract_data.get('format_type', ''))
    ]).lower()
    
    federal_indicators = ['federal bids', 'federal notification', 'federal']
    
    return any(indicator in text_to_check for indicator in federal_indicators)

def load_existing_contracts():
    """Load existing contracts from the latest smart parser results"""
    try:
        # Look for the latest smart contracts file
        data_dir = "/Users/christophernguyen/bidnet-hvac-scraper/data"
        smart_files = [f for f in os.listdir(data_dir) if f.startswith('smart_contracts_') and f.endswith('.txt')]
        
        if not smart_files:
            logger.error("No smart contracts files found")
            return []
        
        # Get the latest file
        latest_file = sorted(smart_files)[-1]
        logger.info(f"Loading contracts from: {latest_file}")
        
        contracts = []
        current_contract = {}
        
        with open(os.path.join(data_dir, latest_file), 'r') as f:
            content = f.read()
        
        # Replace escaped newlines with actual newlines
        content = content.replace('\\n', '\n')
        
        # Split by contract separators
        contract_sections = content.split('Contract ')[1:]  # Skip header
        
        for section in contract_sections:
            lines = section.split('\n')
            contract = {}
            
            for line in lines:
                original_line = line
                line = line.strip()
                if ':' in line and original_line.startswith('  '):
                    key, value = line.split(':', 1)
                    key = key.strip().lower().replace(' ', '_')
                    value = value.strip()
                    contract[key] = value
            
            if contract.get('bidnet_url') and contract.get('title'):
                contracts.append(contract)
        
        logger.info(f"Loaded {len(contracts)} contracts from {latest_file}")
        return contracts
        
    except Exception as e:
        logger.error(f"Error loading existing contracts: {e}")
        return []

def scrape_contract_details(contracts_to_scrape, max_contracts=None):
    """Main function to scrape detailed contract information"""
    logger.info("🚀 Starting Contract Detail Scraping")
    play_alert("Starting contract detail scraping")
    
    detailed_contracts = []
    processed_count = 0
    skipped_federal = 0
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = context.new_page()
        
        try:
            # Login first
            logger.info("🔐 Logging in to BidNet...")
            page.goto("https://www.bidnetdirect.com/public/authentication/login")
            page.wait_for_timeout(3000)
            
            handle_cookie_banner(page)
            
            username = os.getenv("BIDNET_USERNAME")
            password = os.getenv("BIDNET_PASSWORD")
            
            page.fill("input[name='j_username']", username)
            page.fill("input[name='j_password']", password)
            page.click("button[type='submit']")
            page.wait_for_timeout(10000)
            
            logger.info("✅ Login successful!")
            
            # Process each contract
            for contract in contracts_to_scrape:
                if max_contracts and processed_count >= max_contracts:
                    break
                
                # Skip federal bids
                if is_federal_bid(contract):
                    logger.info(f"⏭️  Skipping federal bid: {contract.get('title', 'Unknown')[:50]}...")
                    skipped_federal += 1
                    continue
                
                contract_url = contract.get('bidnet_url')
                if not contract_url:
                    logger.info(f"⏭️  No URL for contract: {contract.get('title', 'Unknown')[:50]}...")
                    continue
                
                # Extract detailed information
                detailed_info = extract_contract_details(page, contract_url, contract)
                
                if detailed_info:
                    detailed_contracts.append(detailed_info)
                    processed_count += 1
                    logger.info(f"✅ Processed {processed_count}: {detailed_info.get('title', 'Unknown')[:50]}...")
                else:
                    logger.info(f"❌ Failed to extract details for: {contract.get('title', 'Unknown')[:50]}...")
                
                # Small delay between requests
                page.wait_for_timeout(2000)
            
        except Exception as e:
            logger.error(f"❌ Error during scraping: {e}")
            
        finally:
            browser.close()
    
    logger.info(f"🎉 Contract detail scraping complete!")
    logger.info(f"📊 Processed: {processed_count}, Skipped Federal: {skipped_federal}")
    play_alert(f"Detail scraping complete: {processed_count} contracts processed")
    
    return detailed_contracts

def save_detailed_contracts(contracts):
    """Save detailed contract information to Excel and JSON"""
    if not contracts:
        logger.info("📭 No detailed contracts to save")
        return
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save as JSON
    json_filename = f"data/detailed_contracts_{timestamp}.json"
    with open(json_filename, 'w') as f:
        json.dump(contracts, f, indent=2)
    
    logger.info(f"💾 Saved {len(contracts)} detailed contracts to {json_filename}")
    
    # Save as Excel
    excel_filename = f"/Users/christophernguyen/Documents/hvacscraper/detailed_hvac_contracts_{timestamp}.xlsx"
    
    # Convert to DataFrame
    df = pd.DataFrame(contracts)
    
    # Reorder columns for better readability
    column_order = [
        'original_title', 'title', 'reference_number', 'issuing_organization',
        'solicitation_type', 'solicitation_number', 'source_id', 'location', 'purchase_type', 
        'piggyback_contract', 'publication_date', 'closing_date', 'prebid_conference',
        'contact_name', 'contact_email', 'contact_phone',
        'description', 'external_rfp_link', 'estimated_value', 'duration',
        'original_agency', 'original_url', 'scraped_at'
    ]
    
    # Reorder columns (only include existing ones)
    existing_columns = [col for col in column_order if col in df.columns]
    remaining_columns = [col for col in df.columns if col not in existing_columns]
    final_columns = existing_columns + remaining_columns
    
    df = df[final_columns]
    
    with pd.ExcelWriter(excel_filename, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Detailed Contracts', index=False)
        
        # Create summary sheet
        summary_data = {
            'Metric': [
                'Total Contracts Processed',
                'Extraction Date',
                'Average Fields Extracted',
                'Contracts with Contact Info',
                'Contracts with Closing Dates',
                'Contracts with Descriptions'
            ],
            'Value': [
                len(contracts),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                len([col for col in df.columns if not col.startswith('original_')]),
                len(df[df['contact_email'] != 'Not Available']),
                len(df[df['closing_date'] != 'Not Available']),
                len(df[df['description'] != 'Not Available'])
            ]
        }
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    logger.info(f"📊 Saved detailed contracts Excel to {excel_filename}")
    
    # Update notes
    notes_file = "/Users/christophernguyen/Documents/hvacscraper/scraper_issues_and_fixes.txt"
    with open(notes_file, 'a') as f:
        f.write(f"\n\nDETAILED CONTRACT EXTRACTION - {datetime.now()}\n")
        f.write(f"SUCCESS: Extracted detailed information from individual contract pages\n")
        f.write(f"Total contracts processed: {len(contracts)}\n")
        f.write(f"JSON file: {json_filename}\n")
        f.write(f"Excel file: {excel_filename}\n")
        f.write(f"Features: Basic details, dates, contact info, descriptions extracted\n")
    
    play_alert(f"Detailed contracts saved: {len(contracts)} contracts")

def main():
    """Main execution function"""
    logger.info("🌟 BidNet Contract Detail Scraper Starting...")
    
    # Load existing contracts
    existing_contracts = load_existing_contracts()
    
    if not existing_contracts:
        logger.error("❌ No existing contracts found. Run smart_contract_parser.py first.")
        return
    
    logger.info(f"📋 Loaded {len(existing_contracts)} existing contracts")
    
    # Filter out federal contracts (skip them as we don't have access)
    non_federal_contracts = [c for c in existing_contracts if not is_federal_bid(c)]
    federal_count = len(existing_contracts) - len(non_federal_contracts)
    
    logger.info(f"🚫 Skipping {federal_count} federal contracts (no access)")
    logger.info(f"✅ Processing {len(non_federal_contracts)} non-federal contracts")
    
    if not non_federal_contracts:
        logger.info("❌ No non-federal contracts to process")
        return
    
    # Scrape detailed information from non-federal contracts
    detailed_contracts = scrape_contract_details(non_federal_contracts, max_contracts=5)  # Limit for testing
    
    # Save results
    save_detailed_contracts(detailed_contracts)
    
    logger.info("✅ Contract detail scraping process complete!")
    play_alert("All detail scraping tasks complete")

if __name__ == "__main__":
    main()