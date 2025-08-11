#!/usr/bin/env python3
"""
Portal Authentication System Test Suite
=======================================

Comprehensive testing for the portal authentication and registration system.
Tests all components with known LA region cities that use different portal types.

Test sequence:
1. Portal Detection - Identify portal types and registration requirements
2. Flag Creation - Generate registration flags for manual intervention
3. Credential Management - Test secure credential storage (simulation)
4. Pattern Library - Test pattern storage and retrieval
5. Integration Test - Full workflow simulation
"""

import sys
import os
from datetime import datetime
from typing import Dict, List, Any

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.portal.detector import PortalDetector
from src.portal.credential_manager import CredentialManager
from src.portal.pattern_library import PortalPatternLibrary
from src.ai_agents.pattern_discovery_agent import PatternDiscoveryAgent
from src.database.connection import DatabaseManager
from src.database.models import PortalType, AccountStatus, FlagStatus

def main():
    """Run comprehensive portal system tests"""
    print("🧪 Portal Authentication System Test Suite")
    print("=" * 60)
    
    # Test data - LA region cities with different portal types
    test_cities = [
        {
            'city_name': 'Los Angeles',
            'website_url': 'https://www.lacity.org/business/contracting-procurement',
            'expected_portal': 'Unknown (to be detected)',
            'notes': 'Major city - highest priority'
        },
        {
            'city_name': 'San Diego',
            'website_url': 'https://www.sandiego.gov/purchasing-contracting',
            'expected_portal': 'Unknown (to be detected)',
            'notes': 'Major city - high priority'
        },
        {
            'city_name': 'Santa Monica',
            'website_url': 'https://www.santamonica.gov/business/procurement',
            'expected_portal': 'Unknown (to be detected)', 
            'notes': 'Medium city - test case'
        },
        {
            'city_name': 'Anaheim',
            'website_url': 'https://www.anaheim.net/1316/Procurement',
            'expected_portal': 'Unknown (to be detected)',
            'notes': 'Orange County - regional test'
        }
    ]
    
    # Initialize components
    detector = PortalDetector()
    credential_manager = CredentialManager()
    pattern_library = PortalPatternLibrary()
    ai_agent = PatternDiscoveryAgent()
    db = DatabaseManager()
    
    # Test Results Storage
    test_results = {
        'portal_detection': [],
        'credential_tests': [],
        'pattern_tests': [],
        'integration_tests': [],
        'flags_created': 0,
        'total_cost': 0.0
    }
    
    print(f"Testing with {len(test_cities)} LA region cities\n")
    
    # Test 1: Portal Detection
    print("🔍 Test 1: Portal Detection")
    print("-" * 30)
    
    for city in test_cities:
        print(f"Analyzing {city['city_name']}...")
        
        detection_result = detector.detect_city_portal(
            city['city_name'],
            city['website_url']
        )
        
        test_results['portal_detection'].append(detection_result)
        
        # Display results
        portal_type = detection_result.get('portal_type', PortalType.NONE).value
        registration_req = "🔐" if detection_result.get('registration_required', False) else "🌐"
        confidence = detection_result.get('detection_confidence', 0.0)
        
        print(f"  {registration_req} Portal: {portal_type} (confidence: {confidence:.1%})")
        
        if detection_result.get('portal_url'):
            print(f"     URL: {detection_result['portal_url']}")
        
        if detection_result.get('registration_notes'):
            print(f"     Notes: {detection_result['registration_notes']}")
        
        print()
    
    # Test 2: Registration Flag Analysis
    print("🚩 Test 2: Registration Flags Analysis")
    print("-" * 40)
    
    with db.get_session() as session:
        from src.database.models import RegistrationFlag
        
        flags = session.query(RegistrationFlag).filter_by(
            resolution_status=FlagStatus.PENDING
        ).order_by(RegistrationFlag.priority_score.desc()).all()
        
        print(f"📊 {len(flags)} registration flags created")
        test_results['flags_created'] = len(flags)
        
        if flags:
            print("\nTop Priority Flags:")
            for flag in flags[:3]:
                print(f"  🎯 {flag.city_name} - {flag.flag_reason} (Priority: {flag.priority_score})")
                print(f"     Portal: {flag.portal_type.value if flag.portal_type else 'Unknown'}")
                print(f"     Effort: {flag.estimated_manual_hours:.1f}h")
                print()
    
    # Test 3: Credential Management (Simulation)
    print("🔐 Test 3: Credential Management")
    print("-" * 35)
    
    # Test storing dummy credentials
    test_credential_result = credential_manager.store_credentials(
        city_name="Test City",
        portal_type=PortalType.PLANETBIDS,
        username="test_user",
        password="test_password_123",
        email="test@example.com"
    )
    
    print(f"Store test credentials: {'✅' if test_credential_result else '❌'}")
    
    # Test retrieving credentials
    retrieved = credential_manager.get_credentials("Test City", PortalType.PLANETBIDS)
    print(f"Retrieve credentials: {'✅' if retrieved else '❌'}")
    
    if retrieved:
        print(f"  Username: {retrieved['username']}")
        print(f"  Password: {'*' * len(retrieved['password'])}")
        print(f"  Encryption: {'✅' if credential_manager.cipher_suite else '❌ Plain text'}")
    
    # Get credential summary
    cred_summary = credential_manager.get_credentials_summary()
    print(f"  Total stored: {cred_summary['total_credentials']}")
    print(f"  Encryption enabled: {'✅' if cred_summary['encryption_enabled'] else '❌'}")
    
    test_results['credential_tests'].append({
        'store_success': test_credential_result,
        'retrieve_success': bool(retrieved),
        'encryption_enabled': cred_summary['encryption_enabled']
    })
    
    print()
    
    # Test 4: Pattern Library
    print("📚 Test 4: Pattern Library")
    print("-" * 28)
    
    # Get library stats
    library_stats = pattern_library.get_library_stats()
    print(f"Default patterns available: {library_stats['default_patterns_available']}")
    print(f"Database patterns: {library_stats['total_patterns']}")
    
    # Test getting pattern for PlanetBids
    planetbids_pattern = pattern_library.get_pattern_for_city("Test City", PortalType.PLANETBIDS)
    
    print(f"PlanetBids pattern retrieval: {'✅' if planetbids_pattern else '❌'}")
    
    if planetbids_pattern:
        print(f"  Pattern: {planetbids_pattern['pattern_name']}")
        print(f"  Login selectors: {len(planetbids_pattern['login_selectors'])}")
        print(f"  Document selectors: {len(planetbids_pattern['document_selectors'])}")
    
    test_results['pattern_tests'].append({
        'default_patterns': library_stats['default_patterns_available'],
        'pattern_retrieval': bool(planetbids_pattern)
    })
    
    print()
    
    # Test 5: Enhanced AI Agent (Simulation Mode)
    print("🤖 Test 5: Enhanced AI Agent")
    print("-" * 32)
    
    # Test enhanced analysis with first city
    test_city = test_cities[0]
    print(f"Testing enhanced AI analysis on {test_city['city_name']}...")
    
    ai_result = ai_agent.analyze_city_website(
        test_city['city_name'],
        test_city['website_url']
    )
    
    print(f"AI analysis: {'✅' if ai_result['success'] else '❌'}")
    
    if ai_result['success']:
        portal_info = ai_result.get('portal_info', {})
        print(f"  Portal detected: {portal_info.get('portal_type', 'none')}")
        print(f"  Registration required: {portal_info.get('registration_required', False)}")
        
        auth_info = ai_result.get('authentication', {})
        if auth_info:
            print(f"  Credentials available: {auth_info.get('credentials_available', False)}")
            print(f"  Registration needed: {auth_info.get('registration_needed', False)}")
        
        patterns = ai_result.get('patterns', {})
        selectors = patterns.get('selectors', {})
        print(f"  Patterns discovered: {len(selectors)} selectors")
        
        test_results['total_cost'] += ai_result.get('cost_estimate', 0.0)
    else:
        print(f"  Error: {ai_result.get('error', 'Unknown error')}")
    
    test_results['integration_tests'].append({
        'ai_analysis_success': ai_result['success'],
        'portal_detection_integrated': 'portal_info' in ai_result,
        'authentication_handled': 'authentication' in ai_result
    })
    
    print()
    
    # Final Summary
    print("📊 Test Suite Results Summary")
    print("=" * 40)
    
    # Portal Detection Summary
    detected_portals = {}
    registration_required = 0
    
    for result in test_results['portal_detection']:
        portal_type = result.get('portal_type', PortalType.NONE).value
        detected_portals[portal_type] = detected_portals.get(portal_type, 0) + 1
        
        if result.get('registration_required', False):
            registration_required += 1
    
    print(f"🔍 Portal Detection:")
    print(f"   Cities analyzed: {len(test_cities)}")
    print(f"   Portal types found: {len(detected_portals)}")
    for portal, count in detected_portals.items():
        print(f"     {portal}: {count}")
    print(f"   Requiring registration: {registration_required}")
    
    # System Status
    print(f"\n🚩 Registration Management:")
    print(f"   Flags created: {test_results['flags_created']}")
    print(f"   Manual intervention needed: {'Yes' if test_results['flags_created'] > 0 else 'No'}")
    
    print(f"\n🔐 Credential Management:")
    cred_tests = test_results['credential_tests'][0] if test_results['credential_tests'] else {}
    print(f"   Storage/retrieval: {'✅' if cred_tests.get('store_success') and cred_tests.get('retrieve_success') else '❌'}")
    print(f"   Encryption: {'✅' if cred_tests.get('encryption_enabled') else '❌ Plain text'}")
    
    print(f"\n📚 Pattern Library:")
    pattern_tests = test_results['pattern_tests'][0] if test_results['pattern_tests'] else {}
    print(f"   Default patterns: {pattern_tests.get('default_patterns', 0)}")
    print(f"   Pattern retrieval: {'✅' if pattern_tests.get('pattern_retrieval') else '❌'}")
    
    print(f"\n🤖 AI Integration:")
    integration_tests = test_results['integration_tests'][0] if test_results['integration_tests'] else {}
    print(f"   Enhanced analysis: {'✅' if integration_tests.get('ai_analysis_success') else '❌'}")
    print(f"   Portal integration: {'✅' if integration_tests.get('portal_detection_integrated') else '❌'}")
    print(f"   Authentication handling: {'✅' if integration_tests.get('authentication_handled') else '❌'}")
    
    print(f"\n💰 Estimated Costs:")
    print(f"   Total session cost: ${test_results['total_cost']:.2f}")
    
    # Recommendations
    print(f"\n🎯 Next Steps:")
    
    if test_results['flags_created'] > 0:
        print(f"   1. Complete {test_results['flags_created']} portal registrations")
        print(f"      Run: python portal_registration_manager.py")
    
    if not cred_tests.get('encryption_enabled'):
        print(f"   2. Set up credential encryption:")
        print(f"      export PORTAL_ENCRYPTION_KEY=<key>")
    
    if test_results['total_cost'] == 0:
        print(f"   3. Configure AI API keys for real pattern discovery:")
        print(f"      export ANTHROPIC_API_KEY=<key>")
    
    print(f"\n✅ Portal authentication system testing complete!")
    print(f"   System is ready for manual registration workflow")

if __name__ == "__main__":
    main()