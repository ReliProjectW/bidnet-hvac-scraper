"""
Portal Pattern Library
=====================

Library of reusable portal navigation patterns for different portal types.
Stores successful patterns and provides pattern matching for new cities.

Features:
- Pattern templates for common portal types
- Success rate tracking
- Pattern validation and testing
- Automatic pattern updates
- Cross-city pattern reuse
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import json

from ..database.connection import DatabaseManager
from ..database.models import PortalPattern, CityPortal, PortalType

logger = logging.getLogger(__name__)

class PortalPatternLibrary:
    """Manages reusable portal navigation patterns"""
    
    def __init__(self):
        self.db = DatabaseManager()
        
        # Built-in pattern templates
        self.default_patterns = self._load_default_patterns()
        
        logger.info("📚 Portal Pattern Library initialized")
    
    def _load_default_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Load built-in pattern templates for common portals"""
        return {
            'planetbids_generic': {
                'portal_type': PortalType.PLANETBIDS,
                'pattern_name': 'planetbids_generic_v1',
                'description': 'Generic PlanetBids portal navigation patterns',
                'login_selectors': {
                    'login_form': 'form[action*="login"], #loginForm, .login-form',
                    'username_field': '#username, input[name="username"], #email, input[name="email"], .username-input',
                    'password_field': '#password, input[name="password"], .password-input',
                    'login_button': 'input[type="submit"], button[type="submit"], .login-btn, .submit-btn',
                    'remember_me': 'input[name="remember"], #remember, .remember-checkbox'
                },
                'navigation_flow': [
                    {'step': 'navigate_to_login', 'url': 'login_url', 'selector': 'login_form'},
                    {'step': 'fill_credentials', 'username_selector': 'username_field', 'password_selector': 'password_field'},
                    {'step': 'submit_login', 'selector': 'login_button'},
                    {'step': 'verify_login', 'success_indicators': ['dashboard', 'welcome', 'logout', 'my-account']},
                    {'step': 'navigate_to_projects', 'selector': '.projects, .bids, .opportunities'},
                    {'step': 'extract_project_list', 'selector': 'project_list'}
                ],
                'document_selectors': {
                    'project_list': '.project-row, .bid-row, tbody tr, .opportunity-item',
                    'project_title': '.project-title, .bid-title, td.title a, .opportunity-title',
                    'project_agency': '.agency, .department, td.agency, .client-name',
                    'due_date': '.due-date, .bid-date, td.due, .deadline',
                    'project_value': '.value, .amount, .contract-value, td.value',
                    'project_link': 'a.view-details, .more-info, .project-link, .opportunity-link',
                    'documents_link': '.documents, .plans, .view-docs, a[href*="documents"], .attachments',
                    'download_links': '.document-download, .plan-download, a[href*="download"], .file-download',
                    'addenda_links': '.addenda, .amendments, .updates, .modifications'
                },
                'search_patterns': {
                    'search_form': '#search-form, .search-form, form[action*="search"]',
                    'search_input': 'input[name="search"], input[name="q"], #search-field, .search-input',
                    'category_filter': 'select[name="category"], .category-select, #category',
                    'date_range': 'input[name="date_from"], .date-range, #date-filter',
                    'search_button': 'input[type="submit"], .search-btn, .filter-btn'
                },
                'pagination_patterns': {
                    'pagination_container': '.pagination, .pager, .page-navigation',
                    'next_button': '.next, .page-next, a[rel="next"]',
                    'prev_button': '.prev, .page-prev, a[rel="prev"]',
                    'page_numbers': '.page-number, .pagination a[href*="page"]',
                    'current_page': '.current, .active, .selected'
                }
            },
            
            'bidsync_generic': {
                'portal_type': PortalType.BIDSYNC,
                'pattern_name': 'bidsync_generic_v1',
                'description': 'Generic BidSync portal navigation patterns',
                'login_selectors': {
                    'login_form': 'form[action*="login"], #signin-form, .login-form',
                    'username_field': '#email, input[name="email"], .email-input',
                    'password_field': '#password, input[name="password"], .password-input',
                    'login_button': 'input[type="submit"], .signin-btn, .login-button'
                },
                'navigation_flow': [
                    {'step': 'navigate_to_login', 'url': 'login_url'},
                    {'step': 'fill_credentials', 'username_selector': 'username_field', 'password_selector': 'password_field'},
                    {'step': 'submit_login', 'selector': 'login_button'},
                    {'step': 'navigate_to_opportunities', 'selector': '.opportunities, .solicitations'}
                ],
                'document_selectors': {
                    'opportunity_list': '.opportunity-row, .solicitation-row, .bid-opportunity',
                    'opportunity_title': '.opportunity-title, .solicitation-title, .title',
                    'opportunity_agency': '.agency, .organization, .client',
                    'due_date': '.due-date, .deadline, .response-date',
                    'opportunity_link': '.view-opportunity, .details-link, .more-info',
                    'documents_section': '.documents, .attachments, .files'
                }
            },
            
            'custom_city': {
                'portal_type': PortalType.CUSTOM,
                'pattern_name': 'custom_city_generic_v1',
                'description': 'Generic patterns for custom city websites',
                'document_selectors': {
                    'rfp_list': '.rfp-list, .bid-list, .procurement-list, .contracts table tbody tr',
                    'rfp_title': '.rfp-title, .bid-title, .title, h3 a, td.title',
                    'agency': '.agency, .department, .division, td.agency',
                    'due_date': '.due-date, .deadline, .close-date, td.due',
                    'rfp_link': '.view-rfp, .details, .more-info, a.rfp-link',
                    'documents_link': '.documents, .attachments, .downloads, a[href*="pdf"]'
                },
                'navigation_flow': [
                    {'step': 'find_procurement_page', 'selectors': ['.procurement', '.rfp', '.bids', '.contracting']},
                    {'step': 'extract_rfp_list', 'selector': 'rfp_list'},
                    {'step': 'follow_rfp_links', 'selector': 'rfp_link'}
                ]
            }
        }
    
    def get_pattern_for_city(self, city_name: str, portal_type: PortalType = None) -> Optional[Dict[str, Any]]:
        """
        Get the best pattern for a specific city
        
        Args:
            city_name: Name of the city
            portal_type: Optional portal type filter
            
        Returns:
            Best matching pattern or None
        """
        with self.db.get_session() as session:
            # First, try to find city-specific pattern
            query = session.query(PortalPattern).filter_by(is_active=True)
            
            if portal_type:
                query = query.filter_by(portal_type=portal_type)
            
            # Look for patterns that work with this city
            city_specific_patterns = query.filter(
                PortalPattern.works_with_cities.contains([city_name])
            ).order_by(PortalPattern.success_rate.desc()).all()
            
            if city_specific_patterns:
                return self._format_pattern(city_specific_patterns[0])
            
            # Fallback to generic pattern for portal type
            if portal_type:
                generic_patterns = query.filter_by(portal_type=portal_type).order_by(
                    PortalPattern.success_rate.desc()
                ).all()
                
                if generic_patterns:
                    return self._format_pattern(generic_patterns[0])
                
                # Use default pattern
                default_key = f"{portal_type.value}_generic"
                if default_key in self.default_patterns:
                    return self.default_patterns[default_key]
            
            return None
    
    def store_successful_pattern(self, city_name: str, portal_type: PortalType,
                               pattern_data: Dict[str, Any], success_metrics: Dict[str, Any]) -> bool:
        """
        Store a successful pattern for reuse
        
        Args:
            city_name: City where pattern was successful
            portal_type: Type of portal
            pattern_data: Pattern selectors and navigation
            success_metrics: Success rate, contracts found, etc.
            
        Returns:
            True if stored successfully
        """
        logger.info(f"📚 Storing successful pattern for {city_name} ({portal_type.value})")
        
        try:
            with self.db.get_session() as session:
                # Create pattern name
                pattern_name = f"{portal_type.value}_{city_name.lower().replace(' ', '_')}_v1"
                
                # Check if pattern already exists
                existing = session.query(PortalPattern).filter_by(
                    pattern_name=pattern_name
                ).first()
                
                if existing:
                    # Update existing pattern
                    existing.login_selectors = pattern_data.get('login_selectors', {})
                    existing.navigation_flow = pattern_data.get('navigation_flow', [])
                    existing.document_selectors = pattern_data.get('document_selectors', {})
                    existing.search_patterns = pattern_data.get('search_patterns', {})
                    existing.success_rate = success_metrics.get('success_rate', 0.0)
                    existing.total_attempts += 1
                    existing.successful_attempts += 1
                    existing.last_successful_use = datetime.utcnow()
                    existing.pattern_confidence = success_metrics.get('confidence', 0.0)
                    existing.updated_at = datetime.utcnow()
                    
                    # Add city to works_with_cities list
                    works_with = existing.works_with_cities or []
                    if city_name not in works_with:
                        works_with.append(city_name)
                        existing.works_with_cities = works_with
                    
                    logger.info(f"✅ Updated existing pattern: {pattern_name}")
                else:
                    # Create new pattern
                    pattern = PortalPattern(
                        portal_type=portal_type,
                        pattern_name=pattern_name,
                        login_selectors=pattern_data.get('login_selectors', {}),
                        navigation_flow=pattern_data.get('navigation_flow', []),
                        document_selectors=pattern_data.get('document_selectors', {}),
                        search_patterns=pattern_data.get('search_patterns', {}),
                        success_rate=success_metrics.get('success_rate', 1.0),
                        total_attempts=1,
                        successful_attempts=1,
                        last_successful_use=datetime.utcnow(),
                        created_from_city=city_name,
                        works_with_cities=[city_name],
                        pattern_confidence=success_metrics.get('confidence', 0.8)
                    )
                    session.add(pattern)
                    logger.info(f"✅ Created new pattern: {pattern_name}")
                
                session.commit()
                return True
                
        except Exception as e:
            logger.error(f"Error storing pattern: {e}")
            return False
    
    def update_pattern_success(self, pattern_id: int, success: bool, 
                             city_name: str = None) -> bool:
        """
        Update success metrics for a pattern
        
        Args:
            pattern_id: Pattern ID to update
            success: Whether the pattern was successful
            city_name: City where pattern was tested (optional)
            
        Returns:
            True if updated successfully
        """
        try:
            with self.db.get_session() as session:
                pattern = session.query(PortalPattern).get(pattern_id)
                
                if pattern:
                    pattern.total_attempts += 1
                    
                    if success:
                        pattern.successful_attempts += 1
                        pattern.last_successful_use = datetime.utcnow()
                        
                        # Add city to works_with_cities if provided
                        if city_name:
                            works_with = pattern.works_with_cities or []
                            if city_name not in works_with:
                                works_with.append(city_name)
                                pattern.works_with_cities = works_with
                    
                    # Recalculate success rate
                    pattern.success_rate = pattern.successful_attempts / pattern.total_attempts
                    
                    session.commit()
                    
                    logger.debug(f"Updated pattern {pattern.pattern_name}: {pattern.success_rate:.2%} success rate")
                    return True
                
        except Exception as e:
            logger.error(f"Error updating pattern success: {e}")
            
        return False
    
    def find_similar_patterns(self, portal_type: PortalType, 
                            min_success_rate: float = 0.5) -> List[Dict[str, Any]]:
        """
        Find patterns for similar portal types
        
        Args:
            portal_type: Type of portal to find patterns for
            min_success_rate: Minimum success rate threshold
            
        Returns:
            List of matching patterns
        """
        with self.db.get_session() as session:
            patterns = session.query(PortalPattern).filter(
                PortalPattern.portal_type == portal_type,
                PortalPattern.is_active == True,
                PortalPattern.success_rate >= min_success_rate
            ).order_by(PortalPattern.success_rate.desc()).all()
            
            return [self._format_pattern(pattern) for pattern in patterns]
    
    def _format_pattern(self, pattern: PortalPattern) -> Dict[str, Any]:
        """Format database pattern for use"""
        return {
            'id': pattern.id,
            'portal_type': pattern.portal_type.value,
            'pattern_name': pattern.pattern_name,
            'login_selectors': pattern.login_selectors or {},
            'navigation_flow': pattern.navigation_flow or [],
            'document_selectors': pattern.document_selectors or {},
            'search_patterns': pattern.search_patterns or {},
            'success_rate': pattern.success_rate,
            'works_with_cities': pattern.works_with_cities or [],
            'pattern_confidence': pattern.pattern_confidence,
            'created_from_city': pattern.created_from_city,
            'last_successful_use': pattern.last_successful_use
        }
    
    def validate_pattern(self, pattern: Dict[str, Any], test_url: str) -> Dict[str, Any]:
        """
        Validate a pattern against a test URL
        
        Args:
            pattern: Pattern to validate
            test_url: URL to test against
            
        Returns:
            Validation results
        """
        validation_result = {
            'pattern_valid': False,
            'selectors_found': {},
            'validation_score': 0.0,
            'errors': []
        }
        
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(test_url, timeout=10000)
                
                # Test document selectors
                document_selectors = pattern.get('document_selectors', {})
                total_selectors = len(document_selectors)
                found_selectors = 0
                
                for selector_name, selector in document_selectors.items():
                    try:
                        elements = page.query_selector_all(selector)
                        found = len(elements) > 0
                        validation_result['selectors_found'][selector_name] = {
                            'found': found,
                            'count': len(elements),
                            'selector': selector
                        }
                        
                        if found:
                            found_selectors += 1
                            
                    except Exception as e:
                        validation_result['selectors_found'][selector_name] = {
                            'found': False,
                            'error': str(e),
                            'selector': selector
                        }
                
                # Calculate validation score
                if total_selectors > 0:
                    validation_result['validation_score'] = found_selectors / total_selectors
                    validation_result['pattern_valid'] = validation_result['validation_score'] >= 0.5
                
                browser.close()
                
        except Exception as e:
            validation_result['errors'].append(str(e))
        
        return validation_result
    
    def get_library_stats(self) -> Dict[str, Any]:
        """Get statistics about the pattern library"""
        with self.db.get_session() as session:
            from sqlalchemy import func
            
            # Portal type distribution
            portal_counts = session.query(
                PortalPattern.portal_type,
                func.count(PortalPattern.id)
            ).group_by(PortalPattern.portal_type).all()
            
            # Success rate statistics
            avg_success_rate = session.query(func.avg(PortalPattern.success_rate)).scalar() or 0.0
            
            # Active patterns
            active_patterns = session.query(PortalPattern).filter_by(is_active=True).count()
            
            return {
                'total_patterns': session.query(PortalPattern).count(),
                'active_patterns': active_patterns,
                'portal_type_distribution': {pt.value: count for pt, count in portal_counts},
                'average_success_rate': float(avg_success_rate),
                'default_patterns_available': len(self.default_patterns)
            }
    
    def export_patterns(self, output_file: str) -> bool:
        """Export all patterns to JSON file"""
        try:
            with self.db.get_session() as session:
                patterns = session.query(PortalPattern).filter_by(is_active=True).all()
                
                export_data = {
                    'export_date': datetime.utcnow().isoformat(),
                    'patterns': [self._format_pattern(p) for p in patterns],
                    'default_patterns': self.default_patterns
                }
                
                with open(output_file, 'w') as f:
                    json.dump(export_data, f, indent=2, default=str)
                
                logger.info(f"📚 Exported {len(patterns)} patterns to {output_file}")
                return True
                
        except Exception as e:
            logger.error(f"Error exporting patterns: {e}")
            return False

def main():
    """Test pattern library functionality"""
    library = PortalPatternLibrary()
    
    # Get stats
    stats = library.get_library_stats()
    print(f"\n📚 Pattern Library Stats:")
    print(f"Total patterns: {stats['total_patterns']}")
    print(f"Active patterns: {stats['active_patterns']}")
    print(f"Default patterns: {stats['default_patterns_available']}")
    print(f"Average success rate: {stats['average_success_rate']:.1%}")
    
    # Test getting pattern for PlanetBids
    pattern = library.get_pattern_for_city("Test City", PortalType.PLANETBIDS)
    if pattern:
        print(f"\n🔍 Found pattern: {pattern['pattern_name']}")
        print(f"Document selectors: {len(pattern['document_selectors'])}")
        print(f"Login selectors: {len(pattern['login_selectors'])}")

if __name__ == "__main__":
    main()