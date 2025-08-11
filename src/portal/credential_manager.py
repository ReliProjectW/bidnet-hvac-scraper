"""
Portal Credential Management System
==================================

Securely manages portal login credentials with:
- Encrypted password storage
- Credential verification
- Session management
- Business profile management
- Security best practices

Features:
- AES encryption for passwords
- Environment variable for encryption key
- Credential validation and testing
- Business information storage for registrations
- Audit trail for credential usage
"""

import logging
import os
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import json

# Encryption imports
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    logging.warning("Cryptography library not available - credentials will be stored in plain text")

from playwright.sync_api import sync_playwright

from ..database.connection import DatabaseManager
from ..database.models import (
    PortalCredential, CityPortal, PortalSession, RegistrationFlag,
    PortalType, AccountStatus, ProcessingStatus, FlagStatus
)

logger = logging.getLogger(__name__)

class CredentialManager:
    """Manages portal login credentials securely"""
    
    def __init__(self):
        self.db = DatabaseManager()
        
        # Initialize encryption
        self.encryption_key = self._get_or_create_encryption_key()
        if ENCRYPTION_AVAILABLE and self.encryption_key:
            self.cipher_suite = Fernet(self.encryption_key)
        else:
            self.cipher_suite = None
            logger.warning("⚠️ Credentials will be stored without encryption")
        
        # Default business profile for registrations
        self.default_business_profile = {
            'business_name': os.getenv('BUSINESS_NAME', 'HVAC Contractor Services'),
            'business_address': os.getenv('BUSINESS_ADDRESS', '123 Business St, Los Angeles, CA 90001'),
            'business_phone': os.getenv('BUSINESS_PHONE', '(555) 123-4567'),
            'email': os.getenv('BUSINESS_EMAIL', 'contractor@example.com'),
            'tax_id': os.getenv('BUSINESS_TAX_ID', '12-3456789')
        }
        
        logger.info("🔐 Credential Manager initialized")
    
    def _get_or_create_encryption_key(self) -> Optional[bytes]:
        """Get encryption key from environment or create new one"""
        if not ENCRYPTION_AVAILABLE:
            return None
        
        # Try to get existing key from environment
        key_b64 = os.getenv('PORTAL_ENCRYPTION_KEY')
        if key_b64:
            try:
                return base64.b64decode(key_b64)
            except Exception as e:
                logger.warning(f"Invalid encryption key in environment: {e}")
        
        # Generate new key
        try:
            password = os.getenv('PORTAL_MASTER_PASSWORD', 'default_password_change_this').encode()
            salt = os.urandom(16)
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(password))
            
            # Save salt and key info for future use (in production, handle this securely)
            logger.info("🔑 Generated new encryption key - save PORTAL_ENCRYPTION_KEY to environment")
            logger.info(f"PORTAL_ENCRYPTION_KEY={base64.b64encode(key).decode()}")
            
            return key
            
        except Exception as e:
            logger.error(f"Failed to create encryption key: {e}")
            return None
    
    def store_credentials(self, city_name: str, portal_type: PortalType, 
                         username: str, password: str, email: str = None,
                         business_info: Dict[str, str] = None) -> bool:
        """
        Store credentials for a city portal
        
        Args:
            city_name: Name of the city
            portal_type: Type of portal (PlanetBids, etc.)
            username: Login username
            password: Login password (will be encrypted)
            email: Email address used for registration
            business_info: Business information used for registration
            
        Returns:
            True if stored successfully
        """
        logger.info(f"🔐 Storing credentials for {city_name} ({portal_type.value})")
        
        try:
            with self.db.get_session() as session:
                portal_key = f"{city_name.lower().replace(' ', '_')}_{portal_type.value}"
                
                # Encrypt password
                encrypted_password = self._encrypt_password(password)
                
                # Merge business info with defaults
                business_profile = self.default_business_profile.copy()
                if business_info:
                    business_profile.update(business_info)
                
                # Check if credentials already exist
                existing = session.query(PortalCredential).filter_by(portal_key=portal_key).first()
                
                if existing:
                    # Update existing credentials
                    existing.username = username
                    existing.password_encrypted = encrypted_password
                    existing.email = email or existing.email
                    existing.business_name = business_profile.get('business_name')
                    existing.business_address = business_profile.get('business_address')
                    existing.business_phone = business_profile.get('business_phone')
                    existing.tax_id = business_profile.get('tax_id')
                    existing.updated_at = datetime.utcnow()
                    logger.info(f"✅ Updated existing credentials for {portal_key}")
                else:
                    # Create new credentials
                    credential = PortalCredential(
                        portal_key=portal_key,
                        city_name=city_name,
                        portal_type=portal_type,
                        username=username,
                        password_encrypted=encrypted_password,
                        email=email or business_profile.get('email'),
                        registration_date=datetime.utcnow(),
                        registration_method="manual",
                        registered_by="credential_manager",
                        business_name=business_profile.get('business_name'),
                        business_address=business_profile.get('business_address'),
                        business_phone=business_profile.get('business_phone'),
                        tax_id=business_profile.get('tax_id'),
                        verification_status=AccountStatus.PENDING
                    )
                    session.add(credential)
                    logger.info(f"✅ Created new credentials for {portal_key}")
                
                # Update city portal status
                city_portal = session.query(CityPortal).filter_by(city_name=city_name).first()
                if city_portal:
                    city_portal.account_status = AccountStatus.REGISTERED
                
                session.commit()
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to store credentials for {city_name}: {e}")
            return False
    
    def get_credentials(self, city_name: str, portal_type: PortalType = None) -> Optional[Dict[str, Any]]:
        """
        Get credentials for a city portal
        
        Args:
            city_name: Name of the city
            portal_type: Optional portal type filter
            
        Returns:
            Decrypted credentials or None
        """
        with self.db.get_session() as session:
            query = session.query(PortalCredential).filter_by(city_name=city_name)
            
            if portal_type:
                query = query.filter_by(portal_type=portal_type)
            
            credential = query.first()
            
            if credential:
                decrypted_password = self._decrypt_password(credential.password_encrypted)
                
                return {
                    'portal_key': credential.portal_key,
                    'city_name': credential.city_name,
                    'portal_type': credential.portal_type,
                    'username': credential.username,
                    'password': decrypted_password,
                    'email': credential.email,
                    'business_info': {
                        'business_name': credential.business_name,
                        'business_address': credential.business_address,
                        'business_phone': credential.business_phone,
                        'tax_id': credential.tax_id
                    },
                    'verification_status': credential.verification_status,
                    'last_verified': credential.last_verified
                }
            
            return None
    
    def verify_credentials(self, city_name: str, portal_type: PortalType = None, 
                          update_database: bool = True) -> Dict[str, Any]:
        """
        Verify credentials by attempting to login
        
        Args:
            city_name: Name of the city
            portal_type: Optional portal type
            update_database: Whether to update verification status in database
            
        Returns:
            Verification result
        """
        logger.info(f"🔍 Verifying credentials for {city_name}")
        
        result = {
            'success': False,
            'error': None,
            'verification_date': datetime.utcnow(),
            'session_cookies': None
        }
        
        try:
            # Get credentials
            credentials = self.get_credentials(city_name, portal_type)
            if not credentials:
                result['error'] = "No credentials found"
                return result
            
            # Get portal info
            portal_info = self._get_portal_info(city_name)
            if not portal_info or not portal_info.login_url:
                result['error'] = "No portal login URL found"
                return result
            
            # Attempt login
            login_result = self._attempt_login(portal_info, credentials)
            result.update(login_result)
            
            # Update database
            if update_database:
                self._update_verification_status(credentials['portal_key'], result)
            
        except Exception as e:
            logger.error(f"Error verifying credentials for {city_name}: {e}")
            result['error'] = str(e)
        
        return result
    
    def _attempt_login(self, portal_info: CityPortal, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Attempt to login to portal with credentials"""
        result = {
            'success': False,
            'error': None,
            'session_cookies': None
        }
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()
                
                # Navigate to login page
                page.goto(portal_info.login_url, timeout=15000)
                page.wait_for_load_state('networkidle', timeout=10000)
                
                # Try common login selectors
                login_selectors = [
                    {'username': '#username', 'password': '#password', 'submit': 'input[type="submit"]'},
                    {'username': '#email', 'password': '#password', 'submit': 'button[type="submit"]'},
                    {'username': 'input[name="username"]', 'password': 'input[name="password"]', 'submit': '.login-button'},
                    {'username': 'input[name="email"]', 'password': 'input[name="password"]', 'submit': '.submit-button'}
                ]
                
                login_success = False
                
                for selectors in login_selectors:
                    try:
                        # Check if selectors exist
                        username_field = page.query_selector(selectors['username'])
                        password_field = page.query_selector(selectors['password'])
                        
                        if username_field and password_field:
                            # Fill in credentials
                            username_field.fill(credentials['username'])
                            password_field.fill(credentials['password'])
                            
                            # Submit form
                            submit_button = page.query_selector(selectors['submit'])
                            if submit_button:
                                submit_button.click()
                            else:
                                # Try pressing Enter
                                password_field.press('Enter')
                            
                            # Wait for navigation or response
                            page.wait_for_load_state('networkidle', timeout=10000)
                            
                            # Check for login success indicators
                            current_url = page.url
                            page_content = page.content().lower()
                            
                            # Success indicators
                            if any(indicator in current_url.lower() for indicator in ['dashboard', 'home', 'welcome', 'profile']):
                                login_success = True
                                break
                            
                            if any(indicator in page_content for indicator in ['welcome', 'dashboard', 'logout', 'profile']):
                                login_success = True
                                break
                            
                            # Failure indicators
                            if any(indicator in page_content for indicator in ['invalid', 'incorrect', 'failed', 'error']):
                                result['error'] = "Invalid credentials"
                                break
                            
                    except Exception as e:
                        logger.debug(f"Login attempt failed with selectors {selectors}: {e}")
                        continue
                
                if login_success:
                    result['success'] = True
                    result['session_cookies'] = context.cookies()
                    logger.info(f"✅ Login successful for {credentials['city_name']}")
                else:
                    if not result['error']:
                        result['error'] = "Login failed - could not find login form or success indicators"
                
                context.close()
                browser.close()
                
        except Exception as e:
            result['error'] = f"Login attempt error: {str(e)}"
        
        return result
    
    def _get_portal_info(self, city_name: str) -> Optional[CityPortal]:
        """Get portal information from database"""
        with self.db.get_session() as session:
            return session.query(CityPortal).filter_by(city_name=city_name).first()
    
    def _update_verification_status(self, portal_key: str, verification_result: Dict[str, Any]):
        """Update credential verification status in database"""
        with self.db.get_session() as session:
            credential = session.query(PortalCredential).filter_by(portal_key=portal_key).first()
            
            if credential:
                if verification_result['success']:
                    credential.verification_status = AccountStatus.REGISTERED
                    credential.last_verified = verification_result['verification_date']
                    credential.verification_error = None
                    
                    # Update city portal success tracking
                    city_portal = session.query(CityPortal).filter_by(city_name=credential.city_name).first()
                    if city_portal:
                        city_portal.successful_logins += 1
                        city_portal.last_successful_login = verification_result['verification_date']
                else:
                    credential.verification_status = AccountStatus.FAILED
                    credential.verification_error = verification_result['error']
                    
                    # Update city portal failure tracking
                    city_portal = session.query(CityPortal).filter_by(city_name=credential.city_name).first()
                    if city_portal:
                        city_portal.failed_login_attempts += 1
                
                session.commit()
    
    def _encrypt_password(self, password: str) -> str:
        """Encrypt password for storage"""
        if self.cipher_suite and password:
            try:
                encrypted = self.cipher_suite.encrypt(password.encode())
                return base64.b64encode(encrypted).decode()
            except Exception as e:
                logger.warning(f"Password encryption failed: {e}")
                return password  # Fallback to plain text
        
        return password  # Store as plain text if encryption not available
    
    def _decrypt_password(self, encrypted_password: str) -> str:
        """Decrypt password from storage"""
        if self.cipher_suite and encrypted_password:
            try:
                encrypted_bytes = base64.b64decode(encrypted_password.encode())
                decrypted = self.cipher_suite.decrypt(encrypted_bytes)
                return decrypted.decode()
            except Exception as e:
                logger.debug(f"Password decryption failed, assuming plain text: {e}")
                return encrypted_password  # Assume it's plain text
        
        return encrypted_password  # Return as-is if no encryption
    
    def test_all_credentials(self) -> List[Dict[str, Any]]:
        """Test all stored credentials"""
        logger.info("🧪 Testing all stored credentials")
        
        results = []
        
        with self.db.get_session() as session:
            credentials = session.query(PortalCredential).all()
            
            for credential in credentials:
                logger.info(f"Testing {credential.city_name} ({credential.portal_type.value})")
                
                result = self.verify_credentials(credential.city_name, credential.portal_type, update_database=True)
                
                results.append({
                    'city_name': credential.city_name,
                    'portal_type': credential.portal_type.value,
                    'success': result['success'],
                    'error': result['error']
                })
                
                # Brief pause between tests
                import time
                time.sleep(2)
        
        logger.info(f"✅ Credential testing complete: {len(results)} tested")
        return results
    
    def get_credentials_summary(self) -> Dict[str, Any]:
        """Get summary of stored credentials"""
        with self.db.get_session() as session:
            from sqlalchemy import func
            
            total_credentials = session.query(PortalCredential).count()
            
            # Status counts
            status_counts = session.query(
                PortalCredential.verification_status,
                func.count(PortalCredential.portal_key)
            ).group_by(PortalCredential.verification_status).all()
            
            # Portal type counts
            portal_counts = session.query(
                PortalCredential.portal_type,
                func.count(PortalCredential.portal_key)
            ).group_by(PortalCredential.portal_type).all()
            
            return {
                'total_credentials': total_credentials,
                'status_counts': {status.value: count for status, count in status_counts},
                'portal_counts': {portal.value: count for portal, count in portal_counts},
                'encryption_enabled': self.cipher_suite is not None
            }
    
    def delete_credentials(self, city_name: str, portal_type: PortalType = None) -> bool:
        """Delete credentials for a city"""
        logger.warning(f"🗑️ Deleting credentials for {city_name}")
        
        try:
            with self.db.get_session() as session:
                query = session.query(PortalCredential).filter_by(city_name=city_name)
                
                if portal_type:
                    query = query.filter_by(portal_type=portal_type)
                
                credentials = query.all()
                
                for credential in credentials:
                    session.delete(credential)
                
                session.commit()
                
                logger.info(f"✅ Deleted {len(credentials)} credentials for {city_name}")
                return True
                
        except Exception as e:
            logger.error(f"Error deleting credentials: {e}")
            return False

def main():
    """Test credential management"""
    manager = CredentialManager()
    
    # Test storing credentials
    success = manager.store_credentials(
        city_name="Test City",
        portal_type=PortalType.PLANETBIDS,
        username="test_user",
        password="test_password",
        email="test@example.com"
    )
    
    print(f"Store credentials: {'✅' if success else '❌'}")
    
    # Test retrieving credentials
    credentials = manager.get_credentials("Test City", PortalType.PLANETBIDS)
    print(f"Retrieve credentials: {'✅' if credentials else '❌'}")
    
    if credentials:
        print(f"Username: {credentials['username']}")
        print(f"Password: {'*' * len(credentials['password'])}")
    
    # Get summary
    summary = manager.get_credentials_summary()
    print(f"\n📊 Summary: {summary['total_credentials']} credentials stored")
    print(f"Encryption: {'✅' if summary['encryption_enabled'] else '⚠️ Plain text'}")

if __name__ == "__main__":
    main()