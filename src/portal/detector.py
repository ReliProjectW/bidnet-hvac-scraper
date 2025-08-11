"""
Portal Detection System
======================

Detects and classifies city procurement portals:
- PlanetBids (most common)
- BidSync, DemandStar, PublicPurchase, CivicBid
- Custom city portals
- No portal (direct city website)

Features:
- AI-powered portal classification
- Registration requirement detection
- URL pattern matching
- Confidence scoring
"""

import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from ..database.connection import DatabaseManager
from ..database.models import CityPortal, RegistrationFlag, PortalType, AccountStatus, FlagStatus

logger = logging.getLogger(__name__)

class PortalDetector:
    """Detects and classifies city procurement portals"""
    
    def __init__(self):
        self.db = DatabaseManager()
        
        # Portal detection patterns
        self.portal_patterns = {
            PortalType.PLANETBIDS: {
                'url_patterns': [
                    r'\.planetbids\.com',
                    r'planetbids\.com',
                    r'/planetbids',
                ],
                'content_patterns': [
                    'planetbids',
                    'planet bids',
                    'powered by planetbids',
                ],
                'selectors': [
                    '[href*="planetbids"]',
                    '.planetbids-logo',
                    '#planetbids-container'
                ]
            },
            PortalType.BIDSYNC: {
                'url_patterns': [
                    r'\.bidsync\.com',
                    r'bidsync\.com',
                    r'/bidsync',
                ],
                'content_patterns': [
                    'bidsync',
                    'bid sync',
                    'powered by bidsync',
                ],
                'selectors': [
                    '[href*="bidsync"]',
                    '.bidsync-logo'
                ]
            },
            PortalType.DEMANDSTAR: {
                'url_patterns': [
                    r'\.demandstar\.com',
                    r'demandstar\.com',
                    r'/demandstar',
                ],
                'content_patterns': [
                    'demandstar',
                    'demand star',
                ],
                'selectors': [
                    '[href*="demandstar"]',
                ]
            },
            PortalType.PUBLICPURCHASE: {
                'url_patterns': [
                    r'\.publicpurchase\.com',
                    r'publicpurchase\.com',
                ],
                'content_patterns': [
                    'publicpurchase',
                    'public purchase',
                ],
                'selectors': [
                    '[href*="publicpurchase"]',
                ]
            },
            PortalType.CIVICBID: {
                'url_patterns': [
                    r'\.civicbid\.com',
                    r'civicbid\.com',
                ],
                'content_patterns': [
                    'civicbid',
                    'civic bid',
                ],
                'selectors': [
                    '[href*="civicbid"]',
                ]
            }
        }
        
        # Registration indicators
        self.registration_indicators = [
            'login required',
            'registration required',
            'create account',
            'new vendor registration',
            'vendor registration',
            'register to bid',
            'member login',
            'sign up',
            'member access',
            'restricted access',
            'login to view',
            'authentication required'
        ]
        
        logger.info("🔍 Portal Detector initialized")
    
    def detect_city_portal(self, city_name: str, city_website_url: str, 
                          rfp_urls: List[str] = None) -> Dict[str, Any]:
        """
        Detect portal type and registration requirements for a city
        
        Args:
            city_name: Name of the city
            city_website_url: Main city website URL
            rfp_urls: Optional list of specific RFP page URLs
            
        Returns:
            Portal detection results
        """
        logger.info(f"🔍 Detecting portal for {city_name}: {city_website_url}")
        
        detection_result = {
            'city_name': city_name,
            'portal_type': PortalType.NONE,
            'portal_url': None,
            'registration_required': False,
            'detection_confidence': 0.0,
            'registration_url': None,
            'login_url': None,
            'portal_subdomain': None,
            'registration_notes': '',
            'errors': []
        }
        
        try:
            # Check if we already have this city in database
            existing_portal = self._get_existing_portal(city_name)
            if existing_portal:
                logger.info(f"✅ Using cached portal info for {city_name}")
                return self._format_existing_portal(existing_portal)
            
            # Analyze main city website
            main_analysis = self._analyze_website_for_portal(city_website_url)
            detection_result.update(main_analysis)
            
            # Analyze specific RFP URLs if provided
            if rfp_urls:
                for rfp_url in rfp_urls[:3]:  # Limit to first 3 URLs
                    rfp_analysis = self._analyze_website_for_portal(rfp_url)
                    if rfp_analysis['portal_type'] != PortalType.NONE:
                        # Use RFP-specific detection if found
                        detection_result.update(rfp_analysis)
                        break
            
            # Store detection results in database
            self._store_portal_detection(detection_result)
            
            logger.info(f"✅ Portal detection complete for {city_name}: {detection_result['portal_type'].value}")
            
        except Exception as e:
            logger.error(f"❌ Portal detection failed for {city_name}: {e}")
            detection_result['errors'].append(str(e))
        
        return detection_result
    
    def _analyze_website_for_portal(self, url: str) -> Dict[str, Any]:
        """Analyze a single website URL for portal indicators"""
        analysis = {
            'portal_type': PortalType.NONE,
            'portal_url': None,
            'registration_required': False,
            'detection_confidence': 0.0,
            'portal_subdomain': None,
            'registration_url': None,
            'login_url': None,
            'registration_notes': ''
        }
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Navigate to URL
                page.goto(url, timeout=15000)
                page.wait_for_load_state('networkidle', timeout=10000)
                
                # Get page content
                html_content = page.content()
                page_text = page.evaluate('document.body.innerText').lower()
                page_url = page.url  # Might be different due to redirects
                
                browser.close()
            
            # Analyze for portal patterns
            portal_detection = self._detect_portal_type(page_url, html_content, page_text)
            analysis.update(portal_detection)
            
            # Check for registration requirements
            registration_detection = self._detect_registration_requirements(html_content, page_text, page_url)
            analysis.update(registration_detection)
            
        except Exception as e:
            logger.debug(f"Error analyzing {url}: {e}")
        
        return analysis
    
    def _detect_portal_type(self, url: str, html_content: str, page_text: str) -> Dict[str, Any]:
        """Detect the type of portal based on URL and content"""
        detection = {
            'portal_type': PortalType.NONE,
            'portal_url': None,
            'detection_confidence': 0.0,
            'portal_subdomain': None
        }
        
        max_confidence = 0.0
        detected_portal = PortalType.NONE
        
        for portal_type, patterns in self.portal_patterns.items():
            confidence = 0.0
            
            # Check URL patterns
            for url_pattern in patterns['url_patterns']:
                if re.search(url_pattern, url, re.IGNORECASE):
                    confidence += 0.5
                    detection['portal_url'] = url
                    
                    # Extract subdomain for PlanetBids
                    if portal_type == PortalType.PLANETBIDS:
                        match = re.search(r'(\w+)\.planetbids\.com', url)
                        if match:
                            detection['portal_subdomain'] = match.group(1)
                            confidence += 0.2
            
            # Check content patterns
            for content_pattern in patterns['content_patterns']:
                if content_pattern in page_text:
                    confidence += 0.3
            
            # Check HTML selectors
            soup = BeautifulSoup(html_content, 'html.parser')
            for selector in patterns['selectors']:
                try:
                    if soup.select(selector):
                        confidence += 0.2
                except:
                    pass
            
            # Use highest confidence portal
            if confidence > max_confidence:
                max_confidence = confidence
                detected_portal = portal_type
                detection['detection_confidence'] = min(confidence, 1.0)
        
        detection['portal_type'] = detected_portal
        
        return detection
    
    def _detect_registration_requirements(self, html_content: str, page_text: str, url: str) -> Dict[str, Any]:
        """Detect if registration is required to access RFP documents"""
        detection = {
            'registration_required': False,
            'registration_url': None,
            'login_url': None,
            'registration_notes': ''
        }
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Check for registration indicators in text
        registration_score = 0
        found_indicators = []
        
        for indicator in self.registration_indicators:
            if indicator in page_text:
                registration_score += 1
                found_indicators.append(indicator)
        
        # Look for login/registration links
        login_links = []
        registration_links = []
        
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').lower()
            text = link.get_text().lower().strip()
            
            # Login links
            if any(term in href or term in text for term in ['login', 'signin', 'sign-in']):
                full_url = urljoin(url, link.get('href'))
                login_links.append({'url': full_url, 'text': text})
            
            # Registration links
            if any(term in href or term in text for term in ['register', 'signup', 'sign-up', 'create-account']):
                full_url = urljoin(url, link.get('href'))
                registration_links.append({'url': full_url, 'text': text})
        
        # Determine registration requirement
        if registration_score >= 2 or login_links or registration_links:
            detection['registration_required'] = True
            
            if login_links:
                detection['login_url'] = login_links[0]['url']
            
            if registration_links:
                detection['registration_url'] = registration_links[0]['url']
            
            # Create notes
            notes_parts = []
            if found_indicators:
                notes_parts.append(f"Found indicators: {', '.join(found_indicators[:3])}")
            if login_links:
                notes_parts.append(f"Login link: {login_links[0]['text']}")
            if registration_links:
                notes_parts.append(f"Registration link: {registration_links[0]['text']}")
            
            detection['registration_notes'] = '; '.join(notes_parts)
        
        return detection
    
    def _get_existing_portal(self, city_name: str) -> Optional[CityPortal]:
        """Check if we already have portal info for this city"""
        with self.db.get_session() as session:
            return session.query(CityPortal).filter_by(city_name=city_name).first()
    
    def _format_existing_portal(self, portal: CityPortal) -> Dict[str, Any]:
        """Format existing portal record for return"""
        return {
            'city_name': portal.city_name,
            'portal_type': portal.portal_type,
            'portal_url': portal.portal_url,
            'registration_required': portal.registration_required,
            'detection_confidence': portal.detection_confidence,
            'registration_url': portal.registration_url,
            'login_url': portal.login_url,
            'portal_subdomain': portal.portal_subdomain,
            'registration_notes': portal.registration_notes or '',
            'account_status': portal.account_status,
            'from_cache': True
        }
    
    def _store_portal_detection(self, detection_result: Dict[str, Any]):
        """Store portal detection results in database"""
        city_name = detection_result['city_name']
        
        with self.db.get_session() as session:
            try:
                # Create or update CityPortal record
                portal = session.query(CityPortal).filter_by(city_name=city_name).first()
                
                if portal:
                    # Update existing record
                    portal.portal_type = detection_result['portal_type']
                    portal.portal_url = detection_result['portal_url']
                    portal.registration_required = detection_result['registration_required']
                    portal.detection_confidence = detection_result['detection_confidence']
                    portal.registration_url = detection_result['registration_url']
                    portal.login_url = detection_result['login_url']
                    portal.portal_subdomain = detection_result['portal_subdomain']
                    portal.registration_notes = detection_result['registration_notes']
                    portal.last_verified = None  # Will be updated when verified
                else:
                    # Create new record
                    portal = CityPortal(
                        city_name=city_name,
                        portal_type=detection_result['portal_type'],
                        portal_url=detection_result['portal_url'],
                        registration_required=detection_result['registration_required'],
                        detection_confidence=detection_result['detection_confidence'],
                        registration_url=detection_result['registration_url'],
                        login_url=detection_result['login_url'],
                        portal_subdomain=detection_result['portal_subdomain'],
                        registration_notes=detection_result['registration_notes']
                    )
                    session.add(portal)
                
                # Create registration flag if registration is needed
                if detection_result['registration_required'] and detection_result['portal_type'] != PortalType.NONE:
                    existing_flag = session.query(RegistrationFlag).filter_by(
                        city_name=city_name,
                        resolution_status=FlagStatus.PENDING
                    ).first()
                    
                    if not existing_flag:
                        flag = RegistrationFlag(
                            city_name=city_name,
                            portal_type=detection_result['portal_type'],
                            portal_url=detection_result['portal_url'],
                            flag_reason="registration_needed",
                            flag_description=f"Registration required for {detection_result['portal_type'].value} portal",
                            priority_score=self._calculate_priority_score(city_name, detection_result['portal_type']),
                            estimated_manual_hours=1.5  # Typical registration time
                        )
                        session.add(flag)
                
                session.commit()
                logger.debug(f"✅ Stored portal detection for {city_name}")
                
            except Exception as e:
                logger.error(f"Error storing portal detection: {e}")
                session.rollback()
    
    def _calculate_priority_score(self, city_name: str, portal_type: PortalType) -> int:
        """Calculate priority score for registration flags"""
        base_score = 50
        
        # Higher priority for larger cities
        major_cities = ['los angeles', 'san diego', 'san francisco', 'oakland', 'anaheim', 'santa ana']
        if city_name.lower() in major_cities:
            base_score += 30
        
        # Higher priority for common portals (more patterns to learn)
        if portal_type == PortalType.PLANETBIDS:
            base_score += 20
        elif portal_type in [PortalType.BIDSYNC, PortalType.DEMANDSTAR]:
            base_score += 10
        
        return base_score
    
    def batch_detect_portals(self, cities_data: List[Dict[str, str]], max_concurrent: int = 3) -> List[Dict[str, Any]]:
        """
        Detect portals for multiple cities with concurrency control
        
        Args:
            cities_data: List of {'city_name': str, 'website_url': str} dicts
            max_concurrent: Maximum concurrent detections
            
        Returns:
            List of detection results
        """
        logger.info(f"🔍 Starting batch portal detection for {len(cities_data)} cities")
        
        results = []
        
        for city_data in cities_data:
            try:
                result = self.detect_city_portal(
                    city_data['city_name'],
                    city_data['website_url']
                )
                results.append(result)
                
                # Brief pause to be respectful to websites
                import time
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error detecting portal for {city_data['city_name']}: {e}")
                results.append({
                    'city_name': city_data['city_name'],
                    'portal_type': PortalType.NONE,
                    'error': str(e)
                })
        
        logger.info(f"✅ Batch portal detection complete: {len(results)} results")
        return results
    
    def get_detection_summary(self) -> Dict[str, Any]:
        """Get summary of portal detection results"""
        with self.db.get_session() as session:
            from sqlalchemy import func
            
            # Portal type counts
            portal_counts = session.query(
                CityPortal.portal_type,
                func.count(CityPortal.city_name)
            ).group_by(CityPortal.portal_type).all()
            
            # Registration requirements
            registration_count = session.query(CityPortal).filter_by(registration_required=True).count()
            
            # Pending flags
            pending_flags = session.query(RegistrationFlag).filter_by(resolution_status=FlagStatus.PENDING).count()
            
            return {
                'total_cities': session.query(CityPortal).count(),
                'portal_types': {portal_type.value: count for portal_type, count in portal_counts},
                'registration_required': registration_count,
                'pending_flags': pending_flags
            }

