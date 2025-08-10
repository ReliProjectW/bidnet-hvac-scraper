import time
import logging
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright
import requests

from config import Config

class BidNetAuthenticator:
    def __init__(self):
        self.session = requests.Session()
        self.page = None
        self.browser = None
        self.context = None
        self.playwright = None
        self.authenticated = False
        self.logger = logging.getLogger(__name__)
        self.cookies_file = Path(Config.DATA_DIR) / "bidnet_cookies.json"
        
    def setup_browser(self):
        """Set up Playwright browser with appropriate options"""
        if self.browser:
            return self.browser, self.context, self.page
            
        self.playwright = sync_playwright().start()
        
        # Launch browser with options similar to Selenium config
        self.browser = self.playwright.chromium.launch(
            headless=Config.BROWSER_SETTINGS.get("headless", False),
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage", 
                "--disable-gpu",
                "--disable-extensions"
            ]
        )
        
        # Create context with user agent and viewport
        self.context = self.browser.new_context(
            user_agent=Config.BROWSER_SETTINGS.get("user_agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"),
            viewport={
                'width': Config.BROWSER_SETTINGS.get("window_size", [1920, 1080])[0],
                'height': Config.BROWSER_SETTINGS.get("window_size", [1920, 1080])[1]
            }
        )
        
        # Create new page
        self.page = self.context.new_page()
        
        return self.browser, self.context, self.page
        
    def save_cookies(self):
        """Save cookies to file for reuse"""
        try:
            # Ensure data directory exists
            Path(Config.DATA_DIR).mkdir(exist_ok=True)
            
            # Get cookies from both Playwright and requests session
            playwright_cookies = self.context.cookies() if self.context else []
            requests_cookies = dict(self.session.cookies)
            
            cookie_data = {
                "playwright_cookies": playwright_cookies,
                "requests_cookies": requests_cookies,
                "timestamp": time.time()
            }
            
            with open(self.cookies_file, 'w') as f:
                json.dump(cookie_data, f, indent=2)
                
            self.logger.info(f"Cookies saved to {self.cookies_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save cookies: {str(e)}")
            return False
            
    def load_cookies(self):
        """Load cookies from file if they exist and are recent"""
        try:
            if not self.cookies_file.exists():
                self.logger.info("No saved cookies found")
                return False
                
            with open(self.cookies_file, 'r') as f:
                cookie_data = json.load(f)
                
            # Check if cookies are less than 24 hours old
            cookie_age = time.time() - cookie_data.get("timestamp", 0)
            if cookie_age > 86400:  # 24 hours
                self.logger.info("Saved cookies are too old, will re-authenticate")
                return False
                
            # Load cookies into requests session
            for name, value in cookie_data.get("requests_cookies", {}).items():
                self.session.cookies.set(name, value)
                
            self.logger.info("Cookies loaded from file")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load cookies: {str(e)}")
            return False
            
    def load_cookies_to_playwright(self):
        """Load saved cookies into Playwright context"""
        try:
            if not self.cookies_file.exists():
                return False
                
            with open(self.cookies_file, 'r') as f:
                cookie_data = json.load(f)
                
            playwright_cookies = cookie_data.get("playwright_cookies", [])
            
            if not playwright_cookies:
                # Try to convert old selenium cookies if they exist
                selenium_cookies = cookie_data.get("selenium_cookies", [])
                for cookie in selenium_cookies:
                    playwright_cookie = {
                        'name': cookie.get('name'),
                        'value': cookie.get('value'),
                        'url': f"https://{cookie.get('domain', '')}" if cookie.get('domain') else Config.BASE_URL,
                        'domain': cookie.get('domain'),
                        'path': cookie.get('path', '/'),
                    }
                    if cookie.get('secure') is not None:
                        playwright_cookie['secure'] = cookie.get('secure')
                    if cookie.get('httpOnly') is not None:
                        playwright_cookie['httpOnly'] = cookie.get('httpOnly')
                    playwright_cookies.append(playwright_cookie)
            
            if playwright_cookies and self.context:
                self.context.add_cookies(playwright_cookies)
                self.logger.info("Cookies loaded into Playwright context")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to load cookies to Playwright: {str(e)}")
            return False
        
    def login(self):
        """Authenticate with BidNet Direct using SAML SSO"""
        if not Config.USERNAME or not Config.PASSWORD:
            raise ValueError("Username and password must be set in environment variables")
            
        try:
            browser, context, page = self.setup_browser()
            self.logger.info("Starting BidNet Direct authentication")
            
            # Navigate directly to login URL (since we know it works)
            login_url = "https://www.bidnetdirect.com/public/authentication/login"
            self.logger.info(f"Navigating directly to login page: {login_url}")
            page.goto(login_url)
            
            # Wait for page to load with longer timeout for SAML redirect
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except:
                self.logger.warning("Page load timeout, continuing...")
            
            # Wait a bit for any redirects to complete
            page.wait_for_timeout(3000)
            
            self.logger.info(f"After navigation - Current URL: {page.url}")
            self.logger.info(f"After navigation - Page title: {page.title()}")
            
            # Now look for username field on the login page
            username_selectors = [
                "input[name='j_username']",  # BidNet specific
                "input[id='j_username']",    # BidNet specific
                "input[name='username']",
                "input[type='email']",
                "input[id*='username']",
                "input[id*='email']",
                "input[class*='username']",
                "#username",
                "#email"
            ]
            
            username_element = None
            for selector in username_selectors:
                try:
                    page.wait_for_selector(selector, timeout=10000)
                    if page.locator(selector).first.is_visible():
                        username_element = page.locator(selector).first
                        self.logger.info(f"Found username field with selector: {selector}")
                        break
                except:
                    continue
                    
            if not username_element:
                self.logger.error("Could not find username field")
                # Take a screenshot for debugging
                try:
                    page.screenshot(path="debug_login_page.png")
                    self.logger.info("Screenshot saved as debug_login_page.png")
                except:
                    pass
                return False
                
            # Look for password field
            password_selectors = [
                "input[name='j_password']",  # BidNet specific
                "input[id='j_password']",    # BidNet specific
                "input[name='password']",
                "input[type='password']", 
                "input[id*='password']",
                "#password"
            ]
            
            password_element = None
            for selector in password_selectors:
                try:
                    page.wait_for_selector(selector, timeout=5000)
                    if page.locator(selector).first.is_visible():
                        password_element = page.locator(selector).first
                        self.logger.info(f"Found password field with selector: {selector}")
                        break
                except:
                    continue
                    
            if not password_element:
                self.logger.error("Could not find password field")
                return False
                
            # Enter credentials
            self.logger.info("Entering credentials")
            username_element.clear()
            username_element.fill(Config.USERNAME)
            
            password_element.clear()
            password_element.fill(Config.PASSWORD)
            
            # Find and click login button
            login_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button[id*='login']",
                "button[class*='login']",
                ".login-button",
                "#login-button"
            ]
            
            login_button_element = None
            for selector in login_selectors:
                try:
                    page.wait_for_selector(selector, timeout=5000)
                    if page.locator(selector).first.is_visible():
                        login_button_element = page.locator(selector).first
                        self.logger.info(f"Found login button with selector: {selector}")
                        break
                except:
                    continue
                    
            if not login_button_element:
                self.logger.warning("Could not find login button, will try pressing Enter on password field")
                # Try pressing Enter on password field as fallback
                try:
                    password_element.press("Enter")
                    self.logger.info("Pressed Enter on password field")
                except:
                    self.logger.error("Could not find login button and Enter key failed")
                    return False
            else:
                # Click login
                self.logger.info("Clicking login button")
                login_button_element.click()
            
            # Wait for redirect/authentication to complete
            page.wait_for_load_state("networkidle")
            
            # Check if we're successfully authenticated
            current_url = page.url
            self.logger.info(f"Current URL after login: {current_url}")
            
            # Transfer cookies to requests session
            playwright_cookies = context.cookies()
            for cookie in playwright_cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])
                
            self.authenticated = True
            self.logger.info("Authentication successful")
            
            # Save cookies for future use
            self.save_cookies()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Authentication failed: {str(e)}")
            return False
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up Playwright resources"""
        try:
            if self.page:
                self.page.close()
                self.page = None
            if self.context:
                self.context.close()
                self.context = None
            if self.browser:
                self.browser.close()
                self.browser = None
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
        except Exception as e:
            self.logger.debug(f"Error during cleanup: {e}")
                
    def authenticate_with_cookies(self):
        """Try to authenticate using saved cookies"""
        self.logger.info("Attempting authentication with saved cookies...")
        
        # Try to load cookies into requests session
        if not self.load_cookies():
            return False
            
        # Test if the cookies work
        try:
            response = self.session.get(Config.SEARCH_URL)
            
            # Check if we're redirected to login (indicating auth failed)
            if "login" in response.url.lower() or response.status_code == 401:
                self.logger.info("Saved cookies are invalid, need fresh login")
                return False
                
            self.authenticated = True
            self.logger.info("✅ Authentication successful using saved cookies!")
            return True
            
        except Exception as e:
            self.logger.warning(f"Cookie authentication test failed: {str(e)}")
            return False
    
    def get_authenticated_session(self):
        """Return the authenticated requests session"""
        if not self.authenticated:
            # Try cookie authentication first
            if not self.authenticate_with_cookies():
                # Fall back to full login if cookies don't work
                if not self.login():
                    raise Exception("Authentication failed")
        return self.session
        
    def test_authentication(self):
        """Test if authentication is working by accessing a protected page"""
        if not self.authenticated:
            return False
            
        try:
            # Try to access the main dashboard or search page
            response = self.session.get(Config.SEARCH_URL)
            
            # Check if we're redirected to login (indicating auth failed)
            if "login" in response.url.lower() or response.status_code == 401:
                self.logger.warning("Authentication appears to have failed")
                return False
                
            self.logger.info("Authentication test successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Authentication test failed: {str(e)}")
            return False
    
    def is_login_page(self, page_or_url=None):
        """Detect if current page is a login page"""
        try:
            if page_or_url is None and hasattr(self, 'page') and self.page:
                # Check current Playwright page
                current_url = self.page.url
                page_title = self.page.title()
                page_source = self.page.content()
            elif isinstance(page_or_url, str):
                # URL string provided
                current_url = page_or_url
                page_title = ""
                page_source = ""
            else:
                # Playwright Page provided
                current_url = page_or_url.url
                page_title = page_or_url.title()
                page_source = page_or_url.content()
            
            # Check URL patterns
            login_url_patterns = [
                "login",
                "authentication", 
                "sso",
                "signin",
                "SAML2"
            ]
            
            # Check title patterns
            login_title_patterns = [
                "login",
                "sign in",
                "authentication",
                "sso"
            ]
            
            # Check if URL indicates login page
            for pattern in login_url_patterns:
                if pattern.lower() in current_url.lower():
                    return True
                    
            # Check if title indicates login page  
            for pattern in login_title_patterns:
                if pattern.lower() in page_title.lower():
                    return True
                    
            # Check for login form elements in page source
            if page_source and any(pattern in page_source.lower() for pattern in ['j_username', 'j_password', 'name="username"', 'type="password"']):
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking login page: {str(e)}")
            return False
    
    def auto_login_if_needed(self, page=None):
        """Automatically login if we detect we're on a login page"""
        try:
            target_page = page or self.page
            if not target_page:
                self.logger.error("No page available for auto-login")
                return False
                
            if self.is_login_page(target_page):
                self.logger.info("🔄 Login page detected - attempting automatic login")
                
                # Use existing login logic but with current page
                old_page = self.page
                self.page = target_page
                
                try:
                    success = self._perform_login_on_current_page()
                    if success:
                        self.logger.info("✅ Auto-login successful")
                        return True
                    else:
                        self.logger.error("❌ Auto-login failed")
                        return False
                finally:
                    self.page = old_page
            else:
                # Not on login page, we're good
                return True
                
        except Exception as e:
            self.logger.error(f"Auto-login error: {str(e)}")
            return False
    
    def _perform_login_on_current_page(self):
        """Perform login on current page (assumes we're already on login page)"""
        try:
            # Look for username field
            username_selectors = [
                "input[name='j_username']",
                "input[id='j_username']",
                "input[name='username']",
                "input[type='email']",
                "input[id*='username']",
                "#username"
            ]
            
            username_element = None
            for selector in username_selectors:
                try:
                    if self.page.locator(selector).first.is_visible(timeout=5000):
                        username_element = self.page.locator(selector).first
                        break
                except:
                    continue
                    
            if not username_element:
                self.logger.error("Could not find username field")
                return False
                
            # Look for password field
            password_selectors = [
                "input[name='j_password']",
                "input[id='j_password']", 
                "input[name='password']",
                "input[type='password']",
                "#password"
            ]
            
            password_element = None
            for selector in password_selectors:
                try:
                    if self.page.locator(selector).first.is_visible(timeout=2000):
                        password_element = self.page.locator(selector).first
                        break
                except:
                    continue
                    
            if not password_element:
                self.logger.error("Could not find password field")
                return False
                
            # Enter credentials
            self.logger.info("Entering credentials")
            username_element.clear()
            username_element.fill(Config.USERNAME)
            
            password_element.clear()
            password_element.fill(Config.PASSWORD)
            
            # Find and click submit button
            submit_selectors = [
                "input[type='submit']",
                "button[type='submit']", 
                "button:has-text('Sign In')",
                "button:has-text('Login')",
                ".login-button",
                "#loginButton"
            ]
            
            submit_element = None
            for selector in submit_selectors:
                try:
                    if self.page.locator(selector).first.is_visible(timeout=2000):
                        submit_element = self.page.locator(selector).first
                        break
                except:
                    continue
                    
            if submit_element:
                self.logger.info("Clicking login button")
                submit_element.click()
            else:
                # Try pressing Enter on password field
                password_element.press("Enter")
                
            # Wait for redirect
            self.page.wait_for_load_state("networkidle")
            
            # Check if login was successful
            if not self.is_login_page(self.page):
                self.logger.info("Login successful - no longer on login page")
                return True
            else:
                self.logger.error("Login may have failed - still on login page")
                return False
                
        except Exception as e:
            self.logger.error(f"Login on current page failed: {str(e)}")
            return False