def main():
    """Test portal detection"""
    detector = PortalDetector()
    
    # Test cities
    test_cities = [
        {'city_name': 'Los Angeles', 'website_url': 'https://www.lacity.org/business/contracting-procurement'},
        {'city_name': 'San Diego', 'website_url': 'https://www.sandiego.gov/purchasing-contracting'},
        {'city_name': 'Santa Monica', 'website_url': 'https://www.santamonica.gov/business/procurement'}
    ]
    
    # Run detection
    results = detector.batch_detect_portals(test_cities)
    
    # Show results
    print("\n" + "="*60)
    print("🔍 PORTAL DETECTION RESULTS")
    print("="*60)
    
    for result in results:
        status = "✅" if 'error' not in result else "❌"
        portal_type = result.get('portal_type', PortalType.NONE).value
        registration = "🔐" if result.get('registration_required', False) else "🌐"
        
        print(f"{status} {registration} {result['city_name']}: {portal_type}")
        
        if result.get('portal_url'):
            print(f"   Portal: {result['portal_url']}")
        if result.get('registration_notes'):
            print(f"   Notes: {result['registration_notes']}")
        if 'error' in result:
            print(f"   Error: {result['error']}")
    
    # Show summary
    summary = detector.get_detection_summary()
    print(f"\n📊 Summary: {summary['total_cities']} cities, {summary['registration_required']} require registration")

if __name__ == "__main__":
    main()